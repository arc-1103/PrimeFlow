# AGENTS.md
## Streaming Live RAG — Agent Operating Instructions

This file is read by any coding agent (Claude Code, or otherwise) working in this repository. It is the source of truth for how to behave in this codebase. If something here conflicts with a one-off instruction in chat, ask before overriding it — this file encodes hackathon-wide constraints that apply across every session and every module.

---

## 1. What This Project Is

An event-driven **Streaming Live RAG engine**: it ingests a transcript incrementally, decides in real time whether to retrieve, decomposes compound utterances into parallel sub-queries, retrieves hybrid (dense+sparse) evidence, and refines an existing answer in place when late constraints arrive — instead of the standard "wait for full utterance, one-shot search" RAG pattern.

Full context, in order of authority:
1. `docs/CHALLENGE_BREAKDOWN.md` — the graded spec, source of truth for required behavior
2. `docs/PHASE_0_PLAN.md` — repo tree, dependency choices, risk list
3. `docs/PHASE_BREAKDOWN.md` — the phase you are currently implementing, with its own agentic prompt, stop condition, and verification conditions
4. `docs/ARCHITECTURE.md` / `docs/HACKATHON_STATUS.md` — living documents, update them as you go, don't let them drift from the code

**Read the relevant phase in `docs/PHASE_BREAKDOWN.md` before writing any code for that phase.** Each phase has its own agentic prompt template — treat it as your task brief, not just background reading.

## 2. Hard Constraints (never violate these, regardless of what a task seems to ask for)

- **Corpus isolation.** No web search, no third-party knowledge bases, no answering factual questions from parametric/training knowledge. Every factual claim must trace to an indexed corpus chunk.
- **No hardcoding / no precomputation.** The benchmark replay set is held-out and private. Never embed sample queries, canned answers, or demo-specific strings into application logic. If you catch yourself writing `if query == "..."`, stop.
- **Never fabricate a citation.** A `[Doc_ID §Section]` tag must reference a chunk ID that actually exists in `data/chunks.jsonl` and actually supports the claim. If evidence is missing, emit an explicit uncertainty string — never guess, never invent an ID.
- **Session-bound state only.** No cross-session memory, profiling, or persistence beyond one `session_id`'s lifetime. Sessions must never read or leak into each other's state — this is unit-tested, keep it passing.
- **Architectural parsimony.** Don't add a framework, service, or dependency because it's popular. Every dependency needs a one-line justification in `docs/DEPENDENCIES.md`. No multi-agent orchestration frameworks, no new microservice, no new datastore without checking `docs/PHASE_0_PLAN.md`'s stack decisions first.
- **Don't restart sessions unnecessarily.** Late-arriving constraints get targeted retrieval and an answer delta (new `AnswerVersion`), not a full pipeline re-run. This is graded (G5) — don't regress it while touching session/synthesis code.

## 3. Reinvent Nothing — Use These, Don't Rebuild Them

| Need | Use | Do not build |
|---|---|---|
| PDF/DOCX parsing | PyMuPDF, python-docx | a custom parser |
| Dense embeddings | sentence-transformers | a custom embedding model |
| Vector index | FAISS | a custom ANN index, Qdrant (unless explicitly revisited) |
| Sparse retrieval | rank_bm25 | a custom TF-IDF/BM25 implementation |
| Fusion | Reciprocal Rank Fusion (standard formula) | a bespoke scoring heuristic |
| Reranking | RRF order, or a sentence-transformers CrossEncoder if time allows | a trained reranker |
| Session/metadata store | SQLite | Postgres/pgvector (out of scope for this build) |
| API/streaming | FastAPI + WebSocket/SSE + Pydantic | Flask, a custom protocol |
| LLM calls | OpenAI-compatible client abstraction (swap-in Ollama/llama.cpp) | a hard-coded single-vendor SDK call scattered through the code |
| Structured logs | Python `logging` + JSON formatter | a custom telemetry framework |
| Tests | pytest | a custom test runner |
| Frontend | Plain HTML/CSS/vanilla JS over the existing WS/SSE contract | a React/Vite build for a single demo page |

The two places light custom logic is *expected* and correct: the deterministic sentence-aware chunker (Phase 1) and the claim-level diff/delta engine (Phase 4). Everything else routes through the table above.

## 4. Repository Map

```
app/
  streaming/     transcript chunk simulator + event stream
  controller/    WAIT / RETRIEVE / NO_RETRIEVAL heuristics
  decomposition/ sub-query extraction
  retrieval/     Retriever interface, dense.py, sparse.py
  fusion/        RRF, dedupe, rerank
  session/       session store, AnswerVersion model
  synthesis/     answer generation, delta engine
  grounding/     citation validator, uncertainty detector
  telemetry/     structured event logger, schema
  evaluation/    G1–G6 automated gate tests
scripts/         ingest.py, run_eval.py
data/, indexes/, corpus/   pipeline artifacts (not hand-edited)
frontend/        single demo page
tests/           mirrors app/ module structure
docs/            all planning + status documents
```

Shared contracts live in `app/schemas.py` and `app/retrieval/base.py`. **Do not change a shared schema without checking what else consumes it** — grep for the model name across `app/` and `tests/` first.

## 5. How to Run Things

```bash
docker compose up                     # full stack, single command (G1)
python scripts/ingest.py              # rebuild chunk store + indexes from corpus/
python scripts/run_eval.py            # run all G1–G6 automated gates, print results table
pytest                                # full test suite
pytest tests/test_controller.py -v    # one module
```

If any of these commands don't work as described, that's a bug to fix, not a doc to quietly ignore — G1 is graded on exactly this.

## 6. Working Style

- **Follow the phase's agentic prompt** in `docs/PHASE_BREAKDOWN.md` verbatim for scope — don't pull in work from a later phase because it seemed convenient.
- **Don't blindly continue after a failed verification.** Each phase has explicit verification conditions; if one fails, fix it before moving to the next phase's task.
- **Every task, on completion, reports:** what changed, why, files changed, tests added/passed, metrics (if applicable), remaining risk, next recommended task. Put this in the PR description or commit message, not just in chat.
- **Feature freeze at H19** (from `docs/PHASE_0_PLAN.md`): no new major features after this point in the 24-hour clock — only bug fixes, reliability, telemetry, docs, demo prep. **Full freeze at H22**: critical bugs, deployment, tests, demo only. If you're an agent picking up work late in the clock, check the current hour before proposing new scope.
- **Never commit secrets.** LLM API keys and any credentials go in `.env` (gitignored), referenced via `.env.example` with placeholder values only.
- **Update `docs/HACKATHON_STATUS.md`** whenever a gate's actual measured value changes — it should always reflect the latest `run_eval.py` output, not a stale snapshot from an earlier phase.

## 7. Definition of Done for Any Change

Before considering a task complete, confirm:
- [ ] It matches the current phase's expected output in `docs/PHASE_BREAKDOWN.md`
- [ ] It doesn't violate any Hard Constraint in Section 2 above
- [ ] It reuses the open-source component from Section 3 rather than reimplementing it
- [ ] Relevant tests exist and pass (`pytest`)
- [ ] Telemetry is emitted for any new event type introduced (once Phase 6 exists — before that, note it as a TODO for Phase 6, don't skip it silently)
- [ ] `docs/` is updated if the change affects architecture, dependencies, or gate status
