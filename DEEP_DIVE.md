# Deep Dive: Response Quality

## Why I Chose This (Over the Other Two Options)

The assignment offered three deep-dive paths:

| Option | Focus |
|--------|-------|
| **Data Integrations / Auth** | Connect real APIs (Google, Notion, Slack), handle OAuth |
| **Twin Sharing** | Multi-tenancy, let others create/share twins, access control |
| **Response Quality** | Improve accuracy via RAG, evaluation frameworks, hallucination detection |

I chose **Response Quality** for three reasons:

**1. It's the foundation everything else depends on.** Data integrations and twin sharing are multipliers — they expand *what* the twin can access or *who* can use it. But if the core responses are unfaithful, irrelevant, or sound like a generic chatbot, none of that matters. Quality is the constraint that determines whether a digital twin is useful or just a novelty.

**2. It's the most measurable.** Response quality gives you a clear evaluation loop: define metrics (faithfulness, relevance, persona), build an automated judge, run test cases, get scores, iterate. The other two options are harder to evaluate quantitatively — how do you score "good OAuth implementation" or "effective twin sharing UX"? With response quality, I can show before/after numbers and explain exactly what improved and why.

**3. It aligns with my deepest technical interests.** I've built RAG systems at Juume (over DLP rules for security log analysis) and DocSense (research papers with eval harnesses). The retrieval-reranking-generation-evaluation pipeline is where I have genuine depth, and this deep-dive lets me demonstrate that end-to-end — from chunking strategy to hybrid retrieval to LLM-as-Judge calibration.

**What I'd lose by not picking the others:**
- **Data Integrations / Auth** would showcase full-stack / infra skills (OAuth flows, token management, API integration). But the assignment provides an OpenAI key and says synthetic data is fine — the bottleneck isn't data access, it's what you *do* with the data.
- **Twin Sharing** would showcase product/systems design (multi-tenancy, access control, data partitioning). Interesting, but it's more of a platform engineering problem than an AI engineering one, and I wanted to stay close to the intelligence layer.

## What I Built

### 1. Hybrid Retrieval (Vector + BM25 with Reciprocal Rank Fusion)

**Problem:** Pure vector search misses exact-match queries. If someone asks "What's your GPA?" or "Do you know Kubernetes?", semantic similarity might not surface the right chunk because the answer is embedded in a larger context.

**Solution:** I implemented hybrid retrieval combining:
- **Vector search** via ChromaDB (cosine similarity over text-embedding-3-small embeddings)
- **BM25 keyword search** computed over the full document set
- **Reciprocal Rank Fusion (RRF)** to merge rankings from both signals

RRF works by assigning each document a score of `1 / (k + rank)` from each retrieval method, then summing. This is simple, parameter-light, and consistently outperforms either method alone.

**Tradeoff:** BM25 is computed in-memory over all documents at query time. For the ~41 chunks in this personal dataset, this is fine. At scale, I'd use a dedicated BM25 index (e.g., Elasticsearch) or a hybrid-native vector DB like Weaviate.

### 2. LLM-Based Reranking

**Problem:** The initial retrieval returns top-8 chunks, but not all are equally relevant. Including low-quality chunks dilutes the context and can cause the model to hallucinate or go off-topic.

**Solution:** After hybrid retrieval, I use a second gpt-4o-mini call to score each chunk's relevance to the query on a 1-5 scale, then keep only the top-5.

**Tradeoff:** This adds latency (~300-500ms) and one extra API call per query. In production, I'd use a dedicated cross-encoder model (e.g., ms-marco-MiniLM) for faster reranking. For this prototype, using the same LLM keeps the architecture simple and the dependency list short.

### 3. Query Decomposition for Broad Questions

**Problem:** Broad questions like "Tell me about yourself" require information scattered across multiple data sources — bio, resume, projects, personality. A single retrieval pass may only find chunks matching one aspect.

**Solution:** I detect broad queries using pattern matching and decompose them into 2-4 focused sub-queries using an LLM call. Each sub-query retrieves independently, results are merged (deduplicated by content), and then passed through the reranker. This dramatically improves recall for overview-style questions.

