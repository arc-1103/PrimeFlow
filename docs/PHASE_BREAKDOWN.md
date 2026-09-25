# PHASE_BREAKDOWN.md
## Streaming Live RAG — Phase-by-Phase Execution Guide

Ground rule for every phase below: **check the Open-Source Lego Blocks list before writing anything custom.** If a phase's "Reinvent nothing" line names a library, that library does the job — the only custom code is the glue/interface around it.

---

## Phase 0 — Architecture & Repo Setup
**Window:** H0–1

**Objective:** Lock every interface so Tracks A–E (ingestion/retrieval, controller/streaming, session/synthesis, telemetry/eval, frontend) can build in parallel without merge conflicts.

**Expected Input:** Challenge PDF, this breakdown, an empty repo.

**Expected Output:**
- Repo skeleton (`app/`, `docs/`, `scripts/`, `data/`, `indexes/`, `corpus/`, `tests/`, `frontend/`)
- `docker-compose.yml` + `Dockerfile` that boot an empty FastAPI app
- `app/schemas.py` — Pydantic models for every cross-module contract: `TranscriptChunk`, `ControllerDecision`, `SubQuery`, `RetrievedChunk`, `AnswerVersion`, `TelemetryEvent`
- `Retriever` abstract interface (`retrieve(query, top_k) -> list[RetrievedChunk]`)
- Task board (issues/kanban) with the 5 parallel tracks

**Reinvent nothing:** FastAPI + Pydantic for the skeleton; Docker/docker-compose for packaging. Don't hand-roll config loading — `pydantic-settings`.

**Agentic Prompt:**
```
ROLE: Architect
OBJECTIVE: Stand up the repo skeleton, Docker setup, and every shared Pydantic
schema (TranscriptChunk, ControllerDecision, SubQuery, RetrievedChunk,
AnswerVersion, TelemetryEvent) and the Retriever interface, so four other
tracks can build against them without touching this code again.
CONSTRAINTS: No business logic yet. No hardcoded prompts/queries. Every
schema field must map to something named explicitly in the challenge PDF.
INPUT: Challenge PDF, CHALLENGE_BREAKDOWN.md.
OUTPUT: repo tree, docker-compose.yml, app/schemas.py, app/retrieval/base.py,
docs/ARCHITECTURE.md (skeleton).
VERIFICATION: `docker compose up` boots a FastAPI hello-world route with no
errors. `python -c "import app.schemas"` succeeds.
STOP CONDITION: All interfaces are defined and reviewed; no interface changes
should be needed after this point without cross-track discussion.
REPORT: files changed, open questions, next task.
```

**Stop Condition:** Team can run the hello-world app; all shared schemas exist and are frozen.

**Verification Conditions:**
- [ ] `docker compose up` succeeds on a clean checkout
- [ ] Every schema in `app/schemas.py` has a field-for-field match to a concept named in the PDF (no speculative fields)
- [ ] `Retriever` interface has zero implementation — pure contract

---

## Phase 1 — Corpus Ingestion & Indexing
**Window:** H1–4 · **Roadmap ref:** "Corpus audit, indexing, and chunking optimization"

**Objective:** Turn the provided corpus into a deterministic, metadata-preserving chunk store with both a dense and a sparse index built on top.

**Expected Input:** Raw corpus files (PDF/DOCX/MD/TXT) in `corpus/`.

**Expected Output:**
- `data/chunks.jsonl` — one record per chunk: `{chunk_id, doc_id, section, page, text}`
- `indexes/faiss.index` + `indexes/bm25.pkl`
- `scripts/ingest.py` — idempotent: same corpus → same chunk IDs every run

**Reinvent nothing:**
- Parsing: **PyMuPDF** (PDF), **python-docx** (DOCX), plain text/Markdown readers
- Chunking: a simple deterministic sentence-aware splitter (this is the one place light custom code is appropriate — no off-the-shelf chunker fits every corpus shape)
- Dense embeddings: **sentence-transformers** (a small, fast model — e.g. `all-MiniLM-L6-v2` class)
- Vector index: **FAISS** (in-process, no extra container)
- Sparse index: **rank_bm25**

