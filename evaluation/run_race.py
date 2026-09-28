"""Run the Agent versus Fixed Workflow race evaluation."""

from __future__ import annotations

import csv
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ollama

import app.agent as agent_module
import app.workflow as workflow_module
# Warm the existing module-level SentenceTransformer and Chroma resources once
# before per-question timing begins. The policy lookup continues to use search().
import app.search as policy_search_module
from app.agent import COST_PER_1K_TOKENS
from evaluation.race_dataset import RACE_DATASET


CSV_PATH = ROOT / "evaluation" / "race.csv"
SUMMARY_PATH = ROOT / "evaluation" / "race_summary.md"


class CallMeter:
    """Measure all model calls for one system using Ollama metadata or one fallback."""

    def __init__(self, original: Callable[..., Any]):
        self.original = original
        self.tokens = 0
        self.calls = 0
        self.usage_source = "none"

    def __call__(self, **kwargs):
        self.calls += 1
        response = self.original(**kwargs)
        prompt_tokens = _response_field(response, "prompt_eval_count")
        completion_tokens = _response_field(response, "eval_count")
        if prompt_tokens is not None and completion_tokens is not None:
            self.usage_source = "ollama_metadata"
            self.tokens += int(prompt_tokens) + int(completion_tokens)
        else:
            self.usage_source = "fallback_estimate"
            request_text = str(kwargs.get("messages", []))
            response_text = _response_content(response)
            self.tokens += max(1, (len(request_text) + len(response_text) + 3) // 4)
        return response

    @property
    def estimated_cost(self) -> float:
        return (self.tokens / 1000) * COST_PER_1K_TOKENS


def _response_field(response: Any, field: str) -> Any:
    if isinstance(response, dict):
        return response.get(field)
    return getattr(response, field, None)


def _response_content(response: Any) -> str:
    if isinstance(response, dict):
        message = response.get("message", {})
        if isinstance(message, dict):
            return str(message.get("content", ""))
    message = getattr(response, "message", None)
    return str(getattr(message, "content", ""))


def _number_present(answer: str, expected: float) -> bool:
    normalized = answer.lower()
    number_words = {
        0: ("zero", "none", "no days"),
        1: ("one",),
        2: ("two",),
        3: ("three",),
        4: ("four",),
        5: ("five",),
        10: ("ten",),
        12: ("twelve",),
        20: ("twenty",),
    }
    if expected == 0:
        # Numeric/explicit zero only — natural-negation phrases are handled by
        # _zero_lapse_present() when the disposition key is lapsed_days.
        return bool(re.search(r"\b0(?:\.0+)?\b|\bzero\b|\bnone\b|\bno days?\b", normalized))
    text = str(int(expected)) if expected.is_integer() else str(expected)
    numeric = bool(re.search(rf"(?<![\d.]){re.escape(text)}(?:\.0+)?(?![\d.])", normalized))
    words = number_words.get(int(expected), ())
    return numeric or any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in words)


# Lapse/expiry/forfeit verbs used in _zero_lapse_present patterns.
_LAPSE_VERBS = r"(?:lapse[sd]?|expire[sd]?|forfeit(?:ed)?)"


def _zero_lapse_present(answer: str) -> bool:
    """Return True when the answer conveys that zero days lapsed/expired/were forfeited.

    Accepts both explicit numeric forms ("0 days lapse", "zero days lapse") and
    natural negative-lapse statements ("does not lapse", "no annual leave lapses").
    Requires lapse/expiry/forfeit semantic context in all branches so that
    isolated occurrences of "no" or "not" in non-lapse sentences are ignored.

    Negative cases that must NOT match:
        "10 days lapse, but this does not affect encashment."
        "5 days can be carried over, but the remaining 10 days lapse."
    """
    normalized = answer.lower()

    # Branch 1 — Explicit numeric zero immediately before a lapse verb.
    explicit_zero = bool(re.search(
        rf"(?:\b0(?:\.0+)?|\bzero|\bnone of \w+ \w+|\bno days?)\b[^.]*?{_LAPSE_VERBS}",
        normalized,
    ))
    if explicit_zero:
        return True

    # Branch 2 — Negative auxiliary immediately before a lapse verb.
    neg_aux = bool(re.search(
        rf"\b(?:does?n'?t|do(?:es)?\s+not|did\s+not|will\s+not|won'?t)\s+{_LAPSE_VERBS}",
        normalized,
    ))
    if neg_aux:
        return True

    # Branch 3 — "no [noun phrase] lapse/expire/forfeit".
    no_noun = bool(re.search(
        rf"\bno\s+(?:\w+\s+){{0,3}}{_LAPSE_VERBS}",
        normalized,
    ))
    if no_noun:
        return True

    return False


def evaluate_answer(case: dict[str, Any], result: dict[str, Any]) -> bool:
    """Require each expected numeric fact and its disposition term in the answer."""
    answer = str(result.get("answer", ""))
    if not answer or result.get("terminated_by_budget"):
        return False
    labels = {
        "carryover_days": ("carry", "carried", "carry-over", "carry over"),
        "encashable_days": ("encash",),
        "lapsed_days": ("lapse", "lapsed", "expire", "forfeit"),
    }

    def _fact_present(key: str, expected: float) -> bool:
        label_hit = any(label in answer.lower() for label in labels[key])
        if key == "lapsed_days" and expected == 0.0:
            return _zero_lapse_present(answer) or (
                _number_present(answer, 0.0) and label_hit
            )
        return _number_present(answer, expected) and label_hit

    return all(_fact_present(key, expected) for key, expected in case["expected"].items())


