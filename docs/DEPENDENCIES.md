# DEPENDENCIES.md
## One-line justification per dependency (AGENTS.md SS3 / SS6)

| Dependency | Justification |
|---|---|
| fastapi | API/streaming server + WebSocket/SSE, async-native (AGENTS.md SS3 table) |
| uvicorn | ASGI server to run FastAPI |
| pydantic | Shared cross-module schemas (app/schemas.py) |
| pydantic-settings | Typed config from env vars, no raw `os.environ` reads (AGENTS.md SS5, ENV_VARS.md) |
| pymupdf | PDF parsing for ingestion — mandated, do not hand-roll (AGENTS.md SS3) |
| python-docx | DOCX parsing for ingestion — mandated (AGENTS.md SS3) |
| sentence-transformers | Dense embeddings for retrieval — mandated (AGENTS.md SS3) |
| faiss-cpu | In-process vector index, no extra container — mandated (AGENTS.md SS3) |
| rank_bm25 | Sparse/BM25 retrieval — mandated (AGENTS.md SS3) |
| numpy | Vector math glue for embeddings/FAISS |
| pytest | Test runner — mandated (AGENTS.md SS3) |
| httpx | FastAPI TestClient transport for API tests |