**Agentic Prompt:**
```
ROLE: Ingestion + Retrieval Agent
OBJECTIVE: Build scripts/ingest.py: parse corpus/ → deterministic chunks with
preserved (doc_id, section, page, chunk_id) → sentence-transformers embeddings
→ FAISS index; also build a BM25 index over the same chunks.
CONSTRAINTS: No external knowledge, no web calls. Re-running ingest.py on an
unchanged corpus must reproduce identical chunk_ids (hash-based IDs, not
incrementing counters). Every chunk must carry a valid, traceable source
identifier — no orphan chunks.
INPUT: corpus/ directory, app/retrieval/base.py (Retriever interface).
OUTPUT: scripts/ingest.py, data/chunks.jsonl, indexes/faiss.index,
indexes/bm25.pkl, app/retrieval/dense.py, app/retrieval/sparse.py
(implementing Retriever).
VERIFICATION:
  1. Run ingest.py twice → chunk_ids identical both runs.
  2. Query DenseRetriever and SparseRetriever with a known in-corpus phrase →
     both return the chunk that contains it, with correct doc_id/section.
  3. No chunk in chunks.jsonl has a missing/null source identifier.
STOP CONDITION: A hand-picked test query reliably retrieves the correct known
chunk from both dense and sparse indexes.
REPORT: files changed, tests passed, chunk count, index sizes, known issues.
```

