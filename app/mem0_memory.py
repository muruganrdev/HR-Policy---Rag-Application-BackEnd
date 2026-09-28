from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import mem0  # type: ignore
except ImportError:  # pragma: no cover - runtime environment guard
    mem0 = None


class Mem0UnavailableError(RuntimeError):
    """Raised when Mem0 is not installed in the current environment."""


class Mem0ConfigError(RuntimeError):
    """Raised when Mem0 runtime configuration is missing."""


def is_mem0_available() -> bool:
    return mem0 is not None


def get_mem0_status() -> str:
    if mem0 is None:
        return "BLOCKED: mem0 package is not installed in the current environment."
    return "AVAILABLE"


class Mem0MemoryClient:
    """Wrapper around the real mem0.Memory runtime.

    The implementation intentionally follows the actual Mem0 package contract:
    - Memory.add accepts messages plus user_id/run_id metadata
    - Memory.search uses filters={"user_id": ..., "run_id": ...}
    - configuration is driven by environment variables and never hard-coded
    """

    def __init__(self, *, user_id: str | None = None, session_id: str | None = None, config: Any | None = None):
        if mem0 is None:
            raise Mem0UnavailableError(
                "Mem0 is not installed. Install the actual 'mem0' package to enable runtime integration."
            )
        self.user_id = user_id
        self.session_id = session_id
        self._config = config or self._build_default_config()
        self._client = mem0.Memory(config=self._config)

    @staticmethod
    def _build_default_config() -> Any:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Mem0ConfigError(
                "The default OpenAI-backed Mem0 configuration requires OPENAI_API_KEY. "
                "Pass an explicit local Mem0 config to use local providers instead."
            )

        data_dir = Path(__file__).resolve().parents[1] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        vector_store = mem0.configs.base.VectorStoreConfig(
            provider="qdrant",
            config={"path": str(data_dir / "mem0_qdrant")},
        )
        llm = mem0.configs.base.LlmConfig(
            provider="openai",
            config={"api_key": api_key},
        )
        embedder = mem0.configs.base.EmbedderConfig(
            provider="openai",
            config={"api_key": api_key},
        )
        return mem0.configs.base.MemoryConfig(
            vector_store=vector_store,
            llm=llm,
            embedder=embedder,
            history_db_path=str(data_dir / "mem0_history.db"),
        )

    def add(
        self,
        text: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        infer: bool = True,
    ) -> dict[str, Any]:
        if not str(text).strip():
            raise ValueError("text must be non-empty")
        resolved_user_id = user_id or self.user_id
        resolved_session_id = session_id or self.session_id
        if not resolved_user_id or not resolved_session_id:
            raise ValueError("user_id and session_id are required")
        return self._client.add(
            [{"role": "user", "content": str(text).strip()}],
            user_id=str(resolved_user_id),
            run_id=str(resolved_session_id),
            metadata=metadata or {},
            infer=infer,
        )

    def search(
        self,
        query: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        if not str(query).strip():
            return []
        resolved_user_id = user_id or self.user_id
        resolved_session_id = session_id or self.session_id
        if not resolved_user_id or not resolved_session_id:
            raise ValueError("user_id and session_id are required")
        response = self._client.search(
            str(query).strip(),
            filters={"user_id": str(resolved_user_id), "run_id": str(resolved_session_id)},
            top_k=top_k,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        return list(results)

    def close(self) -> None:
        """Close Mem0's vector-store clients and release their local file locks."""
        stores = (
            getattr(self._client, "vector_store", None),
            getattr(self._client, "_telemetry_vector_store", None),
        )
        closed_clients: set[int] = set()
        for vector_store in stores:
            client = getattr(vector_store, "client", None)
            close = getattr(client, "close", None)
            if callable(close) and id(client) not in closed_clients:
                close()
                closed_clients.add(id(client))
