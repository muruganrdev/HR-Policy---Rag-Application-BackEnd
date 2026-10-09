import logging

import pytest
from fastapi.testclient import TestClient

from app import rag
from app.main import app
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


def test_ask_logs_generation_exception_without_exposing_it(monkeypatch, caplog):
    monkeypatch.setattr(rag, "preprocess_question", lambda question: question)
    monkeypatch.setattr(rag, "rewrite_question", lambda question: question)
    monkeypatch.setattr(rag, "expand_query", lambda question: question)
    monkeypatch.setattr(
        rag.embedding_model,
        "encode",
        lambda _question: type("Embedding", (), {"tolist": lambda self: [0.1, 0.2]})(),
    )
    monkeypatch.setattr(
        rag.collection,
        "query",
        lambda **_kwargs: {
            "documents": [["A policy statement."]],
            "metadatas": [[{"source": "policy.pdf", "chunk_index": 0}]],
            "distances": [[0.1]],
        },
    )
    monkeypatch.setattr(
        rag,
        "rerank_documents",
        lambda _question, documents, metadatas, distances: (documents, metadatas, distances),
    )

    def fail_generation(**_kwargs):
        raise RuntimeError("private model allocation details")

    monkeypatch.setattr(rag.ollama, "chat", fail_generation)
    caplog.set_level(logging.ERROR, logger="app.rag")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/ask", json={"question": "What does the policy state?"})

    assert response.status_code == 500
    assert "private model allocation details" not in response.text
    assert "Traceback" not in response.text
    assert "RAG pipeline failed at stage=llm_generation" in caplog.text
    assert "private model allocation details" in caplog.text
