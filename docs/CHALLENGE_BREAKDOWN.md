# CHALLENGE_BREAKDOWN.md
## Streaming Live RAG — Theme 4 (Samsung Prism)

---

## A. Problem Statement

Standard RAG systems are batch-oriented: user finishes the full utterance → one query fires → system searches → system answers. This is unacceptable for conversational/voice interfaces because it introduces multi-second dead air, treats a single compound utterance as one search when it may contain 2–3 distinct information needs, and throws away everything and restarts from scratch the moment the user adds a clarifying detail mid-conversation.

The challenge asks for an **event-driven streaming RAG engine** that listens to a transcript as it arrives (not after it ends), decides *while listening* whether it has enough signal to search, breaks compound questions into parallel sub-queries, and when new constraints show up later in the conversation, patches the existing answer instead of rebuilding it.

## B. Required System Behavior

1. Consume timestamped transcript **chunks**, not a single final string.
2. Make a per-chunk decision: **WAIT** (not enough signal) / **RETRIEVE** (fire search now, before the user stops talking) / **NO_RETRIEVAL** (this turn needs no corpus access at all).
3. When retrieving, **decompose** compound utterances into distinct, non-duplicate sub-queries and run them **in parallel**.
4. Combine dense + sparse (hybrid) retrieval, fuse, rerank, and deduplicate the results.
5. Keep **session state**: transcript so far, established facts, answer versions, citations, open uncertainties — scoped to one conversation only (never cross-session).
6. When a **late-arriving constraint** appears ("actually it was international travel"), retrieve *only* what's needed to resolve the delta, patch the existing answer into a new version, and preserve everything that's still valid. Never re-run the full pipeline for this.
7. Recognize **presentation-only** requests ("make that shorter," "repeat in bullets") and skip retrieval entirely — operate on session state only.
8. Every factual claim in an answer must trace to a real corpus chunk ID (`[Doc_ID §Section]`). No claim without a citation may be presented as fact.
9. When the corpus doesn't have enough evidence for a sub-intent, say so explicitly instead of guessing.
10. Emit structured, replayable telemetry for every step of every request.

## C. Required Architecture

Four pipeline stages (per the PDF diagram), plus telemetry as a first-class cross-cutting concern:

```
Transcript stream (chunk@0.0s → chunk@0.8s → chunk@1.6s → [end]@2.1s)
        │
        ▼
[1] Retrieval Controller       — intent stability check → WAIT | RETRIEVE | NO_RETRIEVAL
        │ (on RETRIEVE)
        ▼
[2] Multi-Intent Decomposer    — split into sub-queries, route in parallel
        │
        ▼
[3] Corpus Retrieval & Fusion  — dense + sparse hybrid search → rerank → dedupe
        │
        ▼
[4] Session-Aware Synthesis    — incremental answer update, citation/grounding check, uncertainty flag
        │
        ▼
Output: streamed answer + citations + telemetry event log
```

Mapped to code, this is one FastAPI service with clean internal module boundaries — **not** microservices:

```
app/
  streaming/     [1a] transcript simulator + chunk event stream
  controller/    [1]  intent stability check, WAIT/RETRIEVE/NO_RETRIEVAL
  decomposition/ [2]  sub-query extraction + parallel routing
  retrieval/     [3a] dense retriever, sparse (BM25) retriever
  fusion/        [3b] RRF fusion, rerank, dedupe
  session/       [4a] session store, answer versions, delta engine
  synthesis/     [4b] LLM-backed answer generation (session-aware)
  grounding/     [4c] citation validator, uncertainty detector
  telemetry/     structured event logger, schema
  evaluation/    G1–G6 automated test harness
```

## D. Hard Constraints (non-negotiable)

| Constraint | Meaning for implementation |
|---|---|
| **Corpus isolation** | Zero web search, zero third-party KBs, zero "the LLM just knows this" answers for facts. Everything factual must come from indexed corpus chunks. |
| **No hardcoding / no precomputation** | The eval set is held-out and private. Don't bake sample Q&A, canned strings, or the demo prompts into app logic — the code must generalize. |
| **Rigorous factual grounding** | Every factual sentence needs a `[Doc_ID §Section]` tag or an explicit uncertainty statement. Never invent a doc ID. |
| **Session-bound state** | No persistence or profiling across sessions. State is ephemeral, keyed by `session_id`, and dies with the session. |
| **Architectural parsimony** | No multi-agent frameworks or heavyweight orchestration just because they exist — every added component must earn its latency/compute cost. Justify it or cut it. |

## E. Input/Output Examples (from the spec — treat as ground truth for behavior, not literal test data)

**Example 1 — incremental multi-intent:**
`0.0s "workshop in..."` → WAIT → `0.8s "...Pune for 30 people..."` → provisional RETRIEVE (`"Pune workshop venue capacity 30"`) → `1.6s "...cancellation policy and catering options"` → decompose into 3 sub-queries, parallel retrieve → `2.1s [end]` → synthesize one grounded answer citing all three, flagging anything unverifiable. Output is a structured JSON record: `retrieval_events[]`, `sub_queries[]`, `answer`, `citations[]`, `uncertainty`.

**Example 2 — late-arriving detail:** Initial answer (V1) cites base policy. User adds "international, booked after travel." System does **not** restart — it dispatches *targeted* queries for international-travel and late-booking exceptions only, then emits V2 that keeps V1's still-valid content, adds new citations, and states the new requirement (director approval, currency verification).

