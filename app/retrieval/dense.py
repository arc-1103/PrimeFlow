"""FAISS + sentence-transformers dense retriever -- no custom ANN index
(AGENTS.md SS3).
"""
import json

import faiss
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.retrieval.base import Retriever
from app.schemas import RetrievedChunk


class DenseRetriever(Retriever):
    def __init__(
        self,
        faiss_index_path: str | None = None,
        chunks_path: str | None = None,
        model_name: str | None = None,
    ):
        faiss_index_path = faiss_index_path or settings.faiss_index_path
        chunks_path = chunks_path or settings.chunks_path
        model_name = model_name or settings.embedding_model_name

        self._index = faiss.read_index(faiss_index_path)
        self._model = SentenceTransformer(model_name)

        self._chunk_order: list[dict] = []
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                self._chunk_order.append(json.loads(line))

    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        query_vec = self._model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        scores, indices = self._index.search(query_vec.astype("float32"), top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            record = self._chunk_order[idx]
            results.append(RetrievedChunk(**record, score=float(score), source="dense"))
        return results
