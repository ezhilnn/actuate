"""Memory storage vs retrieval, plus a correction learning graph.

The graph records successful (prompt → revision, score) edges so later
runs can retrieve similar trajectories — graph structure for accuracy,
not a second orchestration engine.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from actuate.domain.signals import MemoryRecord


def _embed(text: str) -> list[float]:
    """Tiny hashed bag-of-words embedding so memory works without extra deps.

    MD5 (not `hash()`) so embeddings stay stable across process restarts / Postgres.
    """

    vector = [0.0] * 64
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:2], "big") % 64] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._rows: list[tuple[MemoryRecord, list[float]]] = []

    async def put(self, record: MemoryRecord, *, embedding: list[float]) -> None:
        self._rows.append((record, embedding))

    async def count(self) -> int:
        return len(self._rows)

    def rows(self) -> list[tuple[MemoryRecord, list[float]]]:
        return list(self._rows)


class CosineMemoryRetriever:
    def __init__(self, store: InMemoryVectorStore) -> None:
        self.store = store

    async def recall(self, query: str, *, top_k: int = 5) -> list[MemoryRecord]:
        query_vec = _embed(query)
        ranked = sorted(
            ((_cosine(query_vec, emb), record) for record, emb in self.store.rows()),
            key=lambda item: item[0],
            reverse=True,
        )
        return [record for score, record in ranked[:top_k] if score > 0]


class LearningGraph:
    """Directed graph of successful corrections used as a retrieval index."""

    def __init__(self, store: InMemoryVectorStore) -> None:
        self.store = store

    async def record_success(self, *, prompt: str, revision: str, score: float) -> None:
        text = f"PROMPT: {prompt[:500]}\nREVISION: {revision[:500]}\nSCORE: {score:.3f}"
        record = MemoryRecord(text=text, score=score, kind="success", metadata={"revision": revision})
        await self.store.put(record, embedding=_embed(prompt))

    async def recall(self, query: str, *, top_k: int = 5) -> list[MemoryRecord]:
        retriever = CosineMemoryRetriever(self.store)
        return await retriever.recall(query, top_k=top_k)


class PostgresBackedVectors:
    """In-process cosine index with a Postgres write-through so recall survives restarts."""

    def __init__(self, sql: Any) -> None:
        self.sql = sql
        self._mem = InMemoryVectorStore()

    async def hydrate(self) -> None:
        if not hasattr(self.sql, "list_memory"):
            return
        for record, embedding in await self.sql.list_memory():
            await self._mem.put(record, embedding=embedding)

    async def put(self, record: MemoryRecord, *, embedding: list[float]) -> None:
        await self.sql.save_memory(
            text=record.text,
            score=record.score,
            kind=record.kind,
            metadata=dict(record.metadata or {}),
            embedding=embedding,
        )
        await self._mem.put(record, embedding=embedding)

    async def count(self) -> int:
        return await self._mem.count()

    def rows(self) -> list[tuple[MemoryRecord, list[float]]]:
        return self._mem.rows()
