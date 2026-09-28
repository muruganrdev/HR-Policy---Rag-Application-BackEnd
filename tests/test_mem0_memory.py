from pathlib import Path

import pytest

from app import mem0_memory


@pytest.fixture
def local_mem0_config(tmp_path: Path):
    if not mem0_memory.is_mem0_available():
        pytest.skip("mem0ai is not installed")

    from mem0.configs.base import EmbedderConfig, LlmConfig, MemoryConfig, VectorStoreConfig

    return MemoryConfig(
        vector_store=VectorStoreConfig(
            provider="qdrant",
            config={
                "path": str(tmp_path / "qdrant"),
                "collection_name": "mem0_test",
                "embedding_model_dims": 384,
            },
        ),
        llm=LlmConfig(provider="ollama", config={"model": "llama3"}),
        embedder=EmbedderConfig(
            provider="huggingface",
            config={
                "model": "all-MiniLM-L6-v2",
                "model_kwargs": {"local_files_only": True},
            },
        ),
        history_db_path=str(tmp_path / "history.db"),
    )


@pytest.fixture(autouse=True)
def disable_mem0_telemetry(monkeypatch):
    if not mem0_memory.is_mem0_available():
        return

    from mem0.memory import main as mem0_main
    from mem0.memory import telemetry as mem0_telemetry

    monkeypatch.setattr(mem0_main, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(mem0_telemetry, "MEM0_TELEMETRY", False)


@pytest.fixture
def mem0_client(local_mem0_config):
    client = mem0_memory.Mem0MemoryClient(
        user_id="test-user", session_id="test-run", config=local_mem0_config
    )
    try:
        yield client
    finally:
        client.close()


def test_mem0_runtime_status_is_reported():
    assert isinstance(mem0_memory.get_mem0_status(), str)
    assert isinstance(mem0_memory.is_mem0_available(), bool)


def test_real_mem0_add_and_semantic_search(mem0_client):
    added = mem0_client.add("I prefer email communication.", infer=False)
    hits = mem0_client.search("How should I be contacted?", top_k=3)

    assert added["results"]
    assert any("email" in result["memory"].lower() for result in added["results"])
    assert hits
    assert any("email" in result["memory"].lower() for result in hits)
    assert all(result["user_id"] == "test-user" for result in hits)
    assert all(result["run_id"] == "test-run" for result in hits)


def test_real_mem0_search_isolates_users_and_runs(mem0_client):
    mem0_client.add(
        "I prefer email communication.", user_id="user-a", session_id="run-1", infer=False
    )
    mem0_client.add(
        "I prefer phone calls.", user_id="user-b", session_id="run-1", infer=False
    )
    mem0_client.add(
        "I work remotely.", user_id="user-a", session_id="run-2", infer=False
    )

    email_hits = mem0_client.search(
        "How should I be contacted?", user_id="user-a", session_id="run-1", top_k=5
    )
    phone_hits = mem0_client.search(
        "How should I be contacted?", user_id="user-b", session_id="run-1", top_k=5
    )

    assert email_hits
    assert any("email" in result["memory"].lower() for result in email_hits)
    assert all(result["user_id"] == "user-a" and result["run_id"] == "run-1" for result in email_hits)
    assert all("phone" not in result["memory"].lower() for result in email_hits)
    assert phone_hits
    assert any("phone" in result["memory"].lower() for result in phone_hits)
    assert all(result["user_id"] == "user-b" and result["run_id"] == "run-1" for result in phone_hits)
    assert all("email" not in result["memory"].lower() for result in phone_hits)


def test_real_mem0_retrieves_multiple_topics(mem0_client):
    memories = (
        "I work in the Engineering department.",
        "I prefer email communication.",
        "I usually work remotely.",
    )
    for memory in memories:
        mem0_client.add(memory, infer=False)

    queries = (
        ("Which department do I work in?", "engineering"),
        ("How should I be contacted?", "email"),
        ("Where do I usually work?", "remotely"),
    )
    for query, expected in queries:
        hits = mem0_client.search(query, top_k=3)
        assert hits
        assert any(expected in result["memory"].lower() for result in hits)


def test_real_mem0_persists_across_client_instances(local_mem0_config):
    first = mem0_memory.Mem0MemoryClient(
        user_id="persistent-user", session_id="persistent-run", config=local_mem0_config
    )
    first.add("I prefer email communication.", infer=False)
    first.close()

    reopened = mem0_memory.Mem0MemoryClient(
        user_id="persistent-user", session_id="persistent-run", config=local_mem0_config
    )
    try:
        hits = reopened.search("How should I be contacted?", top_k=3)
        assert hits
        assert any("email" in result["memory"].lower() for result in hits)
    finally:
        reopened.close()


def test_mem0_configuration_error_is_clear(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MEM0_API_KEY", "hosted-mem0-key-is-not-an-openai-key")
    if mem0_memory.is_mem0_available():
        with pytest.raises(mem0_memory.Mem0ConfigError, match="OPENAI_API_KEY"):
            mem0_memory.Mem0MemoryClient()
    else:
        with pytest.raises(mem0_memory.Mem0UnavailableError):
            mem0_memory.Mem0MemoryClient()
