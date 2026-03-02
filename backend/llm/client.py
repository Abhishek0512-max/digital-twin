import json
from typing import AsyncGenerator

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, CHAT_MODEL, RERANK_TOP_K, CONFIDENCE_THRESHOLD
from llm.prompts import (
    SYSTEM_PROMPT, RERANK_PROMPT, DECOMPOSE_PROMPT, CONTEXTUAL_REWRITE_PROMPT,
    CONFIDENCE_CAVEAT, OUT_OF_SCOPE_RESPONSE, BROAD_QUERY_PATTERNS,
)
from rag.retriever import hybrid_retrieve, assess_confidence
from models import Chunk

_aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

_conversations: dict[str, list[dict]] = {}


def _is_broad_query(message: str) -> bool:
    lower = message.lower().strip().rstrip("?.!")
    return any(pattern in lower for pattern in BROAD_QUERY_PATTERNS)


async def _rewrite_with_context(message: str, conversation_id: str | None) -> str:
    """Rewrite a follow-up question using conversation history for context."""
    if not conversation_id or conversation_id not in _conversations:
        return message

    history = _conversations[conversation_id][-6:]
    if not history:
        return message

    short_words = message.lower().split()
    follow_up_signals = ["that", "this", "it", "them", "there", "more", "else", "also", "too"]
    is_likely_followup = (
        len(short_words) < 10
        or any(w in short_words[:4] for w in follow_up_signals)
        or message.lower().startswith(("what about", "how about", "and ", "tell me more", "expand"))
    )

    if not is_likely_followup:
        return message

    history_str = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Abhishek'}: {m['content'][:200]}"
        for m in history
    )

    try:
        response = await _aclient.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{
                "role": "user",
                "content": CONTEXTUAL_REWRITE_PROMPT.format(history=history_str, message=message),
            }],
            temperature=0,
            max_tokens=150,
        )
        rewritten = response.choices[0].message.content or message
        return rewritten.strip().strip('"')
    except Exception:
        return message


async def decompose_query(question: str) -> list[str]:
    """Break a broad question into focused sub-queries for better retrieval."""
    try:
        response = await _aclient.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{
                "role": "user",
                "content": DECOMPOSE_PROMPT.format(question=question),
            }],
            temperature=0,
            max_tokens=300,
        )
        content = response.choices[0].message.content or "[]"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return [question]


async def rerank_chunks(question: str, chunks: list[Chunk]) -> list[Chunk]:
    """Use LLM to rerank chunks by relevance."""
    if len(chunks) <= RERANK_TOP_K:
        return chunks

    chunk_text = "\n\n".join(
        f"[{i}] {c.text[:300]}" for i, c in enumerate(chunks)
    )

    response = await _aclient.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{
            "role": "user",
            "content": RERANK_PROMPT.format(question=question, chunks=chunk_text),
        }],
        temperature=0,
        max_tokens=500,
    )

    try:
        scores = json.loads(response.choices[0].message.content)
        scored = [(s["index"], s["score"]) for s in scores if "index" in s and "score" in s]
        scored.sort(key=lambda x: x[1], reverse=True)
        reranked = [chunks[s[0]] for s in scored[:RERANK_TOP_K] if s[0] < len(chunks)]
        return reranked if reranked else chunks[:RERANK_TOP_K]
    except (json.JSONDecodeError, KeyError, IndexError):
        return chunks[:RERANK_TOP_K]


def _build_context(chunks: list[Chunk]) -> str:
    parts = []
    for chunk in chunks:
        source_label = f"[{chunk.source}"
        if chunk.section:
            source_label += f" > {chunk.section}"
        source_label += "]"
        parts.append(f"{source_label}\n{chunk.text}")
    return "\n\n---\n\n".join(parts)


def _extract_sources(chunks: list[Chunk]) -> list[dict]:
    """Extract unique source citations from chunks."""
    seen = set()
    sources = []
    for chunk in chunks:
        label = chunk.source
        if chunk.section:
            label += f" > {chunk.section}"
        if label not in seen:
            seen.add(label)
            sources.append({
                "file": chunk.source,
                "section": chunk.section,
                "score": round(chunk.score, 4),
            })
    return sources


async def _retrieve_with_decomposition(message: str) -> list[Chunk]:
    """For broad queries, decompose into sub-queries and merge results."""
    if _is_broad_query(message):
        sub_queries = await decompose_query(message)
        all_chunks: dict[str, Chunk] = {}
        for sq in sub_queries:
            for chunk in hybrid_retrieve(sq):
                key = chunk.text[:100]
                if key not in all_chunks or chunk.score > all_chunks[key].score:
                    all_chunks[key] = chunk
        chunks = sorted(all_chunks.values(), key=lambda c: c.score, reverse=True)
        return chunks[:RERANK_TOP_K * 2]
    else:
        return hybrid_retrieve(message)


async def generate_response(
    message: str,
    conversation_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Retrieve context, build prompt, and stream a response."""
    retrieval_query = await _rewrite_with_context(message, conversation_id)

    chunks = await _retrieve_with_decomposition(retrieval_query)
    confidence = assess_confidence(chunks)

    reranked = await rerank_chunks(retrieval_query, chunks)
    sources = _extract_sources(reranked)
    context = _build_context(reranked)
    system = SYSTEM_PROMPT.format(context=context)

    history = []
    if conversation_id and conversation_id in _conversations:
        history = _conversations[conversation_id][-10:]

    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    if confidence < CONFIDENCE_THRESHOLD and not reranked:
        yield json.dumps({"type": "sources", "sources": []})
        yield OUT_OF_SCOPE_RESPONSE
        return

    prefix = CONFIDENCE_CAVEAT if confidence < CONFIDENCE_THRESHOLD else ""

    yield json.dumps({"type": "sources", "sources": sources})

    stream = await _aclient.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=800,
        stream=True,
    )

    full_response = prefix
    if prefix:
        yield prefix

    async for event in stream:
        delta = event.choices[0].delta
        if delta.content:
            full_response += delta.content
            yield delta.content

    if conversation_id:
        if conversation_id not in _conversations:
            _conversations[conversation_id] = []
        _conversations[conversation_id].append({"role": "user", "content": message})
        _conversations[conversation_id].append({"role": "assistant", "content": full_response})


async def generate_response_sync(message: str) -> tuple[str, list[str]]:
    """Non-streaming version for evaluation. Returns (response, chunk_texts)."""
    chunks = await _retrieve_with_decomposition(message)
    reranked = await rerank_chunks(message, chunks)
    context = _build_context(reranked)
    system = SYSTEM_PROMPT.format(context=context)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]

    response = await _aclient.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=800,
    )

    answer = response.choices[0].message.content or ""
    chunk_texts = [c.text for c in reranked]
    return answer, chunk_texts
