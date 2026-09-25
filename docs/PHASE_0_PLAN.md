# PHASE 0 — Implementation Plan
## Streaming Live RAG — Proposed Build Plan (awaiting approval)

---

## 1. Proposed Repository Tree

```
streaming-live-rag/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml / requirements.txt
├── README.md
├── docs/
│   ├── CHALLENGE_BREAKDOWN.md
│   ├── PHASE_0_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── DEPENDENCIES.md
│   └── HACKATHON_STATUS.md
├── corpus/                     # provided source documents
├── data/                       # processed chunks + metadata (json/parquet)
├── indexes/                    # FAISS index + BM25 index artifacts
├── scripts/
│   ├── ingest.py
│   └── run_eval.py
├── app/
│   ├── main.py                 # FastAPI app, WebSocket/SSE endpoints
│   ├── config.py
│   ├── schemas.py              # Pydantic models shared across modules
│   ├── streaming/
│   │   ├── simulator.py        # transcript chunk feeder
│   │   └── events.py
│   ├── controller/
│   │   ├── stability.py        # WAIT/RETRIEVE/NO_RETRIEVAL heuristics
│   │   └── llm_fallback.py     # ambiguous-case LLM check (optional)
│   ├── decomposition/
│   │   └── decomposer.py       # sub-query extraction + confidence fallback
│   ├── retrieval/
│   │   ├── base.py             # Retriever interface
│   │   ├── dense.py            # sentence-transformers + FAISS
│   │   └── sparse.py           # rank_bm25
│   ├── fusion/
│   │   ├── rrf.py              # Reciprocal Rank Fusion
│   │   ├── rerank.py
│   │   └── dedupe.py
│   ├── session/
│   │   ├── store.py            # SQLite-backed, session_id scoped
│   │   └── models.py           # AnswerVersion, Claim, Session
│   ├── synthesis/
│   │   ├── generator.py        # LLM call (OpenAI-compatible, provider-agnostic)
│   │   └── delta.py            # diff/merge for late-constraint refinement
│   ├── grounding/
│   │   ├── citation_validator.py
│   │   └── uncertainty.py
│   ├── telemetry/
│   │   ├── logger.py
│   │   └── schema.py
│   └── evaluation/
│       ├── gates.py             # G1–G6 checks
│       └── fixtures/            # synthetic streaming test scenarios
├── frontend/
│   └── index.html               # single-page demo UI (vanilla JS + SSE/WS)
└── tests/
    ├── test_controller.py
    ├── test_decomposition.py
    ├── test_retrieval.py
    ├── test_session_refinement.py
    ├── test_grounding.py
    └── test_gates.py
```

## 2. Dependency Table (initial — full version goes in `/docs/DEPENDENCIES.md`)

| Dependency | Purpose | Why chosen | Alternative considered | Required for demo? |
|---|---|---|---|---|
| FastAPI + Pydantic | API/streaming server, schemas | Async-native, fast to build, typed | Flask (no native async) | Yes |
| sentence-transformers | Dense embeddings | Small models, no API dependency, deterministic | OpenAI embeddings | Yes |
| FAISS | Vector index | In-process, zero extra container, fast setup | Qdrant | Yes |
| rank_bm25 | Sparse retrieval | Pure Python, no server, permissive license | Elasticsearch | Yes |
| SQLite | Session + metadata store | Zero-ops, file-based, satisfies session isolation trivially | Postgres+pgvector | Yes |
| OpenAI-compatible client (provider-agnostic wrapper) | Answer synthesis LLM calls | Swappable backend (hosted or local via Ollama) | Hard-coded provider SDK | Yes |
| Docker + docker-compose | Reproducibility (G1) | Required by spec | — | Yes |
| pytest | Evaluation harness | Standard, integrates with G1–G6 checks | — | Yes |
| Vanilla JS/HTML + SSE | Demo UI | Zero build step, fastest to ship in 24h | React+Vite | Optional (UI is graded loosely) |
| CrossEncoder reranker | Neural rerank | Improves G3/G4 precision if time allows | Deterministic heuristic rerank | Optional |
| Ollama/llama.cpp local path | Vendor-neutral LLM option | Avoids hard lock-in per spec principle #7 | — | Optional |

## 3. 24-Hour Execution Plan (from the guide, unchanged in structure)

