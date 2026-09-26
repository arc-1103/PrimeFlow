# ENV_VARS.md
## Streaming Live RAG — Environment Variable Reference

Single source of truth for every environment variable the app reads. Keep this file and
`.env.example` in sync — if you add a variable your track needs, add it here in the same PR,
per `AGENTS.md` §6 ("Never commit secrets... `.env.example` with placeholder values only").

Every teammate pulls config through `app/config.py` (Pydantic Settings) — never read
`os.environ` directly in a module. That keeps this table authoritative.

---

## App / Server

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `APP_ENV` | `dev` | No | infra | `dev` \| `test` \| `demo`. Gates some verbose logging. |
| `HOST` | `0.0.0.0` | No | infra | FastAPI bind host. |
| `PORT` | `8000` | No | infra | FastAPI/WebSocket/SSE port — must match `frontend/index.html`'s connection URL. |
| `LOG_LEVEL` | `INFO` | No | infra | Python `logging` level. Use `DEBUG` while building the controller (Track B). |

## LLM / Synthesis (Track C)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `LLM_PROVIDER` | `openai` | No | P3 | `openai` \| `ollama`. Selects the client the OpenAI-compatible wrapper talks to. |
| `OPENAI_API_KEY` | *(none)* | **Yes, if provider=openai** | P3 | Secret. Never commit. Goes in `.env` only. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | No | P3 | Override to point the same client at Ollama/llama.cpp's OpenAI-compatible endpoint. |
| `LLM_MODEL` | `gpt-4o-mini` | No | P3 | Model used for answer synthesis (`synthesis/generator.py`). |
| `LLM_MAX_TOKENS` | `800` | No | P3 | Cap per synthesis call — also feeds telemetry token-cost estimates (G6). |
| `LLM_TIMEOUT_SECONDS` | `20` | No | P3 | Synthesis call timeout. |
| `LLM_FALLBACK_MODEL` | *(same as `LLM_MODEL`)* | No | P2 | Used only if `CONTROLLER_LLM_FALLBACK_ENABLED=true` for ambiguous WAIT/RETRIEVE cases. |

## Local LLM path (optional — cut first per PHASE_0_PLAN.md §7 if time runs short)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Only if `LLM_PROVIDER=ollama` | P3 | Local Ollama server, OpenAI-compatible route. |
| `OLLAMA_MODEL` | `llama3` | Only if `LLM_PROVIDER=ollama` | P3 | Local model tag. |

## Embeddings & Retrieval (Track A)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | No | P1 | Dense embedding model. Keep small — no GPU assumed. |
| `EMBEDDING_DEVICE` | `cpu` | No | P1 | `cpu` \| `cuda`. |
| `FAISS_INDEX_PATH` | `indexes/faiss.index` | No | P1 | Rebuilt by `scripts/ingest.py` — never hand-edited (`CLAUDE.md`). |
| `BM25_INDEX_PATH` | `indexes/bm25.pkl` | No | P1 | Same reproducibility rule as above. |
| `CHUNKS_PATH` | `data/chunks.jsonl` | No | P1 | Must exist and be referenced by every citation — see `AGENTS.md` §2 grounding rule. |
| `TOP_K_DENSE` | `10` | No | P1 | Dense candidates before fusion. |
| `TOP_K_SPARSE` | `10` | No | P1 | BM25 candidates before fusion. |
| `RRF_K` | `60` | No | P1 | Standard Reciprocal Rank Fusion constant. |

## Corpus / Data Paths (Track A, consumed everywhere)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `CORPUS_DIR` | `corpus/` | No | P1 | Raw source documents (PyMuPDF/python-docx input). |
| `DATA_DIR` | `data/` | No | P1 | Processed chunk store. |
| `INDEXES_DIR` | `indexes/` | No | P1 | FAISS + BM25 artifacts. |

