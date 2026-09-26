"""BM25 sparse retriever (rank_bm25) -- no custom TF-IDF/BM25 implementation
(AGENTS.md SS3).
"""
import json
import pickle
import re

from rank_bm25 import BM25Okapi

from app.config import settings
from app.retrieval.base import Retriever
from app.schemas import RetrievedChunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Shared tokenizer -- must match between index build (ingest.py) and query
    time, or BM25 scores are meaningless."""
    return _TOKEN_RE.findall(text.lower())


def build_bm25(texts: list[str]) -> BM25Okapi:
    return BM25Okapi([tokenize(t) for t in texts])


class SparseRetriever(Retriever):
    def __init__(self, bm25_index_path: str | None = None, chunks_path: str | None = None):
        bm25_index_path = bm25_index_path or settings.bm25_index_path
        chunks_path = chunks_path or settings.chunks_path

        # Trusted: bm25.pkl is a build artifact regenerated locally by
        # scripts/ingest.py, never user-supplied input.
        with open(bm25_index_path, "rb") as f:
            payload = pickle.load(f)
        self._bm25: BM25Okapi = payload["bm25"]
        self._chunk_ids: list[str] = payload["chunk_ids"]

        self._chunks_by_id: dict[str, dict] = {}
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                self._chunks_by_id[record["chunk_id"]] = record

    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        for i in ranked:
            if scores[i] <= 0:
                continue
            record = self._chunks_by_id[self._chunk_ids[i]]
            results.append(RetrievedChunk(**record, score=float(scores[i]), source="sparse"))
        return results
