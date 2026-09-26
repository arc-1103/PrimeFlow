"""Cross-module contracts. Every field here maps to a concept named explicitly in
docs/CHALLENGE_BREAKDOWN.md — no speculative fields. Grep for a model name across
app/ and tests/ before changing it (AGENTS.md SS4): other tracks build against these.
"""
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Streaming (app/streaming) -------------------------------------------------

class TranscriptChunk(BaseModel):
    """One incremental slice of a live transcript (CHALLENGE_BREAKDOWN.md SSB.1)."""

    session_id: str
    timestamp: float
    transcript_delta: str
    accumulated_transcript: str
    event_type: Literal["chunk", "end"]


# --- Controller (app/controller) -----------------------------------------------

class Decision(str, Enum):
    WAIT = "WAIT"
    RETRIEVE = "RETRIEVE"
    NO_RETRIEVAL = "NO_RETRIEVAL"


class ControllerDecision(BaseModel):
    """Per-chunk WAIT/RETRIEVE/NO_RETRIEVAL call (CHALLENGE_BREAKDOWN.md SSB.2)."""

    decision: Decision
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    timestamp: float


# --- Decomposition (app/decomposition) -----------------------------------------

class SubQuery(BaseModel):
    """One distinct information need split out of a compound utterance
    (CHALLENGE_BREAKDOWN.md SSB.3)."""

    id: str
    query: str
    intent: str
    entities: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


# --- Retrieval / Fusion (app/retrieval, app/fusion) -----------------------------

class RetrievedChunk(BaseModel):
    """A corpus chunk returned by dense/sparse/hybrid search, carrying enough
    provenance to cite as [doc_id SSsection] (CHALLENGE_BREAKDOWN.md SSB.8)."""

    chunk_id: str
    doc_id: str
    section: str | None = None
    page: int | None = None
    text: str
    score: float
    source: Literal["dense", "sparse", "hybrid"]


# --- Session / Synthesis (app/session, app/synthesis) ---------------------------

class Claim(BaseModel):
    """One factual statement in an answer, with its grounding status
    (CHALLENGE_BREAKDOWN.md SSB.8-9)."""

    text: str
    citation: str | None = None  # "[Doc_ID SSSection]" — only set if grounded
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    uncertain: bool = False
    uncertainty_reason: str | None = None


class AnswerVersion(BaseModel):
    """One version of a session's answer (CHALLENGE_BREAKDOWN.md SSB.5-6, Example 2)."""

    session_id: str
    version: int
    claims: list[Claim]
    citations: list[str] = Field(default_factory=list)
    supporting_chunks: list[str] = Field(default_factory=list)
    changed_claims: list[str] = Field(default_factory=list)
    unchanged_claims: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    timestamp: float


# --- Telemetry (app/telemetry) --------------------------------------------------

class TelemetryEvent(BaseModel):
    """One structured, replayable pipeline event (CHALLENGE_BREAKDOWN.md SSB.10, G6)."""

    timestamp: float
    session_id: str
    event_type: str
    transcript_chunk: TranscriptChunk | None = None
    controller_decision: ControllerDecision | None = None
    retrieval_trigger: bool | None = None
    query: str | None = None
    subqueries: list[SubQuery] = Field(default_factory=list)
    retrieved_document_ids: list[str] = Field(default_factory=list)
    retrieval_latency_ms: float | None = None
    rerank_latency_ms: float | None = None
    answer_version: int | None = None
    citation_ids: list[str] = Field(default_factory=list)
    token_count: int | None = None
    uncertainty: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