## Controller (Track B)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `CONTROLLER_MIN_TOKENS` | `6` | No | P2 | Minimum stable-token window before RETRIEVE is eligible — tune against G2's 80% target. |
| `CONTROLLER_STABILITY_WINDOW_MS` | `400` | No | P2 | How long intent must hold stable before firing. |
| `CONTROLLER_LLM_FALLBACK_ENABLED` | `false` | No | P2 | Turn on only for genuinely ambiguous cases — see PHASE_0_PLAN.md §5 risk #1. |

## Streaming (Track B)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `STREAM_CHUNK_INTERVAL_MS` | `800` | No | P2 | Simulated transcript chunk cadence (`streaming/simulator.py`). |

## Session Store (Track C)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `SESSION_DB_PATH` | `data/sessions.db` | No | P3 | SQLite file. Must never leak state across `session_id`s (unit-tested per `AGENTS.md` §2). |
| `SESSION_TTL_SECONDS` | `3600` | No | P3 | Session expiry — enforces the "session-bound state only" hard constraint. |

## Telemetry (Track D)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `TELEMETRY_LOG_PATH` | `logs/events.jsonl` | No | P4 | Structured JSON log sink — must give 100% trace coverage for G6. |
| `TELEMETRY_LOG_FORMAT` | `json` | No | P4 | Keep as `json`; don't swap for a custom format. |

## Evaluation (Track D)

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `EVAL_FIXTURES_DIR` | `app/evaluation/fixtures/` | No | P4 | Synthetic streaming scenarios for `run_eval.py`. |
| `EVAL_G2_TARGET` | `0.80` | No | P4 | Early-retrieval threshold (CHALLENGE_BREAKDOWN.md §F). |
| `EVAL_G3_TARGET` | `0.70` | No | P4 | Multi-intent identification threshold. |
| `EVAL_G4_TARGET` | `0.85` | No | P4 | Citation-support threshold. |

## Docker / Compose

| Variable | Default | Required | Owner | Description |
|---|---|---|---|---|
| `COMPOSE_PROJECT_NAME` | `streaming-live-rag` | No | infra | Namespacing for `docker compose up` (G1). |

---

## `.env.example` (commit this; never commit the real `.env`)

```bash
# App
APP_ENV=dev
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# LLM / Synthesis
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-REPLACE_ME
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SECONDS=20
LLM_FALLBACK_MODEL=gpt-4o-mini

# Local LLM (optional)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3

# Embeddings & Retrieval
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
FAISS_INDEX_PATH=indexes/faiss.index
BM25_INDEX_PATH=indexes/bm25.pkl
CHUNKS_PATH=data/chunks.jsonl
TOP_K_DENSE=10
TOP_K_SPARSE=10
RRF_K=60

# Corpus / Data
CORPUS_DIR=corpus/
DATA_DIR=data/
INDEXES_DIR=indexes/

# Controller
CONTROLLER_MIN_TOKENS=6
CONTROLLER_STABILITY_WINDOW_MS=400
CONTROLLER_LLM_FALLBACK_ENABLED=false

# Streaming
STREAM_CHUNK_INTERVAL_MS=800

# Session
SESSION_DB_PATH=data/sessions.db
SESSION_TTL_SECONDS=3600

# Telemetry
TELEMETRY_LOG_PATH=logs/events.jsonl
TELEMETRY_LOG_FORMAT=json

# Evaluation
EVAL_FIXTURES_DIR=app/evaluation/fixtures/
EVAL_G2_TARGET=0.80
EVAL_G3_TARGET=0.70
EVAL_G4_TARGET=0.85

# Docker
COMPOSE_PROJECT_NAME=streaming-live-rag
```

## Rules for adding a new variable

1. Add it to this table **and** `.env.example` in the same PR — one without the other drifts.
2. If it's a secret (API key, token), it goes in `.env` only, never in `.env.example` beyond a placeholder.
3. Read it through `app/config.py`, not `os.environ` inline — keeps `pytest` able to override config cleanly.
4. If it changes a gate threshold (`EVAL_G*_TARGET`), flag it in `docs/HACKATHON_STATUS.md` — a silent threshold change invalidates prior gate results.