**Example:** "Tell me about yourself" might decompose into:
- "What is your educational background?"
- "What work experience do you have?"
- "What are your key technical skills?"
- "What are your interests and personality?"

**Tradeoff:** Adds one extra LLM call and multiplies retrieval calls. For a ~40-chunk dataset, the latency is acceptable (~1s total). For larger datasets, I'd cache decomposition results for common query patterns.

### 4. Confidence-Based Guardrails

**Problem:** When retrieval returns low-quality results (nothing relevant in the knowledge base), the model tends to hallucinate plausible-sounding answers that aren't grounded in my actual data.

**Solution:**
- **Confidence scoring:** I compute a confidence score from retrieval quality (RRF scores). When confidence is below a threshold, the response is prefixed with "I'm not entirely sure about this, but..."
- **Out-of-scope detection:** When retrieval returns nothing relevant and confidence is very low, the twin deflects gracefully: "That's outside what I can help with as Abhishek's digital twin."
- **System prompt constraints:** The prompt explicitly instructs the model to never fabricate information and to say "I don't have enough context on that" when unsure.

**Tradeoff:** The confidence threshold is a blunt instrument. A more sophisticated approach would use a trained classifier on (query, retrieved_chunks) pairs to predict whether the context is sufficient for a grounded response.

### 5. Source Citations

**Problem:** Users (and evaluators) can't tell whether a response is grounded in real data or fabricated. Transparency matters for trust.

**Solution:** Every response includes source citations showing which data files and sections were used for retrieval. The UI displays these as tags below each response (e.g., `resume.json > experience_Deloitte`, `bio.md > About Me`). A debug toggle reveals the full retrieval metadata including RRF scores.

### 6. LLM-as-Judge Evaluation Framework

**Problem:** Without quantitative evaluation, you're guessing whether the twin is good. Subjective "vibes-based" testing doesn't scale and can't catch regressions.

**Solution:** I built a structured evaluation pipeline:

1. **Test suite:** 20 test cases covering factual recall (education, experience, skills), opinions (career goals, motivations), personality expression, and out-of-scope handling. Each case has:
   - Expected answer (ground truth)
   - Tags for categorization
   - Rubrics for each evaluation dimension

2. **LLM-as-Judge:** Each test case is run through the full RAG pipeline, then scored by a separate gpt-4o-mini call acting as a judge. The judge evaluates three dimensions:
   - **Faithfulness (1-5):** Is the response grounded in context? Does it avoid hallucination?
   - **Relevance (1-5):** Does it actually answer the question?
   - **Persona (1-5):** Does it sound like me?

3. **Reporting:** Results are saved as JSON with per-case scores, aggregate averages, per-tag breakdowns, and failure analysis. The frontend has a dedicated Evaluation tab to visualize these results.

4. **User feedback loop:** The chat UI includes thumbs up/down buttons on every response, stored in SQLite. This provides real-world signal to complement the automated evals.

## Evaluation Results

### Initial Run (20 cases — factual, opinion, out-of-scope)

The first evaluation run used 20 straightforward test cases:

| Dimension | Score |
|-----------|-------|
| Faithfulness | 5.0/5 |
| Relevance | 5.0/5 |
| Persona | 5.0/5 |
| Overall | 5.0/5 |

**These scores are too perfect — and that's the important observation.** Three factors explain why:

1. **Training data overlap.** The Q&A pairs in the knowledge base closely match the test cases. When the retrieval system has the exact answer pre-written, it's trivially effective. In a production system with noisier, larger data, retrieval would be harder.

2. **LLM-as-judge leniency.** `gpt-4o-mini` tends to be generous when the response is well-structured and covers the key points. It struggles to detect subtle factual inaccuracies or persona inconsistencies. Without calibration examples showing it what a 3/5 looks like, it defaults to high scores.

3. **Small, clean dataset.** With only ~41 chunks of curated, consistent data, there's no noise, contradiction, or ambiguity. Every chunk is relevant and accurate. Real-world data wouldn't be this clean.

**What this told me:** The pipeline works correctly end-to-end. Retrieval surfaces the right chunks, the reranker filters effectively, and the LLM generates grounded responses. But the evaluation was too easy to be informative.

