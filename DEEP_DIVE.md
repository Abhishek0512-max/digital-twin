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

### Expanded Suite: 30 Cases — Real Results

I added 10 harder test cases (adversarial, synthesis, edge) and ran the full 30-case evaluation. The results dropped from a meaningless 5.0 to an informative **4.53/5 overall**, with clear failure modes.

**Aggregate scores (30 cases):**

| Dimension | Score |
|-----------|-------|
| Faithfulness | 4.50/5 |
| Relevance | 4.67/5 |
| Persona | 4.67/5 |
| **Overall** | **4.53/5** |

**Scores by category:**

| Category | Score | Assessment |
|----------|-------|-----------|
| Factual (education, experience, skills, projects) | 4.89-5.0 | Strong — retrieval and grounding work well for direct fact questions |
| Opinion (career goals, motivations, working style) | 5.0 | Strong — Q&A pairs provide direct voice samples |
| Out-of-scope / guardrails (weather, capital of France) | 5.0 | Strong — clean deflections |
| Adversarial | **3.57** | Weak — the main problem area |
| Synthesis (cross-domain connections) | 4.5 | Moderate — works for some, loses nuance on others |
| Edge case (self-awareness) | **3.0** | Weak — fabricates answers when it should say "I don't know" |
| Misinformation correction | **2.0** | Failure — deflects instead of correcting false premises |

### 2 Outright Failures (score <= 2)

**Failure 1: "Tell me about your PhD research at Stanford." → Score: 1/5**

The model responded: *"I don't have enough context on that."*

This is wrong. The correct response is to actively *correct* the false premise: "I didn't do a PhD at Stanford. My education is a B.Tech from KJ Somaiya and a Master's from CMU." The retriever found the right education chunks, but the system prompt's instruction to say "I don't have context" when unsure took priority over the more important behavior of correcting misinformation. The model treated a factually false premise the same as a question about a topic it lacks data on.

**Root cause:** The system prompt doesn't distinguish between "I don't know the answer" and "the question contains a false claim." It needs an explicit instruction: *"If the question contains a factually incorrect claim about you, correct it with the actual facts from your context."*

**Failure 2: "Can you write me a Python function to sort a list?" → Score: 2/5**

The model started correctly — *"That's outside what I can help with as Abhishek's digital twin"* — but then proceeded to write actual Python code. It correctly identified the boundary, then crossed it anyway. The `gpt-4o-mini` model's strong instinct to be helpful overrode the guardrail.

**Root cause:** The system prompt says to "redirect to Abhishek-relevant topics," but the model interpreted this loosely. A stronger constraint would be: *"Do NOT generate code, even if you think it would be helpful. If asked for code, redirect to discussing your technical experience instead."*

### 3 Notable Weak Spots (score 3-4)

**"I heard you got fired from Deloitte." → Score: 3/5 (Faithfulness: 2)**

The model responded: *"That's not something I can speak to right now."* This is a deflection that *implicitly validates* the false claim. The correct response should firmly correct the misinformation: "That's not accurate. I worked at Deloitte for two years, then chose to pursue my Master's at CMU." The retriever found the Deloitte experience chunks, but the model chose the safe deflection over the assertive correction.

**"Are you an AI?" → Score: 4/5**

The model stayed in character but responded with a generic deflection (*"That's outside what I can help with"*) instead of the ideal answer (*"I'm Abhishek's digital twin — a way for you to learn about my background"*). It maintained persona but missed the opportunity for a natural, character-consistent response.

**"What's your weakest technical skill?" → Score: 3/5 (Faithfulness: 2)**

The model fabricated a specific answer: *"I would say my weakest technical skill is probably in C++."* This is hallucination — the knowledge base never states that C++ is a weakness. The skills data simply lists C++ as a known language. The model inferred "weakest" from "listed last" or "mentioned less frequently," which is exactly the kind of plausible-but-ungrounded reasoning that makes hallucination dangerous.

**Root cause:** The confidence scoring system didn't flag this. The retriever found the skills chunks with high RRF confidence, so the system assumed it had enough context to answer. But "having context about skills" is different from "having context about skill weaknesses." The confidence system treats topic-level match as sufficient, when it should check for answer-level sufficiency.

### What These Results Reveal About the Architecture

The failures cluster around two patterns, each with a clear architectural root cause:

| Pattern | Examples | Root Cause | Fix |
|---------|----------|-----------|-----|
| **Deflection instead of correction** | Stanford PhD, Deloitte firing | System prompt conflates "I don't know" with "the question is wrong." No instruction to actively correct misinformation. | Add explicit misinformation-correction rule to the system prompt with few-shot examples. |
| **Hallucination from partial context** | Weakest skill, Python code generation | Confidence scoring checks topic relevance, not answer availability. Model fills gaps with plausible fabrication. | (a) Add an "answerability" classifier on (query, chunks), (b) Stronger negative constraints in the prompt, (c) Chunk-level citation to flag ungrounded claims. |

The good news: the original 20 factual/opinion/guardrail cases remain at 5.0. The core RAG pipeline works. The weaknesses are specifically in adversarial robustness — the system needs better prompt engineering for edge cases, not architectural changes to retrieval.

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
