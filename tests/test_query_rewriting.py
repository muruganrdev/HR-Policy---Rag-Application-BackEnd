import pytest
from app.rag import ask_question

@pytest.mark.parametrize("question,expected_keywords", [
    ("What are the progressive steps in the company disciplinary process?", ["Verbal Warning", "Written Warning", "PIP", "Termination"]),
    ("What are the progresive steps in the company disciplinry process?", ["Verbal Warning", "Written Warning", "PIP", "Termination"]),
])
def test_query_rewriting_and_answer(question, expected_keywords):
    result = ask_question(question)
    assert "answer" in result
    answer = result["answer"].lower()
    for kw in expected_keywords:
        assert kw.lower() in answer

def test_intent_preservation():
    question = "What is the notice period for Grade 4-6 employees?"
    result = ask_question(question)
    assert "notice period" in result["answer"].lower()
