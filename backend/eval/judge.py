import json
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, JUDGE_MODEL
from models import EvalResult

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

JUDGE_PROMPT = """You are an evaluation judge for a digital twin system. The digital twin is supposed to respond as a specific person (Abhishek Venkatadri) based on provided context.

Evaluate the following response on three dimensions, each scored 1-5:

1. **Faithfulness** (1-5): Is the response grounded in the provided context? Does it avoid hallucination? Does it match the expected answer's key facts?
   - Rubric: {faithfulness_rubric}

2. **Relevance** (1-5): Does the response actually answer the question asked? Is it on-topic and complete?
   - Rubric: {relevance_rubric}

3. **Persona** (1-5): Does the response sound like the person described? Does it match the expected communication style (structured, concise, analytical, first person)?
   - Rubric: {persona_rubric}

## Input
**Question:** {question}
**Expected Answer:** {expected_answer}
**Actual Response:** {actual_answer}
**Retrieved Context Used:**
{context}

## Output
Return ONLY a JSON object with this exact structure:
{{
  "faithfulness": <1-5>,
  "relevance": <1-5>,
  "persona": <1-5>,
  "overall": <1-5>,
  "reasoning": "<brief explanation of scores>"
}}
"""


async def judge_response(
    question: str,
    expected_answer: str,
    actual_answer: str,
    retrieved_chunks: list[str],
    rubric: dict | None = None,
) -> EvalResult:
    """Use LLM-as-judge to evaluate a twin response."""
    rubric = rubric or {}
    context_str = "\n---\n".join(retrieved_chunks[:5]) if retrieved_chunks else "(no context retrieved)"

    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_answer=expected_answer,
        actual_answer=actual_answer,
        context=context_str,
        faithfulness_rubric=rubric.get("faithfulness", "Check factual accuracy"),
        relevance_rubric="Does it answer the question?",
        persona_rubric=rubric.get("persona", "Should respond as Abhishek in first person"),
    )

    response = await _client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=500,
    )

    try:
        content = response.choices[0].message.content or "{}"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        scores = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        scores = {"faithfulness": 0, "relevance": 0, "persona": 0, "overall": 0, "reasoning": "Judge failed to parse"}

    return EvalResult(
        question=question,
        expected_answer=expected_answer,
        actual_answer=actual_answer,
        retrieved_chunks=retrieved_chunks,
        faithfulness=scores.get("faithfulness", 0),
        relevance=scores.get("relevance", 0),
        persona=scores.get("persona", 0),
        overall=scores.get("overall", 0),
        judge_reasoning=scores.get("reasoning", ""),
    )
