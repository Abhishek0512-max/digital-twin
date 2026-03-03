# Digital Twin — Abhishek Venkatadri

A digital twin that answers questions as me, grounded in my real background, experience, and personality. Built as a full-stack RAG application with an LLM-as-Judge evaluation framework.

## Architecture

```
User (Browser)
     │
     ▼
┌──────────────────────┐
│    React Chat UI      │  Markdown rendering, streaming,
│    (Vite + TS)        │  source citations, feedback,
│                       │  debug toggle, eval dashboard
└───────────┬──────────┘
            │ SSE stream
            ▼
┌─────────────────────────────────────────────────────┐
│               FastAPI Backend                        │
│                                                      │
│  /chat ──► Query Decomposition (broad queries)      │
│                 │                                    │
│                 ▼                                    │
│            Hybrid Retrieval ──► LLM Rerank          │
│            (Vector + BM25       (gpt-4o-mini)       │
│             + RRF merge)             │              │
│                 │                    ▼              │
│                 ▼               System Prompt       │
│            ChromaDB             + Context           │
│         (text-embedding-              │              │
│          3-small)                     ▼              │
│                              gpt-4o-mini            │
│                              (streaming +           │
│                               source citations)     │
│                                                      │
│  /eval/run ──► Eval Runner ──► LLM-as-Judge        │
│  /feedback ──► SQLite                                │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- An OpenAI API key

### 1. Clone and configure

```bash
git clone <repo-url>
cd digital-twin
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend will:
- Chunk and embed all personal data files on startup
- Store embeddings in a local ChromaDB instance
- Serve the chat API with streaming at `http://localhost:8000`

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Alternative: Docker Compose

```bash
# From the project root:
cp .env.example .env
# Edit .env with your API key
docker-compose up --build
```

Frontend at `http://localhost:3000`, backend at `http://localhost:8000`.

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| LLM | gpt-4o-mini | Cost-effective, fast, sufficient for persona-grounded generation |
| Embeddings | text-embedding-3-small | Good quality-to-cost ratio for semantic search |
| Vector Store | ChromaDB | Local, zero-config, persistent — ideal for reproducibility |
| Backend | FastAPI | Async-native, fast, clean API design with streaming support |
| Frontend | React + Vite + TypeScript | Fast dev cycle, type safety, modern tooling |
| Eval | LLM-as-Judge (gpt-4o-mini) | Scalable automated evaluation without human annotation |

## Project Structure

```
digital-twin/
├── backend/
│   ├── main.py              # FastAPI app with /chat, /feedback, /eval endpoints
│   ├── config.py             # Settings and environment variables
│   ├── models.py             # Pydantic data models
│   ├── rag/
│   │   ├── chunker.py        # Document loading and chunking strategies
│   │   ├── embeddings.py     # OpenAI embeddings + ChromaDB indexing
│   │   └── retriever.py      # Hybrid retrieval (vector + BM25 + RRF)
│   ├── llm/
│   │   ├── client.py         # LLM generation with streaming + reranking
│   │   └── prompts.py        # System prompts and templates
│   ├── eval/
│   │   ├── evaluator.py      # Evaluation runner
│   │   ├── judge.py          # LLM-as-Judge scoring
│   │   └── test_cases.json   # 30 evaluation test cases
│   ├── data/                  # Personal data files
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Main app with chat/eval tabs
│   │   ├── api.ts             # API client with streaming support
│   │   └── components/
│   │       ├── ChatWindow.tsx # Chat interface with suggestions
│   │       ├── MessageBubble.tsx # Message display with feedback
│   │       └── EvalPanel.tsx  # Evaluation dashboard
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── DEEP_DIVE.md               # Response Quality deep-dive write-up
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Stream a chat response (SSE) |
| POST | `/feedback` | Submit thumbs up/down feedback |
| GET | `/feedback/stats` | Get feedback statistics |
| POST | `/eval/run` | Run full evaluation suite |
| GET | `/eval/results` | Get latest evaluation results |
| GET | `/health` | Health check |

## Deep Dive: Response Quality

This project focuses on **Response Quality** as the Phase 2 deep-dive. Key features:

| Feature | What It Does |
|---------|-------------|
| **Hybrid Retrieval** | Combines vector search (ChromaDB) with BM25 keyword search via Reciprocal Rank Fusion |
| **LLM Reranking** | Second gpt-4o-mini pass to score and filter chunks by relevance |
| **Query Decomposition** | Broad questions ("Tell me about yourself") are split into focused sub-queries for better recall |
| **Confidence Guardrails** | Low-confidence caveat prefix, out-of-scope deflection |
| **Source Citations** | Every response shows which data files were used, with a debug toggle for full retrieval metadata |
| **LLM-as-Judge Eval** | 30-case evaluation suite scoring faithfulness, relevance, and persona consistency |
| **User Feedback** | Thumbs up/down on every response, stored in SQLite |
| **Eval Dashboard** | Visual frontend to run evaluations and inspect per-question results |

See [DEEP_DIVE.md](DEEP_DIVE.md) for full technical write-up, evaluation results, tradeoff analysis, and future improvements.

## Data Sources

All data is curated in `backend/data/`:
- `bio.md` — Background, communication style, career goals
- `resume.json` — Structured education, experience, skills
- `projects.md` — Detailed project descriptions
- `personality.md` — Personality traits, values, interests
- `qa_pairs.json` — 18 curated Q&A pairs (also serve as eval ground truth)