def _run_one(system_module: Any, question: str) -> tuple[dict[str, Any], CallMeter, float]:
    meter = CallMeter(system_module.ollama.chat)
    original_chat = system_module.ollama.chat
    system_module.ollama.chat = meter
    started = time.monotonic()
    try:
        result = (
            system_module.run_agent(question)
            if system_module is agent_module
            else system_module.run_workflow(question)
        )
    except Exception as error:
        result = {"answer": "", "error": f"{type(error).__name__}: {error}"}
    finally:
        elapsed = time.monotonic() - started
        system_module.ollama.chat = original_chat
    return result, meter, elapsed


def p50(values: list[float]) -> float:
    """Use the median of the ten observations as p50."""
    return statistics.median(values) if values else 0.0


def _row(case: dict[str, Any], agent_run: tuple, workflow_run: tuple) -> dict[str, Any]:
    agent_result, agent_meter, agent_elapsed = agent_run
    workflow_result, workflow_meter, workflow_elapsed = workflow_run
    agent_answer = str(agent_result.get("answer", ""))
    workflow_answer = str(workflow_result.get("answer", ""))
    agent_failed = bool(agent_result.get("error")) or agent_answer.startswith("Agent stopped safely:")
    workflow_failed = bool(workflow_result.get("error")) or workflow_answer.startswith("Workflow stopped:")
    return {
        "id": case["id"],
        "question": case["question"],
        "dependent": case["dependent"],
        "employee_id": case["employee_id"],
        "agent_pass": evaluate_answer(case, agent_result),
        "workflow_pass": evaluate_answer(case, workflow_result),
        "agent_latency_seconds": round(agent_elapsed, 6),
        "workflow_latency_seconds": round(workflow_elapsed, 6),
        "agent_tokens": agent_result.get("tokens_used", agent_meter.tokens),
        "workflow_tokens": workflow_meter.tokens,
        "agent_estimated_cost": round(agent_result.get("estimated_cost", agent_meter.estimated_cost), 9),
        "workflow_estimated_cost": round(workflow_meter.estimated_cost, 9),
        "agent_iterations": agent_result.get("iterations_used", agent_result.get("iteration_count", 0)),
        "agent_termination_reason": agent_result.get("termination_reason", "error" if agent_failed else ""),
        "agent_terminated_by_budget": agent_result.get("terminated_by_budget", False),
        "workflow_status": "failed" if workflow_failed else "completed",
        "agent_error": agent_result.get("error", agent_answer if agent_failed else ""),
        "workflow_error": workflow_result.get("error", workflow_answer if workflow_failed else ""),
        "agent_usage_source": agent_meter.usage_source,
        "workflow_usage_source": workflow_meter.usage_source,
    }


def write_csv(rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0].keys()) if rows else []
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, Any]]) -> None:
    agent_latencies = [float(row["agent_latency_seconds"]) for row in rows]
    workflow_latencies = [float(row["workflow_latency_seconds"]) for row in rows]
    agent_passes = sum(bool(row["agent_pass"]) for row in rows)
    workflow_passes = sum(bool(row["workflow_pass"]) for row in rows)
    agent_tokens = sum(int(row["agent_tokens"]) for row in rows)
    workflow_tokens = sum(int(row["workflow_tokens"]) for row in rows)
    agent_cost = sum(float(row["agent_estimated_cost"]) for row in rows)
    workflow_cost = sum(float(row["workflow_estimated_cost"]) for row in rows)
    dependent = ", ".join(row["id"] for row in rows if row["dependent"])
    text = f"""# Agent vs Fixed Workflow Race

This artifact reports measurements only. Costs are estimated experiment costs at ${COST_PER_1K_TOKENS:.3f} per 1K tokens, not Ollama billing charges. p50 is the median of the ten per-question elapsed observations.

Dependent/branching cases: {dependent}

| Metric | Agent | Fixed Workflow | Questions |
|---|---:|---:|---:|
| Pass rate | {agent_passes}/10 ({agent_passes / 10:.0%}) | {workflow_passes}/10 ({workflow_passes / 10:.0%}) | 10 |
| p50 latency (seconds) | {p50(agent_latencies):.6f} | {p50(workflow_latencies):.6f} | 10 |
| Total tokens | {agent_tokens} | {workflow_tokens} | 10 |
| Estimated cost/question | ${agent_cost / 10:.9f} | ${workflow_cost / 10:.9f} | 10 |

Agent budget terminations: {sum(bool(row['agent_terminated_by_budget']) for row in rows)}

No winner or final verdict is declared in this step.
"""
    SUMMARY_PATH.write_text(text, encoding="utf-8")


def run_race() -> list[dict[str, Any]]:
    print("Initializing shared policy search resources once before timing...")
    _ = policy_search_module.embedding_model
    _ = policy_search_module.collection
    rows = []
    for case in RACE_DATASET:
        print(f"\n[{case['id']}] Agent")
        agent_run = _run_one(agent_module, case["question"])
        print(f"[{case['id']}] Fixed Workflow")
        workflow_run = _run_one(workflow_module, case["question"])
        rows.append(_row(case, agent_run, workflow_run))
    write_csv(rows)
    write_summary(rows)
    return rows


if __name__ == "__main__":
    run_race()
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {SUMMARY_PATH}")
