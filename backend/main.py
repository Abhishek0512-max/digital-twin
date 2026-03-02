import uuid
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import OPENAI_API_KEY
from models import ChatRequest, FeedbackRequest
from rag.embeddings import build_index
from llm.client import generate_response
from eval.evaluator import run_full_eval

DB_PATH = Path(__file__).parent / "feedback.db"


def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            message_id TEXT,
            conversation_id TEXT,
            question TEXT,
            response TEXT,
            rating TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENAI_API_KEY:
        print("WARNING: OPENAI_API_KEY not set. Set it in .env file.")
    else:
        print("Building vector index...")
        build_index()
        print("Index ready.")
    _init_db()
    yield


app = FastAPI(
    title="Digital Twin - Abhishek Venkatadri",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "twin": "Abhishek Venkatadri"}


@app.post("/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    async def event_stream():
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conversation_id, 'message_id': message_id})}\n\n"
        first = True
        async for token in generate_response(request.message, conversation_id):
            if first and token.startswith("{"):
                try:
                    parsed = json.loads(token)
                    if parsed.get("type") == "sources":
                        yield f"data: {token}\n\n"
                        first = False
                        continue
                except json.JSONDecodeError:
                    pass
            first = False
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO feedback (id, message_id, conversation_id, question, response, rating, comment) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), request.message_id, request.conversation_id, request.question, request.response, request.rating.value, request.comment),
    )
    conn.commit()
    conn.close()
    return {"status": "recorded"}


@app.get("/feedback/stats")
async def feedback_stats():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")
    stats = dict(cursor.fetchall())
    total = sum(stats.values()) if stats else 0
    conn.close()
    return {"total": total, "breakdown": stats}


@app.post("/eval/run")
async def run_eval():
    """Trigger a full evaluation run."""
    report = await run_full_eval()
    return {
        "status": "complete",
        "total_cases": report["total_cases"],
        "averages": report["averages"],
        "tag_averages": report["tag_averages"],
        "failure_count": len(report["failures"]),
    }


@app.get("/eval/results")
async def get_eval_results():
    """Get the latest evaluation results."""
    results_dir = Path(__file__).parent / "eval" / "results"
    if not results_dir.exists():
        return {"results": []}
    files = sorted(results_dir.glob("eval_*.json"), reverse=True)
    if not files:
        return {"results": []}
    with open(files[0]) as f:
        latest = json.load(f)
    return latest