**Stop Condition:** A known test query retrieves the correct chunks from the corpus (per the PDF's own STOP CONDITION for this chunk).

**Verification Conditions:**
- [ ] Same corpus → same chunk IDs on repeated ingestion (determinism, per Hard Constraint "No Hardcoding/No Precomputation" — the *pipeline* must be reproducible even though outputs aren't precomputed)
- [ ] Every retrieved chunk carries a valid `doc_id §section` (satisfies downstream G4 requirement)
- [ ] No corpus content silently dropped (spot-check chunk count vs. source page/section count)

---

## Phase 2 — Streaming Simulator & Retrieval Controller
**Window:** H4–7 · **Roadmap ref:** "Incremental transcript chunking simulator, intent stability classifier & retrieval decision policy"

**Objective:** Feed a transcript incrementally and decide, chunk by chunk, whether to WAIT, RETRIEVE, or declare NO_RETRIEVAL.

**Expected Input:** A transcript string (or pre-scripted timed chunks) + timing config.

**Expected Output:**
- `app/streaming/simulator.py` emitting `{session_id, timestamp, transcript_delta, accumulated_transcript, event_type}` over WebSocket/SSE at configurable intervals
- `app/controller/stability.py` emitting `{decision, confidence, reason, timestamp}` for every chunk

**Reinvent nothing:** No ML classifier needed here — deterministic heuristics (sentence-boundary detection, minimum-stable-token window, keyword/regex check for presentation-only phrasing like "shorter," "bullets," "repeat," "summarize what you said") plus an *optional* single LLM call as a fallback only for genuinely ambiguous cases. Don't train anything.

**Agentic Prompt:**
```
ROLE: Streaming + Controller Agent
OBJECTIVE: Implement the transcript simulator (timestamped chunk emitter) and
the WAIT/RETRIEVE/NO_RETRIEVAL controller as a heuristic decision policy.
CONSTRAINTS: Must not fire retrieval on every incoming token (pitfall #1).
Must correctly suppress retrieval for presentation-only requests (pitfall #4).
Decision must be explainable (a human-readable `reason` string), not a black
box. Use app/retrieval/base.py's Retriever interface only as a mock in tests
— do not depend on Phase 1's concrete implementation being finished.
INPUT: app/schemas.py (TranscriptChunk, ControllerDecision).
OUTPUT: app/streaming/simulator.py, app/controller/stability.py,
tests/test_controller.py with the PDF's three example utterances as fixtures.
VERIFICATION:
  1. "Tell me..." → WAIT.
  2. "I need a customer workshop in Pune for 30 people..." → RETRIEVE before
     the transcript ends.
  3. "Make your previous answer shorter." → NO_RETRIEVAL.
  4. Retrieval timestamp < utterance-end timestamp on the multi-chunk example.
STOP CONDITION: Retrieval visibly starts before utterance completion on the
canonical multi-intent example from the PDF.
REPORT: files changed, tests passed, false-trigger rate on a noise fixture set,
known issues.
```

**Stop Condition:** Retrieval visibly starts before utterance completion (per PDF).

**Verification Conditions:**
- [ ] WAIT / RETRIEVE / NO_RETRIEVAL each independently unit-tested against the PDF's own three examples
- [ ] False-trigger rate measured on a small noise fixture set (incomplete/filler transcript chunks that should not retrieve)
- [ ] Every decision emits a `reason` string (no unexplained decisions — this feeds G6 telemetry later)

---

## Phase 3 — Multi-Intent Decomposition & Hybrid Retrieval
**Window:** H7–11 · **Roadmap ref:** "Query decomposition module, parallelized corpus retrieval, RRF + dedupe reranker"

**Objective:** Turn a compound utterance into distinct sub-queries, retrieve each in parallel across dense+sparse, then fuse/rerank/dedupe into one evidence set.

**Expected Input:** A stabilized query string from the controller (e.g. "venue capacity, cancellation policy and catering options in Pune for 30 people").

**Expected Output:**
- `app/decomposition/decomposer.py` → `{parent_query, sub_queries: [{id, query, intent, entities, constraints}]}`
- `app/fusion/rrf.py`, `app/fusion/dedupe.py`, `app/fusion/rerank.py`
- A merged, deduplicated, reranked `list[RetrievedChunk]` per parent query

**Reinvent nothing:**
- Fusion: **Reciprocal Rank Fusion** (RRF(d) = Σ 1/(k+rank)) — a well-known formula, not a custom scoring scheme
- Reranking: start with RRF-fused order; add a **sentence-transformers CrossEncoder** pass only if time allows
- Decomposition: rule-based split on conjunctions/multiple question anchors + a single LLM call for the general case, with a same-query fallback on low confidence (per the PDF's own stop condition for this chunk) — don't build a custom parser from scratch beyond this

**Agentic Prompt:**
```
ROLE: Ingestion + Retrieval Agent (continued)
OBJECTIVE: Implement query decomposition (parent query → distinct sub-queries)
and hybrid retrieval fusion (dense + sparse → RRF → dedupe → rerank).
CONSTRAINTS: Single-intent query must produce exactly one sub-query — do not
manufacture artificial splits (pitfall #5). If decomposition confidence is low
or sub-queries are near-duplicates, fall back to the original query untouched.
Dense-only, sparse-only, and hybrid retrieval must each work independently;
a missing backend must degrade gracefully, not crash the request.
INPUT: app/retrieval/dense.py, app/retrieval/sparse.py (from Phase 1),
app/schemas.py.
OUTPUT: app/decomposition/decomposer.py, app/fusion/{rrf,dedupe,rerank}.py,
tests/test_decomposition.py, tests/test_retrieval.py.
VERIFICATION:
  1. "What is the venue capacity, cancellation policy and catering options?"
     → 3 distinct sub-queries.
  2. A single-intent question → exactly 1 sub-query.
  3. Kill the dense backend in a test → hybrid retrieval falls back to sparse
     without raising.
  4. No duplicate chunk_ids in the final fused/deduped result set.
STOP CONDITION: A compound query produces multiple parallel searches whose
results are merged into one deduplicated, ranked evidence set.
REPORT: files changed, tests passed, decomposition accuracy on a small hand-
labeled test set, known issues.
```

**Stop Condition:** Compound query → multiple searches → merged evidence (per PDF).

**Verification Conditions:**
- [ ] Multi-intent test set: ≥70% correctly isolate ≥2 sub-intents (this is literally G3 — verify it here, not only at the H19–21 evaluation phase)
- [ ] Single-intent queries never get artificially split
- [ ] Fused result set has zero duplicate `chunk_id`s
- [ ] Missing/failed retrieval backend doesn't crash the request (graceful degradation, per failure-case #11 in the PDF)

---

## Phase 4 — Session-Aware Refinement & Answer Delta
**Window:** H11–14 · **Roadmap ref:** "Ephemeral session memory store, answer delta engine"

**Objective:** Keep per-session state; when a late constraint arrives, retrieve only the delta and produce a new answer version that preserves valid prior content.

**Expected Input:** A session's accumulated state (transcript, prior `AnswerVersion`s, citations, constraints) + a new transcript delta recognized as modifying an existing topic.

**Expected Output:**
- `app/session/store.py` — SQLite-backed, keyed strictly by `session_id`
- `app/session/models.py` — `AnswerVersion { claims, citations, supporting_chunks, changed_claims, unchanged_claims, uncertainty, timestamp }`
- `app/synthesis/delta.py` — diff(old_state, new_state) → targeted retrieval → validated delta → merged new `AnswerVersion`

**Reinvent nothing:** SQLite via the standard library / SQLAlchemy for the store — no need for Postgres at this scale. The "diff" logic is necessarily custom (it's the core IP of this challenge) but should stay a simple claim-level comparison, not a bespoke NLP diffing library.

**Agentic Prompt:**
```
ROLE: Session + Synthesis Agent
OBJECTIVE: Implement the SQLite session store and the answer delta engine:
detect that a new transcript chunk modifies (not replaces) an existing topic,
retrieve only the affected information, and merge it into a new AnswerVersion
without discarding still-valid prior claims or citations.
CONSTRAINTS: Session state must never leak across session_ids (test this
explicitly). Must NOT re-run full-corpus retrieval on a late constraint —
only targeted queries for the new/changed entities. Prior valid citations must
survive into the new version unchanged.
INPUT: app/fusion output (Phase 3), app/schemas.py (AnswerVersion).
OUTPUT: app/session/store.py, app/session/models.py, app/synthesis/delta.py,
tests/test_session_refinement.py using the PDF's "travel reimbursement"
example verbatim as a fixture.
VERIFICATION:
  1. Reproduce the PDF's Example 2 end-to-end: V1 → late detail → V2, and
     assert V2 retains V1's unchanged claims/citations and adds only the delta.
  2. Retrieval call count on the late-constraint turn is smaller than a full
     fresh query would require (prove no full restart happened).
  3. Two parallel sessions with similar topics never see each other's state.
STOP CONDITION: Late constraint updates the answer without restarting the
session (per PDF).
REPORT: files changed, tests passed, retrieval-call reduction measured,
known issues.
```

**Stop Condition:** Late constraint updates answer without restarting session (per PDF).

**Verification Conditions:**
- [ ] End-to-end replay of the PDF's own late-detail example produces V1 → V2 with the expected preserved/added claims
- [ ] Session isolation test: two sessions never cross-contaminate state (Hard Constraint: session-bound state)
- [ ] Delta retrieval is demonstrably narrower than a full re-query (this is what G5 actually checks — "verified state continuity")

---

## Phase 5 — Grounding, Citation Validation & Uncertainty
**Window:** H14–17 · **Roadmap ref:** "Strict grounding verification and explicit uncertainty flagging"

**Objective:** Guarantee every factual claim in a generated answer traces to a real chunk, and every unsupported claim is explicitly flagged instead of stated as fact.

**Expected Input:** A draft answer (from `app/synthesis/generator.py`) + the evidence chunks it was generated from.

**Expected Output:**
- `app/grounding/citation_validator.py` — per-claim check: does a retrieved chunk actually support this claim? Valid → `[Doc_ID §Section]` citation; invalid/unsupported → uncertainty string, never a fabricated citation
- `app/grounding/uncertainty.py`

**Reinvent nothing:** Claim-to-chunk support checking can be done with simple lexical/entailment heuristics (keyword overlap, or a lightweight NLI cross-encoder from sentence-transformers) or a single LLM grading call — don't build a custom entailment model.

**Agentic Prompt:**
```
ROLE: Session + Synthesis Agent (continued)
OBJECTIVE: Implement the citation validator and uncertainty detector that sit
between answer generation and the final response: for every factual claim,
confirm it against retrieved chunks and either attach a real citation or
replace it with an explicit uncertainty statement.
CONSTRAINTS: NEVER emit a document ID that doesn't exist in the retrieved
evidence set (pitfall #3). If evidence is insufficient for a sub-intent, the
uncertainty string must name the specific unverified aspect, not a generic
disclaimer.
INPUT: draft answer text, evidence chunk list (from Phase 3/4).
OUTPUT: app/grounding/citation_validator.py, app/grounding/uncertainty.py,
tests/test_grounding.py.
VERIFICATION:
  1. Feed a fabricated-citation draft answer → validator strips/rejects it,
     never passes it through.
  2. Feed a claim with no supporting chunk → output contains an explicit,
     specific uncertainty statement, not a silent omission or a guess.
  3. Run against ≥20 sampled claims from Phase 3/4 test outputs → measure
     citation support rate.
STOP CONDITION: Unsupported claims are explicitly marked uncertain (per PDF);
zero fabricated document IDs across the test set.
REPORT: files changed, tests passed, measured citation support % (target
≥85%, this is G4), known issues.
```

**Stop Condition:** Unsupported claims are explicitly marked uncertain (per PDF).

**Verification Conditions:**
- [ ] Zero fabricated document IDs across the full test suite (hard requirement, not a percentage)
- [ ] Citation support rate ≥85% measured on a sampled claim set — this is G4, verify it here early rather than discovering the shortfall at H19
- [ ] Uncertainty statements are specific (name the unverified aspect) not generic boilerplate

---

## Phase 6 — Telemetry & Observability
**Window:** H17–19 · **Roadmap ref:** "End-to-end telemetry instrumentation"

**Objective:** Every event in the pipeline (controller decision, retrieval call, decomposition, answer version, citation) is logged in a consistent structured schema, such that a full request can be reconstructed from logs alone.

**Expected Input:** Live events emitted from every module built in Phases 1–5.

**Expected Output:**
- `app/telemetry/schema.py` — one canonical event schema (timestamp, session_id, event_type, transcript_chunk, controller_decision, retrieval_trigger, query, subqueries, retrieved_document_ids, retrieval_latency_ms, rerank_latency_ms, answer_version, citation_ids, token_count, uncertainty, errors)
- `app/telemetry/logger.py` — structured JSON logger wired into every module's call sites

**Reinvent nothing:** Python's standard `logging` module with a JSON formatter is sufficient. OpenTelemetry/Prometheus are explicitly optional per the plan — only add if there's spare time after gates are covered.

**Agentic Prompt:**
```
ROLE: Evaluation + Telemetry Agent
OBJECTIVE: Instrument every module (controller, decomposer, retriever, fusion,
session, grounding) to emit a structured JSON event matching the canonical
telemetry schema, with zero gaps in the trace.
CONSTRAINTS: Do not change any module's business logic — this is instrumentation
only, wired at call boundaries. Every request must be fully reconstructable
from its logged events alone (request → decision → retrieval → answer
version → citations → completion).
INPUT: All modules from Phases 1–5.
OUTPUT: app/telemetry/schema.py, app/telemetry/logger.py, updated call sites
across app/, tests/test_telemetry_coverage.py.
VERIFICATION: Run the PDF's three demo scenarios end-to-end → for each, assert
the log contains: request event, retrieval decision event, retrieval event(s),
answer version event, citation event, completion event — with no missing
step.
STOP CONDITION: A complete request can be replayed from telemetry alone (per
PDF).
REPORT: files changed, tests passed, trace coverage % measured (target 100%,
this is G6), known issues.
```

**Stop Condition:** A complete request can be replayed from telemetry (per PDF).

**Verification Conditions:**
- [ ] 100% of the six required event types present for every one of the three demo scenarios (this is G6, checked directly)
- [ ] No module call site is unlogged — spot-check by grepping module entry points against logger calls
- [ ] Log schema is stable JSON (parseable by the eval harness in Phase 7 without special-casing)

---

## Phase 7 — Evaluation Harness (G1–G6)
**Window:** H19–21 · **Roadmap ref:** "Benchmark execution across held-out streaming test sets"

**Objective:** Automated, quantitative tests for all six gates, runnable with a single command, producing the numbers that go into `HACKATHON_STATUS.md`.

**Expected Input:** The fully assembled pipeline (Phases 0–6) + a set of streaming test fixtures (incremental multi-intent, late-constraint, presentation-only, and the 15 explicit failure cases from the PDF).

**Expected Output:**
- `app/evaluation/gates.py` — one function per gate, each returning `{gate, target, actual, pass}`
- `scripts/run_eval.py` — single command producing a results table
- `docs/HACKATHON_STATUS.md` filled in with real numbers

**Reinvent nothing:** pytest as the test runner; no custom benchmarking framework.

**Agentic Prompt:**
```
ROLE: Evaluation + Telemetry Agent (continued)
OBJECTIVE: Build automated tests for G1–G6 against the assembled pipeline and
the 15 explicit failure cases from the PDF (short transcript, noisy transcript,
repeated chunks, multi-intent, late constraint, contradictory evidence, no
evidence, formatting-only, repeated question, near-duplicate subqueries,
retrieval backend failure, LLM failure, empty corpus, long conversation,
session collision).
CONSTRAINTS: Tests must run against the real pipeline, not mocks, wherever
feasible. No test may embed a canned expected answer string that only matches
because it was copy-pasted from a demo run — assert on structural/behavioral
properties (citation validity, sub-intent count, version lineage, etc.), not
literal text.
INPUT: Full app/ pipeline, telemetry logs.
OUTPUT: app/evaluation/gates.py, app/evaluation/fixtures/, scripts/run_eval.py,
tests/test_gates.py, docs/HACKATHON_STATUS.md (populated).
VERIFICATION: `python scripts/run_eval.py` produces a table with actual values
for all 6 gates and a pass/fail per gate. All 15 failure cases run without an
unhandled crash.
STOP CONDITION: All six evaluation categories have executable, automated
tests, and every one of the 15 failure cases has been exercised at least once.
REPORT: files changed, tests passed, full G1–G6 results table, list of any
failing gates and why, known issues.
```

**Stop Condition:** All six evaluation categories have executable tests (per PDF).

**Verification Conditions:**
- [ ] `scripts/run_eval.py` runs single-command and outputs a results table for G1–G6
- [ ] Every one of the 15 explicit failure cases exercised at least once, no unhandled crash
- [ ] Results table copied into `HACKATHON_STATUS.md`

---

## Phase 8 — Demo UI & Final Integration
**Window:** H21–24 · **Roadmap ref:** "Single-command container packaging and deployment documentation"

**Objective:** A judge can watch the full pipeline (transcript → decision → sub-queries → sources → answer version → citations → latency) and understand the innovation within 30 seconds; final clean build, test run, and demo recording.

**Expected Input:** The complete, gate-passing pipeline.

**Expected Output:**
- `frontend/index.html` — single page, live transcript feed / decision badge / sub-query list / retrieved sources / streamed answer / citations / latency strip, wired to the backend over WebSocket/SSE
- Recorded ≤5-minute demo video covering all three PDF demo scenarios
- Final `README.md`, `docs/ARCHITECTURE.md`, `docs/HACKATHON_STATUS.md`

**Reinvent nothing:** Plain HTML/CSS/vanilla JS consuming the existing WebSocket/SSE contract from Phase 0 — no frontend framework needed for a single page.

**Agentic Prompt:**
```
ROLE: Frontend/Demo Agent
OBJECTIVE: Build one HTML page visualizing, in real time: live transcript →
controller decision → sub-queries → retrieved sources → streaming answer →
citations → per-step latency, then run final integration (clean docker build,
full test suite, demo scenario run, README).
CONSTRAINTS: No frontend framework/build step — plain HTML/CSS/JS only,
consuming the existing WS/SSE event contract. Do not touch backend logic.
INPUT: Backend WS/SSE endpoints, telemetry event schema.
OUTPUT: frontend/index.html, README.md (finalized), demo recording, final
docker compose smoke test.
VERIFICATION:
  1. Clean `docker compose up` on a fresh clone, no manual steps.
  2. Run all three PDF demo scenarios live through the UI, screen-recorded.
  3. Full pytest suite green.
STOP CONDITION: A judge can understand the innovation within 30 seconds of
watching the UI (per PDF); all items in the project stop-condition checklist
are satisfied.
REPORT: files changed, final gate results, demo video link, known
limitations, future improvements.
```

**Stop Condition:** A judge can understand the pipeline within 30 seconds (per PDF); full project stop-condition checklist satisfied.

**Verification Conditions:**
- [ ] Fresh clone + `docker compose up` works with zero manual intervention (G1, re-verified one final time)
- [ ] All three PDF demo scenarios run live and are recorded
- [ ] Full pytest suite passes on the final commit
- [ ] `README.md` explains how to run everything end to end

---

## Cross-Phase Discipline

- **Feature freeze at H19:** only bug fixes, benchmark improvements, reliability, UI clarity, telemetry, docs, demo prep from here.
- **Full freeze at H22:** only critical bugs, deployment, tests, demo.
- Every phase's agent reports the same six things on completion: what changed, why, files changed, tests added/passed, metrics, remaining risk, next task — per the loop in `PHASE_0_PLAN.md`.
