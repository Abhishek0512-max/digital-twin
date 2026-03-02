import asyncio
import json
from datetime import datetime
from pathlib import Path

from eval.judge import judge_response
from llm.client import generate_response_sync
from models import EvalResult
from config import EVAL_DIR

RESULTS_DIR = EVAL_DIR / "results"


async def run_single_eval(test_case: dict) -> EvalResult:
    """Run a single evaluation test case."""
    question = test_case["question"]
    expected = test_case["expected_answer"]
    rubric = test_case.get("rubric", {})

    actual_answer, chunks = await generate_response_sync(question)

    result = await judge_response(
        question=question,
        expected_answer=expected,
        actual_answer=actual_answer,
        retrieved_chunks=chunks,
        rubric=rubric,
    )
    return result


async def run_full_eval(test_cases_path: str | None = None) -> dict:
    """Run evaluation over all test cases and save results."""
    if test_cases_path is None:
        test_cases_path = str(EVAL_DIR / "test_cases.json")

    with open(test_cases_path) as f:
        test_cases = json.load(f)

    results: list[EvalResult] = []
    for i, tc in enumerate(test_cases):
        print(f"  Evaluating [{i+1}/{len(test_cases)}]: {tc['question'][:60]}...")
        result = await run_single_eval(tc)
        results.append(result)

    total = len(results)
    avg_faithfulness = sum(r.faithfulness for r in results) / max(total, 1)
    avg_relevance = sum(r.relevance for r in results) / max(total, 1)
    avg_persona = sum(r.persona for r in results) / max(total, 1)
    avg_overall = sum(r.overall for r in results) / max(total, 1)

    by_tag: dict[str, list[float]] = {}
    for tc, result in zip(test_cases, results):
        for tag in tc.get("tags", []):
            by_tag.setdefault(tag, []).append(result.overall)

    tag_averages = {tag: sum(scores) / len(scores) for tag, scores in by_tag.items()}

    failures = [
        {"question": r.question, "score": r.overall, "reasoning": r.judge_reasoning}
        for r in results
        if r.overall <= 2
    ]

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": total,
        "averages": {
            "faithfulness": round(avg_faithfulness, 2),
            "relevance": round(avg_relevance, 2),
            "persona": round(avg_persona, 2),
            "overall": round(avg_overall, 2),
        },
        "tag_averages": {k: round(v, 2) for k, v in tag_averages.items()},
        "failures": failures,
        "detailed_results": [r.model_dump() for r in results],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"eval_{timestamp}.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  EVALUATION REPORT")
    print(f"{'='*60}")
    print(f"  Total test cases: {total}")
    print(f"  Faithfulness:     {avg_faithfulness:.2f}/5")
    print(f"  Relevance:        {avg_relevance:.2f}/5")
    print(f"  Persona:          {avg_persona:.2f}/5")
    print(f"  Overall:          {avg_overall:.2f}/5")
    print(f"{'='*60}")
    if tag_averages:
        print(f"  Scores by tag:")
        for tag, avg in sorted(tag_averages.items()):
            print(f"    {tag:20s} {avg:.2f}/5")
    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for f_item in failures:
            print(f"    - {f_item['question'][:50]}... (score: {f_item['score']})")
    print(f"\n  Results saved to: {output_path}")

    return report
