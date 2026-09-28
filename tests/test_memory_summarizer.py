from app.memory_summarizer import summarize_conversation


def test_summarize_conversation_exists_and_returns_summary():
    summary = summarize_conversation("User: I need the leave disposition for employee 005. Assistant: We should review policy and leave balance.")
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_summarize_conversation_fallback_on_empty_input():
    summary = summarize_conversation("")
    assert "No conversation content to summarize." in summary