**Example 3 — query suppression:** "Repeat your last answer in two bullets" → controller emits `retrieval_required: false, reason: presentation_restructure` → zero vector/BM25 calls → existing session content is reformatted only.

## F. Evaluation Gates (automated, quantitative)

| Gate | Criterion | Target | What it actually tests |
|---|---|---|---|
| G1 | Reproducibility | Pass/Fail | `docker compose up` (or equivalent single command) on a clean machine, automated replay suite runs unattended |
| G2 | Early retrieval | ≥80% of eligible queries | Retrieval starts before the transcript's final chunk arrives, without excessive false triggers on non-retrieval turns |
| G3 | Multi-intent identification | ≥70% of compound queries | At least 2 distinct sub-intents correctly isolated |
| G4 | Factual grounding | ≥85% citation support | Every sampled claim traces to a real chunk; zero fabricated doc IDs |
| G5 | Session refinement | Verified continuity | Late constraints trigger targeted retrieval + answer delta, never a full-corpus re-search |
| G6 | Telemetry | 100% trace coverage | Every request has a complete, replayable event trail: timestamps, decisions, triggers, citations, version lineage, token cost |

## G. Common Technical Pitfalls (explicitly called out — build defenses against each)

1. **Eager/premature retrieval on noise** — firing search on every token thrashes the system and pollutes context. Controller must wait for a genuine intent-stability signal.
2. **Context loss on late constraints** — clearing session state when a clarification arrives causes duplicated latency and disjointed replies.
3. **Citation hallucination** — fabricated `[Doc_999]`-style IDs, or citing a chunk that doesn't actually contain the claimed fact. This is graded automatically — it's an easy way to fail G4.
4. **Ignoring presentation-only turns** — re-querying the vector DB for "make it shorter" wastes tokens and risks drifting the answer away from the original grounded facts.
5. **Over-fragmenting sub-queries** — splitting one simple question into many near-duplicate queries pollutes the reranker and burns the token budget.

## H. Required Deliverables

1. **Reproducible repository** — source, pinned lockfiles, env config templates, one-command run (`docker compose up` or a clean CLI runner).
2. **System Architecture Brief** (≤6 pages) — design rationale, retrieval trigger logic, decomposition strategy, data provenance, trade-offs, failure-mode mitigations.
3. **Benchmarking & Evaluation Report** — quantitative comparison vs. a baseline pipeline, ≥3 analyzed edge-case failures, ≥2 architectural ablations (e.g. hybrid vs. dense-only retrieval, rule-based vs. model-based controller).
4. **System demonstration video** (≤5 min) — early retrieval, multi-intent decomposition, late-detail refinement, presentation-query suppression, citation traceability, runtime telemetry.
5. **Telemetry & Observability Schema** — structured logs: end-to-end latencies, retrieval trigger events, answer version updates, inference cost estimates.

## I. Mandatory vs. Optional

**Mandatory (graded directly by G1–G6, cannot be cut):**
- Chunk-by-chunk transcript ingestion with WAIT/RETRIEVE/NO_RETRIEVAL controller
- Multi-intent decomposition with parallel sub-query retrieval
- Hybrid (dense + sparse) retrieval with fusion + rerank + dedupe
- Session state with answer versioning and targeted delta refinement (no full restarts)
- Citation validator + explicit uncertainty output
- Full structured telemetry with 100% trace coverage
- Single-command reproducible deployment
- Automated tests covering all six gates

**Optional / nice-to-have (score-supporting but not gate-critical):**
- Polished, animated demo UI (a plain pipeline-visualization page is enough)
- OpenTelemetry/Prometheus wiring (structured JSON logs satisfy G6 on their own)
- Local LLM path (Ollama/llama.cpp) alongside an OpenAI-compatible API — nice for the "no vendor lock-in" story, not required for gates
- CrossEncoder neural reranker (a deterministic RRF + heuristic rerank can satisfy G3/G4 targets)
- PostgreSQL+pgvector — SQLite + FAISS is sufficient at hackathon scale

## J. What to Simplify for a 24-Hour Build

- **Controller = heuristics, not ML.** A rule-based intent-stability check (entity/slot completeness, sentence-boundary + minimum-token heuristics, a short "is this a formatting-only instruction" keyword/regex + one LLM-call fallback for ambiguous cases) is faster to build, easier to debug live, and fully explainable to judges. Skip a trained classifier entirely.
- **Reranking**: RRF score fusion + a lightweight heuristic (or a single small CrossEncoder pass if time allows) beats building a custom trained reranker.
- **Vector DB**: FAISS in-process, not Qdrant — one fewer container, one fewer network hop, zero deployment risk.
- **Session store**: SQLite (or even in-memory dict keyed by `session_id` with periodic SQLite snapshot) — a full Postgres setup buys nothing at this scale and risks the reproducibility gate (G1).
- **Frontend**: one page — live transcript feed, controller decision badge, sub-query list, retrieved sources, streamed answer, citations, and a telemetry/latency strip. No auth, no multi-page app.
- **Multi-agent frameworks**: explicitly avoid (the spec penalizes unjustified orchestration overhead under "Architectural Parsimony"). A single FastAPI app with clean internal modules satisfies every requirement.
