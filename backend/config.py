import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
JUDGE_MODEL = "gpt-4o-mini"

DATA_DIR = Path(__file__).parent / "data"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
EVAL_DIR = Path(__file__).parent / "eval"

CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
RETRIEVAL_TOP_K = 8
RERANK_TOP_K = 5

CONFIDENCE_THRESHOLD = 0.3
