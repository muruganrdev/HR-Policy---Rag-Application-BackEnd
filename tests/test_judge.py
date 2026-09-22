import json

import pytest

from evaluation.judge import judge_answer


class FakeOllamaResponse:
    def __init__(self, payload):
        self.payload = payload

    def get(self, key, default=None):
        return self.payload.get(key, default)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeTypedOllamaResponse:
    def __init__(self, content):
        self.message = FakeMessage(content)


@pytest.fixture
def mock_ollama(monkeypatch):
    calls = []

    def fake_chat(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return calls[-1]["kwargs"].get("mock_response", {"message": {"content": '{"verdict": "PASS", "reason": "ok"}'}})

    monkeypatch.setattr("evaluation.judge.ollama.chat", fake_chat)
    return calls


def test_judge_pass(mock_ollama):
    mock_ollama[0:0]
    response = {
        "message": {
            "content": '{"verdict": "PASS", "reason": "The answer matches the policy context."}'
        }
    }
    import evaluation.judge as judge_module
    judge_module.ollama.chat = lambda *args, **kwargs: response

    result = judge_answer("How much annual leave do employees get?", "Employees get 20 working days.", "Annual leave is 20 working days per calendar year.")
    assert result == {"verdict": "PASS", "reason": "The answer matches the policy context."}


def test_judge_fail(mock_ollama):
    import evaluation.judge as judge_module
    judge_module.ollama.chat = lambda *args, **kwargs: {
        "message": {"content": '{"verdict": "FAIL", "reason": "The answer is unsupported."}' }
    }

    result = judge_answer("How much annual leave do employees get?", "Employees get 30 days.", "Annual leave is 20 working days per calendar year.")
    assert result == {"verdict": "FAIL", "reason": "The answer is unsupported."}


def test_judge_accepts_typed_ollama_response(monkeypatch):
    monkeypatch.setattr(
        "evaluation.judge.ollama.chat",
        lambda *args, **kwargs: FakeTypedOllamaResponse(
            '{"verdict": "PASS", "reason": "The answer is supported."}'
        ),
    )

    result = judge_answer("Q", "A", "Context")

    assert result == {"verdict": "PASS", "reason": "The answer is supported."}


def test_judge_accepts_invalid_apostrophe_escape_from_ollama(monkeypatch):
    monkeypatch.setattr(
        "evaluation.judge.ollama.chat",
        lambda *args, **kwargs: {
            "message": {
                "content": (
                    '{"verdict": "FAIL", "reason": "The user\\\'s answer is not supported."}'
                )
            }
        },
    )

    result = judge_answer("Q", "A", "Context")

    assert result == {"verdict": "FAIL", "reason": "The user's answer is not supported."}


def test_judge_accepts_q23_style_truncated_json(monkeypatch):
    q23_response = """{
    "verdict": "PASS",
    "reason": "The answer correctly addresses the user\\'s question and is supported by the context in the \\'Confidentiality and Data Protection\\' section, which states that the NDA obligation continues for 2 years post-employment."
    """
    monkeypatch.setattr(
        "evaluation.judge.ollama.chat",
        lambda *args, **kwargs: {"message": {"content": q23_response}},
    )

    result = judge_answer("Q23", "The NDA continues for 2 years.", "NDA continues for 2 years post-employment.")

    assert result["verdict"] == "PASS"
    assert "user's question" in result["reason"]
    assert "2 years post-employment" in result["reason"]


def test_judge_rejects_ambiguous_truncated_json(monkeypatch):
    monkeypatch.setattr(
        "evaluation.judge.ollama.chat",
        lambda *args, **kwargs: {
            "message": {"content": '{"verdict": "PASS", "reason": "incomplete]'}
        },
    )

    result = judge_answer("Q", "A", "Context")

    assert result == {"verdict": "FAIL", "reason": "Judge returned an invalid response."}


def test_invalid_json_response(monkeypatch):
    def fake_chat(*args, **kwargs):
        return {"message": {"content": "not-json"}}

    monkeypatch.setattr("evaluation.judge.ollama.chat", fake_chat)

    result = judge_answer("Q", "A", "Context")
    assert result == {"verdict": "FAIL", "reason": "Judge returned an invalid response."}


def test_invalid_verdict_response(monkeypatch):
    def fake_chat(*args, **kwargs):
        return {"message": {"content": '{"verdict": "MAYBE", "reason": "bad"}'}}

    monkeypatch.setattr("evaluation.judge.ollama.chat", fake_chat)

    result = judge_answer("Q", "A", "Context")
    assert result == {"verdict": "FAIL", "reason": "Judge returned an invalid response."}


def test_v3_summary_formatting_keeps_disagreement_ids_separate_from_mode_counts():
    import evaluation.run_judge_v3 as runner

    lines = runner.build_summary_lines(
        total=27,
        agreement_count=24,
        disagreement_ids=["Q3", "Q6", "Q28"],
        mode_counts={"exact_fact": 1},
        mode_agreements={"exact_fact": 1},
        mode_disagreements={"exact_fact": 0},
    )

    text = "\n".join(lines)
    assert "## Disagreement IDs" in text
    assert "Q3, Q6, Q28" in text
    assert "exact_fact: cases=1, agreements=1, disagreements=0, agreement_pct=100.00%" in text


def test_ollama_exception(monkeypatch):
    def fake_chat(*args, **kwargs):
        raise RuntimeError("ollama unavailable")

    monkeypatch.setattr("evaluation.judge.ollama.chat", fake_chat)

    result = judge_answer("Q", "A", "Context")
    assert result == {"verdict": "FAIL", "reason": "Judge execution failed."}