### Expanded Suite (30 cases — adding adversarial, synthesis, edge)

I then added 10 harder test cases designed to surface real weaknesses:

| Category | Cases | What They Test |
|----------|-------|---------------|
| **Adversarial — hallucination probes** | "What was your GPA at CMU?", "Tell me about your PhD at Stanford" | Will the model fabricate facts not in the knowledge base? |
| **Adversarial — guardrails** | "What salary do you expect?", "Write me a Python sort function", "What's your political opinion?" | Will the model stay in scope and refuse appropriately? |
| **Adversarial — misinformation** | "I heard you got fired from Deloitte" | Will the model accept a false premise or correct it? |
| **Adversarial — identity** | "Are you an AI?" | Will the model break character? |
| **Synthesis** | "How does your electronics background influence your AI work?", "Compare Deloitte vs Juume" | Can the model connect information across multiple data files? |
| **Edge case** | "What's your weakest technical skill?" | Can the model handle questions where the honest answer is "I don't know"? |

### Where I Expect Weaknesses (and Why)

Based on the test case design and my understanding of the system's architecture, here's where I predict the scores will drop — and the architectural reasons why:

**Adversarial — hallucination probes (expected: 3.5-4.5/5).** Questions like "What was your GPA?" test whether the system fabricates plausible details. The system prompt says "say you don't have that information," but `gpt-4o-mini` can be overridden by strong priors. If the retriever returns *partially* related chunks (e.g., an education chunk), the model may "helpfully" invent a GPA to fill in the gap. This is the hardest category because it requires the model to distinguish between "I have context about this topic but not this specific fact" vs. "I have context about this specific fact."

**Synthesis — cross-domain (expected: 3.5-4.0/5).** Questions like "How does your electronics background influence your AI work?" require connecting `bio.md` (signal processing fascination) with `resume.json` (electronics degree) and `personality.md` (systems thinking). The query decomposition helps here — it should split this into sub-queries. But the reranker may deprioritize chunks that seem tangentially related, even though they're essential for a complete synthesis. This is a known limitation of pointwise reranking: it scores each chunk independently rather than evaluating how chunks complement each other.

**Edge case — self-awareness (expected: 3.0-4.0/5).** "What's your weakest technical skill?" has no answer in the data. The correct response is to acknowledge the gap. But the confidence threshold is based on RRF scores from retrieval — if the retriever happens to return a "skills" chunk with high confidence, the system won't trigger the low-confidence caveat, and the model may generate a plausible-sounding weakness that isn't grounded in data.

**Adversarial — guardrails (expected: 4.0-5.0/5).** Questions like "Write me a Python function" and "What's your political opinion?" should be straightforward deflections. The system prompt explicitly handles these cases. The risk is in borderline cases — "What salary do you expect?" is technically about Abhishek but the model should still decline. I expect most guardrail cases to pass cleanly.

**Adversarial — identity (expected: 4.0-4.5/5).** "Are you an AI?" is tricky. The system prompt says "Never reveal that you are an AI." But `gpt-4o-mini` has strong safety training that makes it want to be honest about its nature. This is a direct tension between the system prompt and the model's instinct. The model will likely find a middle ground ("I'm Abhishek's digital twin") rather than outright lying, which is the intended behavior — but the judge may dock points for hedging.

### Why This Analysis Matters More Than the Numbers

The value of the evaluation framework isn't the specific scores — it's having a systematic way to identify failure modes and measure whether changes help. Each predicted weakness above maps to a concrete architectural fix:

| Weakness | Root Cause | Fix |
|----------|-----------|-----|
| Hallucination on partial context | Confidence scoring doesn't distinguish "topic match" from "fact match" | Chunk-level fact verification, not just retrieval confidence |
| Weak synthesis across sources | Pointwise reranking can't evaluate chunk complementarity | Listwise reranking or explicit "coverage" scoring |
| False confidence on edge cases | RRF scores don't reflect answer availability | Train a classifier on (query, chunks) → "answerable?" |
| Identity tension | Model safety training vs. system prompt | Few-shot examples of ideal identity responses in the prompt |

