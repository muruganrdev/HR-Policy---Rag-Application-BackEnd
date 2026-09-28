from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "agent_memory.db"


class LongTermMemory:
    """Persistent local memory backend using SQLite.

    This is intentionally isolated from the production employee database and the
    HR policy vector store. It stores user/session-scoped memories on disk so they
    survive application restarts.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    memory_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_user_session ON memories(user_id, session_id)"
            )
            conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def add_memory(
        self,
        *,
        user_id: str,
        session_id: str,
        memory_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not user_id or not session_id:
            raise ValueError("user_id and session_id are required")
        if not memory_text or not str(memory_text).strip():
            raise ValueError("memory_text must be non-empty")

        memory_id = uuid.uuid4().hex
        now = self._now_iso()
        payload = json.dumps(metadata or {}, sort_keys=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memories (id, user_id, session_id, memory_text, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (memory_id, user_id, session_id, str(memory_text).strip(), now, now, payload),
            )
            conn.commit()
        return memory_id

    def get_memories(
        self,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT id, user_id, session_id, memory_text, created_at, updated_at, metadata_json FROM memories"
        clauses: list[str] = []
        params: list[str] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(str(user_id))
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(str(session_id))

        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC, id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(str(limit))

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            memory_id, stored_user_id, stored_session_id, memory_text, created_at, updated_at, metadata_json = row
            results.append(
                {
                    "memory_id": memory_id,
                    "user_id": stored_user_id,
                    "session_id": stored_session_id,
                    "memory_text": memory_text,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "metadata": json.loads(metadata_json or "{}"),
                }
            )
        return results

    def update_memory(
        self,
        *,
        memory_id: str,
        new_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if not memory_id:
            raise ValueError("memory_id is required")

        updates: list[str] = ["updated_at = ?"]
        params: list[str] = [self._now_iso()]

        if new_text is not None:
            if not str(new_text).strip():
                raise ValueError("new_text must be non-empty")
            updates.append("memory_text = ?")
            params.append(str(new_text).strip())
        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata, sort_keys=True))

        params.append(memory_id)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
        return cursor.rowcount > 0

    def delete_memory(self, *, memory_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
        return cursor.rowcount > 0
