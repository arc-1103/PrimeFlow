# ARCHITECTURE.md
## Streaming Live RAG — System Architecture

Living document. Each track owner fills in their section as their module lands
(AGENTS.md SS6 / TEAM_SPLIT.md SS6). Do not let this drift from the code.

## Pipeline

```
Transcript stream (chunk@0.0s -> chunk@0.8s -> chunk@1.6s -> [end]@2.1s)
        |
        v
[1] Retrieval Controller       -- intent stability check -> WAIT | RETRIEVE | NO_RETRIEVAL
        | (on RETRIEVE)
        v
[2] Multi-Intent Decomposer    -- split into sub-queries, route in parallel
        |
        v
[3] Corpus Retrieval & Fusion  -- dense + sparse hybrid search -> rerank -> dedupe
        |
        v
[4] Session-Aware Synthesis    -- incremental answer update, citation/grounding check, uncertainty flag
        |
        v
Output: streamed answer + citations + telemetry event log
```

## Shared Contracts (app/schemas.py)

- `TranscriptChunk` — one incremental transcript slice (streaming)
- `ControllerDecision` — WAIT / RETRIEVE / NO_RETRIEVAL + reason (controller)
- `SubQuery` — one decomposed information need (decomposition)
- `RetrievedChunk` — a corpus chunk with provenance (retrieval/fusion)
- `Claim` / `AnswerVersion` — session answer state (session/synthesis/grounding)
- `TelemetryEvent` — one structured pipeline event (telemetry)

`app/retrieval/base.py` defines the `Retriever` interface consumed by controller,
decomposition, and synthesis — implemented by `app/retrieval/dense.py` and
`app/retrieval/sparse.py`.

## WebSocket / SSE Contract

TODO (Phase 2/Track B): frozen once the streaming simulator and frontend contract
are defined.

## Module Sections (filled in per phase)

### streaming/ — TODO Phase 2
### controller/ — TODO Phase 2
### decomposition/ — TODO Phase 3
### retrieval/ — DONE Phase 1: `scripts/ingest.py` parses `corpus/` (PDF via PyMuPDF,
DOCX via python-docx, MD/TXT via a heading-based splitter), chunks deterministically
(content-hash chunk_ids, sentence-aware, no overlap yet), embeds with
sentence-transformers into FAISS (`dense.py`), and builds a BM25 index
(`sparse.py`) over the same chunks. Both implement `Retriever.retrieve()`.
Verified: identical chunk_ids across repeated ingests; both retrievers surface
the correct chunk for known in-corpus phrases (`tests/test_retrieval.py`).
### fusion/ (RRF + dedupe + rerank) — TODO Phase 3
### session/ + synthesis/ — TODO Phase 4
### grounding/ — TODO Phase 5
### telemetry/ — TODO Phase 6
### evaluation/ — TODO Phase 7
### frontend/ — TODO Phase 8

## Known Issues / Open Questions

- `docker compose up` config is written and the app verified to run standalone
  (`uvicorn app.main:app`, `/health` returns 200), but has not been verified via
  a live `docker compose up` in this environment — Docker Desktop's daemon was
  not running. Re-verify once Docker Desktop is started.
