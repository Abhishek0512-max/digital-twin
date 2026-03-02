# Deep Dive: Response Quality

## Why I Chose This

Response quality is the core differentiator for a digital twin. Without it, you just have a chatbot with a custom system prompt. The twin needs to:
1. Accurately represent me (faithfulness)
2. Actually answer what's asked (relevance)
3. Sound like me, not a generic AI (persona consistency)

I chose this deep-dive because it sits at the intersection of retrieval engineering, prompt design, and evaluation methodology — areas I find most technically interesting and where measurable improvement is possible.

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

Running the full 20-case evaluation suite produced the following results:

| Dimension | Score |
|-----------|-------|
| Faithfulness | 5.0/5 |
| Relevance | 5.0/5 |
| Persona | 5.0/5 |
| Overall | 5.0/5 |

All categories (factual, opinion, out_of_scope, etc.) scored 5.0/5.

### Honest Analysis of These Results

**The scores are too high** — and that's an important observation. Several factors contribute:

1. **Training data overlap:** The Q&A pairs in the knowledge base closely match the test cases, making retrieval trivially effective. In a production system with noisier, larger data, retrieval would be harder.

2. **LLM-as-judge leniency:** gpt-4o-mini tends to be generous when the response is well-structured and covers the key points. It has difficulty detecting subtle factual inaccuracies or persona inconsistencies.

3. **Small, clean dataset:** With only 41 chunks of curated data, there's minimal noise or contradiction. Real-world data would be messier.

**What this tells me:** The pipeline works correctly end-to-end — retrieval surfaces the right chunks, the reranker filters effectively, and the LLM generates grounded responses. But the evaluation needs harder test cases to be truly informative:
- Adversarial questions that probe for hallucination ("What was your GPA at CMU?")
- Edge cases where context is ambiguous
- Questions requiring synthesis across multiple sources
- Questions with intentional misinformation to test correction behavior

## What I'd Do With More Time

1. **Harder evaluation suite:** Add adversarial, edge-case, and multi-hop questions. Include questions where the correct answer is "I don't know" to test hallucination resistance.

2. **Stricter judge calibration:** Provide the judge with calibration examples — show it what a 3/5 vs. 5/5 response looks like. Or use pairwise comparison (is Response A better than Response B?) instead of absolute scoring.

3. **Chunk-level citation:** Tag each sentence in the response with which chunk it came from. This enables transparent attribution and makes hallucination detection more precise.

4. **Fine-tuned cross-encoder reranker:** Replace the LLM-based reranker with a fine-tuned ms-marco model for faster, cheaper, more consistent reranking.

5. **Embedding model comparison:** Benchmark text-embedding-3-small vs. text-embedding-3-large vs. open-source models (e.g., BGE, GTE) on this specific dataset to find the best quality/cost tradeoff.

6. **Continuous eval pipeline:** Run evals on every data change or prompt edit. Track scores over time to catch regressions. Add a CI step that blocks merges if overall score drops below a threshold.

7. **Human-in-the-loop evaluation:** Use the feedback data (thumbs up/down) to build a human preference dataset. Compare human ratings to LLM-judge ratings to calibrate the automated system.

8. **Multi-turn evaluation:** The current eval tests single-turn Q&A. A more complete evaluation would test multi-turn conversations where context from earlier messages matters.

9. **Response latency tracking:** Measure time-to-first-token, total latency, and token count as production quality metrics alongside accuracy.