| Window | Phase | Deliverable | Stop condition |
|---|---|---|---|
| H0–1 | Setup | Repo, Docker, interfaces, task board | Hello-world app runs |
| H1–4 | Ingestion | Parser, chunker, embeddings, BM25, FAISS | Known query retrieves correct doc |
| H4–7 | Streaming + Controller | Simulator, WAIT/RETRIEVE/NO_RETRIEVAL | Retrieval visibly starts before utterance ends |
| H7–11 | Multi-intent + hybrid retrieval | Decomposer, parallel retrieval, fusion, rerank, dedupe | Compound query → multiple merged searches |
| H11–14 | Session refinement | Session store, answer versions, delta engine | Late constraint updates answer, no restart |
| H14–17 | Grounding | Citation validator, uncertainty detector | Unsupported claims explicitly flagged |
| H17–19 | Telemetry | Structured logs, event schema, latency capture | Full request replayable from logs |
| H19–21 | Evaluation harness | Automated G1–G6 tests | All 6 gates have executable tests |
| H21–23 | Demo UI + polish | Pipeline visualization page | Judge understands flow in 30s |
| H23–24 | Final integration | Clean build, full test run, demo record, README | Everything above is green |

**Feature freeze:** no new major features after H19; hard freeze (bugs/deploy/tests/demo only) after H22.

## 4. What Can Run in Parallel

Once interfaces are locked at H1, these can proceed independently with minimal merge conflicts:

- **Track A (Ingestion + Retrieval):** ingestion pipeline, dense retriever, sparse retriever, fusion/rerank — self-contained, testable against the corpus alone.
- **Track B (Streaming + Controller):** transcript simulator and WAIT/RETRIEVE/NO_RETRIEVAL logic — only needs the `Retriever` interface signature, not its implementation, to build/test against mocks.
- **Track C (Session + Synthesis + Grounding):** session store, answer versioning, delta engine, citation validator — can be built and unit-tested against mocked retrieval results.
- **Track D (Telemetry + Evaluation):** event schema and G1–G6 harness can be scaffolded from day one against mock events, then pointed at the real pipeline once it exists.

Frontend (Track E) only needs the WebSocket/SSE event contract, which should be one of the first things frozen at H1.

## 5. Three Highest Technical Risks

1. **Controller precision (WAIT vs RETRIEVE vs NO_RETRIEVAL).** This is the hardest thing to get reliably right in heuristics and it's graded directly (G2) and gates everything downstream. Risk: too aggressive → noisy premature searches (explicitly called out as pitfall #1); too conservative → misses the "before utterance ends" target. Mitigation: start with a generous heuristic (entity/slot completeness + minimum stable token window) tuned against the provided example, and keep an LLM-fallback only for genuinely ambiguous cases so it doesn't become the single point of failure.

2. **Session refinement without full restart (G5) + citation grounding (G4) together.** The late-constraint path has to retrieve *only the delta*, merge it into an existing answer, and keep every citation traceable across versions — this is the most state-heavy, easiest-to-get-subtly-wrong part of the system, and a bug here silently fails both G4 and G5 at once. Mitigation: design the `AnswerVersion`/claim-diff data model before writing any retrieval code (Track C should start on data schemas at H1, not H11).

3. **Time pressure causing scope creep into non-graded polish (UI, extra backends, neural reranker) at the expense of gate coverage.** Given the strict feature-freeze discipline required, the real risk is spending H14+ hours on UI/demo polish while G1–G6 automated tests remain unwritten. Mitigation: evaluation harness scaffolding starts at H1 (Track D) in parallel, not after H19 as a bolt-on.

## 6. Minimum Viable System (must-have to pass all 6 gates)

- Deterministic ingestion → FAISS + BM25 indexes with preserved chunk metadata
- Heuristic-only controller (no LLM fallback required, though useful) producing WAIT/RETRIEVE/NO_RETRIEVAL with a logged reason
- Decomposer that splits on clear compound markers (conjunctions / multiple question words / multiple entities) with a same-query fallback on low confidence
- RRF fusion of dense+sparse, simple dedupe by chunk_id, no neural reranker required
- SQLite session store keyed by session_id, with an `AnswerVersion` list and a basic diff-based delta engine
- Citation validator that checks claim↔chunk mapping via simple string/keyword overlap or an LLM-graded check, refusing ungrounded claims
- JSON structured logs for every event type listed in the spec
- pytest suite covering all six gates against synthetic scenarios
- `docker compose up` single-command launch
- One plain HTML page showing transcript → decision → sub-queries → sources → answer → citations → latency

## 7. Optional Features to Cut First If Time Runs Short (in cut order)

1. Local LLM path (Ollama/llama.cpp) — keep only the OpenAI-compatible path, document the abstraction exists
2. Neural CrossEncoder reranker — fall back to RRF-only fusion
3. OpenTelemetry/Prometheus metrics — structured JSON logs alone satisfy G6
4. Animated/styled frontend — plain unstyled HTML table view is enough to demo the pipeline
5. LLM-fallback in the controller for ambiguous cases — pure heuristics can still hit G2's 80% target on well-behaved test prompts
6. Postgres/pgvector — never start this; SQLite+FAISS from the beginning

---

**Waiting for your approval before any application code is written**, per the Phase 0 instructions. Let me know if you want to adjust scope, swap any stack choice, or start straight into Hour 0–1 setup.
