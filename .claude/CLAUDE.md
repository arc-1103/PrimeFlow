# CLAUDE.md

This project's agent instructions live in [`AGENTS.md`](./AGENTS.md) — that file is the
canonical source (so instructions stay in one place and don't drift between tools).

Claude Code should read `AGENTS.md` in full before making any changes in this repository,
along with the phase-specific brief in `docs/PHASE_BREAKDOWN.md` for whatever phase is
currently being worked on.

Everything below is Claude-Code-specific; it does not repeat what's already in AGENTS.md.

## Claude Code specifics

- Treat each Phase in `docs/PHASE_BREAKDOWN.md` as one work session: read the phase's
  agentic prompt, implement only that phase's scope, run its verification conditions,
  then stop and report before moving to the next phase.
- Prefer small, verifiable diffs over large multi-file rewrites — each phase's stop
  condition is meant to be checkable after a small increment of work.
- When running shell commands (`docker compose up`, `pytest`, `python scripts/ingest.py`,
  `python scripts/run_eval.py`), surface the actual output rather than summarizing away
  a failure.
- Do not modify files under `data/`, `indexes/`, or `corpus/` by hand — regenerate them
  via `scripts/ingest.py` so they stay reproducible (Hard Constraint: determinism).
- If a task would require violating a Hard Constraint in `AGENTS.md` §2 (e.g. reaching
  for a web search to answer a factual question, or hardcoding a benchmark string),
  stop and flag it instead of proceeding.
