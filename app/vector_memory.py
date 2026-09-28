from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

DEFAULT_PERSIST_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "agent_memory_chroma"
DEFAULT_COLLECTION_NAME = "agent_memory"


class VectorMemory:
    """Persistent vector memory implemented with ChromaDB and sentence embeddings."""

    def __init__(
        self,
        *,
        persist_directory: str | Path = DEFAULT_PERSIST_DIRECTORY,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model_name: str = "all-MiniLM-L6-v2",
    ):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _build_where_clause(
        self,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        conditions: list[dict[str, str]] = []
        if user_id is not None:
            conditions.append({"user_id": str(user_id)})
        if session_id is not None:
            conditions.append({"session_id": str(session_id)})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def __enter__(self) -> "VectorMemory":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        try:
            if self.collection is not None:
                self.collection = None
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        try:
            if self.client is not None and hasattr(self.client, "close"):
                self.client.close()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        try:
            if self.client is not None:
                self.client = None
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        try:
            if self.embedding_model is not None:
                self.embedding_model = None
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # pragma: no cover - destructor should be best effort only
            pass

    def store_memory(
        self,
        *,
        user_id: str,
        session_id: str,
        text: str,
        memory_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not user_id or not session_id:
            raise ValueError("user_id and session_id are required")
        cleaned = str(text).strip()
        if not cleaned:
            raise ValueError("text must be non-empty")

        memory_id = memory_id or uuid.uuid4().hex
        meta = {
            "user_id": str(user_id),
            "session_id": str(session_id),
            **(metadata or {}),
        }
        self.collection.upsert(
            ids=[memory_id],
            documents=[cleaned],
            metadatas=[meta],
        )
        return memory_id

    def retrieve_relevant_memories(
        self,
        *,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        n_results: int = 3,
    ) -> list[dict[str, Any]]:
        if not str(query).strip():
            return []

        where = self._build_where_clause(user_id=user_id, session_id=session_id)

        embedding = self.embedding_model.encode(str(query)).tolist()
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        final: list[dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for document, metadata, distance in zip(documents, metadatas, distances):
            final.append(
                {
                    "text": document,
                    "metadata": metadata,
                    "distance": float(distance),
                }
            )
        return final

    def delete_memory(self, *, memory_id: str) -> bool:
        if not memory_id:
            return False
        self.collection.delete(ids=[memory_id])
        return True

    def count(self, *, user_id: str | None = None, session_id: str | None = None) -> int:
        where = self._build_where_clause(user_id=user_id, session_id=session_id)
        if where is None:
            return self.collection.count()
        matches = self.collection.get(where=where, include=[])
        return len(matches.get("ids", []))
