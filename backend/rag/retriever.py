import re
import math
from collections import defaultdict

from rag.embeddings import get_embeddings, get_collection
from models import Chunk
from config import RETRIEVAL_TOP_K, RERANK_TOP_K, CONFIDENCE_THRESHOLD


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_dl: float, k1: float = 1.5, b: float = 0.75) -> float:
    """Simple single-document BM25 score (without IDF for simplicity)."""
    dl = len(doc_tokens)
    score = 0.0
    tf_map = defaultdict(int)
    for t in doc_tokens:
        tf_map[t] += 1
    for qt in query_tokens:
        tf = tf_map.get(qt, 0)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * dl / max(avg_dl, 1))
        score += numerator / denominator if denominator > 0 else 0
    return score


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def hybrid_retrieve(query: str, top_k: int = RETRIEVAL_TOP_K) -> list[Chunk]:
    """Combine vector search with BM25 keyword search using Reciprocal Rank Fusion."""
    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = get_embeddings([query])[0]
    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k * 2, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    all_docs = collection.get(include=["documents", "metadatas"])

    query_tokens = _tokenize(query)
    all_doc_tokens = [_tokenize(doc) for doc in all_docs["documents"]]
    avg_dl = sum(len(dt) for dt in all_doc_tokens) / max(len(all_doc_tokens), 1)

    bm25_scores = []
    for i, doc_tokens in enumerate(all_doc_tokens):
        score = _bm25_score(query_tokens, doc_tokens, avg_dl)
        bm25_scores.append((i, score))

    bm25_scores.sort(key=lambda x: x[1], reverse=True)
    bm25_top = bm25_scores[: top_k * 2]

    rrf_scores: dict[str, float] = defaultdict(float)
    doc_map: dict[str, dict] = {}
    k = 60  # RRF constant

    for rank, (doc_id, doc, meta, dist) in enumerate(zip(
        vector_results["ids"][0],
        vector_results["documents"][0],
        vector_results["metadatas"][0],
        vector_results["distances"][0],
    )):
        rrf_scores[doc_id] += 1.0 / (k + rank + 1)
        doc_map[doc_id] = {"text": doc, "source": meta["source"], "section": meta.get("section", ""), "vector_dist": dist}

    for rank, (idx, _score) in enumerate(bm25_top):
        doc_id = all_docs["ids"][idx]
        rrf_scores[doc_id] += 1.0 / (k + rank + 1)
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "text": all_docs["documents"][idx],
                "source": all_docs["metadatas"][idx]["source"],
                "section": all_docs["metadatas"][idx].get("section", ""),
                "vector_dist": 1.0,
            }

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]

    chunks = []
    for doc_id in sorted_ids:
        info = doc_map[doc_id]
        chunks.append(Chunk(
            text=info["text"],
            source=info["source"],
            section=info["section"],
            score=rrf_scores[doc_id],
        ))

    return chunks


def assess_confidence(chunks: list[Chunk]) -> float:
    """Return a confidence score [0, 1] based on retrieval quality."""
    if not chunks:
        return 0.0
    top_score = chunks[0].score
    max_possible = 1.0 / 61 + 1.0 / 61  # best possible RRF rank 0 from both
    return min(top_score / max_possible, 1.0)
