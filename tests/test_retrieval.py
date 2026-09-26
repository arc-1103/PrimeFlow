"""Phase 1 verification (docs/PHASE_BREAKDOWN.md):
a known in-corpus phrase must be retrieved by both DenseRetriever and
SparseRetriever, with a correct, traceable doc_id/section -- and every chunk
in chunks.jsonl must carry a non-null source identifier.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import settings
from app.retrieval.dense import DenseRetriever
from app.retrieval.sparse import SparseRetriever

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def ingested_corpus():
    """Regenerate chunks/indexes from corpus/ before testing -- never hand-edit
    data/ or indexes/ (AGENTS.md, CLAUDE.md)."""
    subprocess.run([sys.executable, "scripts/ingest.py"], cwd=ROOT, check=True)


def test_no_orphan_chunks():
    with open(settings.chunks_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    assert records, "expected at least one chunk from the placeholder corpus"
    for record in records:
        assert record["chunk_id"]
        assert record["doc_id"]
        assert record["text"].strip()


def test_dense_retriever_finds_known_phrase():
    retriever = DenseRetriever()
    results = retriever.retrieve("What is the cancellation refund policy for venue bookings?", top_k=3)
    assert results
    top = results[0]
    assert top.doc_id == "venue_booking_policy"
    assert "cancellation" in top.section.lower()
    assert top.source == "dense"


def test_sparse_retriever_finds_known_phrase():
    retriever = SparseRetriever()
    results = retriever.retrieve("international travel director approval", top_k=3)
    assert results
    top = results[0]
    assert top.doc_id == "travel_reimbursement_policy"
    assert top.source == "sparse"


def test_pdf_chunks_carry_page_numbers():
    with open(settings.chunks_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    pdf_records = [r for r in records if r["doc_id"] == "equipment_policy"]
    assert pdf_records, "expected chunks from the PDF-sourced document"
    assert all(r["page"] is not None for r in pdf_records)


def test_docx_chunks_carry_heading_sections():
    with open(settings.chunks_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    docx_records = [r for r in records if r["doc_id"] == "remote_work_policy"]
    assert docx_records, "expected chunks from the DOCX-sourced document"
    assert any("stipend" in r["section"].lower() for r in docx_records)


def test_sparse_retriever_finds_pdf_sourced_phrase():
    retriever = SparseRetriever()
    results = retriever.retrieve("wireless microphone kit meeting room", top_k=3)
    assert results
    assert results[0].doc_id == "equipment_policy"
    assert results[0].page is not None


def test_dense_and_sparse_agree_on_distinct_topics():
    dense = DenseRetriever()
    sparse = SparseRetriever()
    query = "Pune workshop venue capacity for 30 people"
    dense_docs = {r.doc_id for r in dense.retrieve(query, top_k=3)}
    sparse_docs = {r.doc_id for r in sparse.retrieve(query, top_k=3)}
    assert "venue_booking_policy" in dense_docs
    assert "venue_booking_policy" in sparse_docs
