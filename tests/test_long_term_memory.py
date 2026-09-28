from app.long_term_memory import LongTermMemory


def test_long_term_memory_store_retrieve_update_delete(tmp_path):
    db_path = tmp_path / "agent_memory.db"
    memory = LongTermMemory(db_path=db_path)
    memory_id = memory.add_memory(
        user_id="user_1",
        session_id="session_1",
        memory_text="Remember that employee 005 has a 20-day leave balance.",
        metadata={"topic": "annual_leave"},
    )

    rows = memory.get_memories(user_id="user_1", session_id="session_1")
    assert len(rows) == 1
    assert rows[0]["memory_id"] == memory_id
    assert "leave balance" in rows[0]["memory_text"].lower()

    updated = memory.update_memory(memory_id=memory_id, new_text="Remember that employee 005 has a 10-day carry-over limit.")
    assert updated is True

    reopened = LongTermMemory(db_path=db_path)
    reopened_rows = reopened.get_memories(user_id="user_1", session_id="session_1")
    assert reopened_rows[0]["memory_text"] == "Remember that employee 005 has a 10-day carry-over limit."

    assert memory.delete_memory(memory_id=memory_id) is True
    assert memory.get_memories(user_id="user_1", session_id="session_1") == []
