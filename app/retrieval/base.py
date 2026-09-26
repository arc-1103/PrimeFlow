"""Retriever contract. Pure interface — no implementation lives here.

Track B (controller/decomposition) builds and tests against a mock of this
class without waiting on Track A's real dense/sparse implementations.
"""
from abc import ABC, abstractmethod

from app.schemas import RetrievedChunk


class Retriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        """Return up to top_k chunks relevant to query, ranked best-first."""
        raise NotImplementedError