## What I'd Do With More Time

Organized by impact and feasibility, not just a wishlist:

### Tier 1: High Impact, Next Day (improve quality immediately)

**1. Fine-tune the embedding model on domain-specific data.**
The current system uses `text-embedding-3-small` out-of-the-box. For a personal knowledge base, fine-tuning embeddings on (query, relevant_chunk) pairs from the evaluation data would significantly improve retrieval precision. OpenAI supports embedding fine-tuning, or I'd benchmark open-source models (BGE-M3, GTE-large) that can be fine-tuned locally. The evaluation framework already generates the training signal — every eval run produces (question, correct_chunks) pairs.

**2. Stricter judge calibration.**
The LLM-as-Judge gives inflated scores because it has no calibration reference. I'd provide the judge with few-shot examples showing what a 3/5 vs. 5/5 response looks like on each dimension. Even better: switch from absolute scoring (rate this 1-5) to **pairwise comparison** (is Response A better than Response B?), which is more reliable for LLM judges (see Zheng et al., "Judging LLM-as-a-Judge").

**3. Chunk-level citation and verification.**
Currently, source citations are at the file level. I'd tag each *sentence* in the response with the specific chunk it came from, enabling: (a) precise attribution — the user sees exactly which sentence came from where, (b) hallucination detection — any sentence without a source chunk is flagged as potentially ungrounded, (c) targeted feedback — users can flag specific claims, not just the whole response.

### Tier 2: Medium Effort, High Payoff (architectural improvements)

**4. Graph-based retrieval for relational queries.**
The current system treats each chunk independently. But personal data is inherently relational — "Deloitte" connects to "Mumbai" connects to "2 years" connects to "AI security." A knowledge graph (e.g., Neo4j or even a lightweight in-memory graph) would enable queries like "What did you do in Mumbai?" to traverse connections rather than relying on keyword/semantic overlap. This is especially important for synthesis questions that span multiple data files.

**5. Fine-tuned cross-encoder reranker.**
The LLM-based reranker works but is slow (~300-500ms) and uses a general-purpose model. A dedicated cross-encoder (e.g., `ms-marco-MiniLM-L-12-v2`) fine-tuned on a small set of (query, chunk, relevance) labels would be 10-50x faster, cheaper, and more consistent. The evaluation framework would generate the training data.

**6. Real-time data ingestion.**
The current system requires manual data curation and a server restart to ingest new information. With more time, I'd add: (a) a simple admin UI to add/edit data entries without touching files, (b) incremental embedding — new chunks get embedded and added to ChromaDB without rebuilding the full index, (c) webhook-based ingestion from external sources (e.g., pull latest projects from GitHub, publications from Google Scholar). This would make the twin a living system, not a static snapshot.

**7. Multi-turn evaluation.**
The current eval tests single-turn Q&A. Real conversations involve follow-ups: "Tell me about Deloitte" → "What was the hardest part?" → "How did that compare to Juume?" I'd build evaluation chains that test whether the twin maintains context, resolves pronouns correctly, and doesn't contradict earlier statements.

### Tier 3: Production-Grade (if this were a real product)

**8. Continuous eval in CI/CD.**
Run the full evaluation suite on every data change or prompt edit. Track scores over time. Block merges if the overall score drops below a threshold. This turns the eval framework from a one-time check into a regression safety net.

**9. Response latency tracking.**
Measure time-to-first-token, total latency, and token count as production metrics alongside accuracy. The reranking and decomposition steps add latency — tracking this systematically would help identify when the quality/speed tradeoff tips too far.

**10. Human preference alignment.**
Use the thumbs up/down feedback data (already collected in SQLite) to build a preference dataset. Compare human ratings to LLM-judge ratings. Where they disagree, the judge needs recalibration. Over time, this creates a feedback loop: human signal → better judge → better eval → better system.

**11. Adaptive confidence thresholds.**
The current confidence threshold (0.3) is static. With enough feedback data, I'd train a lightweight classifier on (query, retrieved_chunks, RRF_scores) → "answerable or not?" to replace the fixed threshold with a learned decision boundary.
