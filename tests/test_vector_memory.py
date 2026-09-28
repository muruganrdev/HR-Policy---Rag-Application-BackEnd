import gc
import tempfile
from pathlib import Path

from app.vector_memory import VectorMemory


def _close_memory(memory: VectorMemory) -> None:
    memory.close()
    gc.collect()


def test_vector_memory_stores_and_retrieves_semantic_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = VectorMemory(persist_directory=Path(tmpdir) / "vector_memory_store")
        try:
            memory.store_memory(user_id="u1", session_id="s1", text="Employee 005 has 20 annual leave days and 10 carry-over days.")
            memory.store_memory(user_id="u1", session_id="s1", text="Recruitment onboarding checklist for new staff.")

            hits = memory.retrieve_relevant_memories(query="annual leave carry-over for employee 005", user_id="u1", session_id="s1", n_results=3)
            assert hits
            assert "annual leave" in hits[0]["text"].lower()
            assert memory.count(user_id="u1", session_id="s1") == 2
        finally:
            _close_memory(memory)


def test_vector_memory_keeps_user_and_session_isolation():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = VectorMemory(persist_directory=Path(tmpdir) / "vector_memory_store")
        try:
            memory.store_memory(user_id="u1", session_id="s1", text="User 1 memory")
            memory.store_memory(user_id="u2", session_id="s1", text="User 2 memory")

            hits_u1 = memory.retrieve_relevant_memories(query="user 1 memory", user_id="u1", session_id="s1", n_results=3)
            hits_u2 = memory.retrieve_relevant_memories(query="user 2 memory", user_id="u2", session_id="s1", n_results=3)
            assert hits_u1[0]["text"] == "User 1 memory"
            assert hits_u2[0]["text"] == "User 2 memory"
        finally:
            _close_memory(memory)
