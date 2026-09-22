import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

sys.path.insert(0, str(ROOT))

from evaluation.assertions import (
    assert_policy_section_reference,
    assert_handbook_version_citation,
    assert_notice_period_numeric,
    assert_out_of_jurisdiction_refusal,
)
from evaluation.evaluation_dataset import EVALUATION_DATASET
from evaluation import judge_v2 as judge_module
from app import rag as rag_module
from app.rag import ask_question

DATASET = EVALUATION_DATASET
LABELS = json.loads((BASE / 'labels_27.json').read_text(encoding='utf-8'))
LABEL_BY_ID = {item['id']: item['human_label'] for item in LABELS}

MODE_ORDER = [
    'exact_fact',
    'eligibility_conditions',
    'procedure_application',
    'multi_tier_penalties',
    'calculation_rule',
    'multi_condition_matrix',
    'unanswerable_fallback',
]

# Deterministic results by case.
def run_assertions(answer: str) -> dict:
    return {
        'policy_section_reference': assert_policy_section_reference(answer),
        'handbook_version_citation': assert_handbook_version_citation(answer),
        'notice_period_numeric': assert_notice_period_numeric(answer),
        'out_of_jurisdiction_refusal': assert_out_of_jurisdiction_refusal(answer),
    }

# Evaluate expected 27-case dataset coverage.
def evaluate_dataset(dataset):
    ids = [int(item['id']) for item in dataset]
    expected_ids = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,27,28}
    if set(ids) != expected_ids:
        raise ValueError("Canonical 27-case dataset IDs do not match labels_27.json coverage.")
    return ids


def _extract_context_from_prompt(prompt: str) -> str | None:
    """Returns the context block from a grounded RAG ask_question prompt."""
    if 'Context:\n' not in prompt:
        return None
    if '\n\nUser Question:' not in prompt:
        return None
    if 'Answer:\n' not in prompt:
        return None
    before_question = prompt.split('\n\nUser Question:', 1)[0]
    context = before_question.split('Context:\n', 1)[1]
    return context.strip()


def main():
    ids = evaluate_dataset(DATASET)

    results = []
    errors = []

    for row in DATASET:
        case_id = int(row['id'])
        if case_id == 26:
            continue

        question = row['question']
        mode = row['mode']

        try:
            # Capture the retrieved context only around the RAG execution and then restore
            # the original Ollama chat object before the semantic V2 judge is called.
            original_rag_chat = rag_module.ollama.chat
            current_context = {}

            def chat_capture(model: str, messages: list[dict[str, Any]], options: dict[str, Any] | None = None):
                user_prompt = ''
                for msg in messages:
                    if isinstance(msg, dict) and msg.get('role') == 'user':
                        user_prompt = str(msg.get('content', ''))
                        break

                if 'Context:\n' in user_prompt and '\n\nUser Question:' in user_prompt and 'Answer:\n' in user_prompt:
                    context = _extract_context_from_prompt(user_prompt)
                    if context:
                        current_context['context'] = context

                return original_rag_chat(model=model, messages=messages, options=options)

            rag_module.ollama.chat = chat_capture
            try:
                rag_result = ask_question(question)
            finally:
                rag_module.ollama.chat = original_rag_chat

            answer = str(rag_result.get('answer', ''))
            sources = rag_result.get('sources', [])
            context = current_context.get('context', '')

            judge_result = judge_module.judge_answer(
                question=question,
                answer=answer,
                context=context
            )

            assertions = run_assertions(answer)
            judge = judge_result
            judge_verdict = str(judge.get('verdict', 'FAIL')).upper()
            judge_reason = str(judge.get('reason', 'Judge returned no reason.'))

            results.append({
                'id': f"Q{case_id}",
                'taxonomy_mode': mode,
                'question': question,
                'answer': answer,
                'sources': sources,
                'retrieved_context': context,
                'assertions': assertions,
                'judge_verdict': judge_verdict,
                'judge_reason': judge_reason,
                'human_label': '',
                'agreement': False,
                'error': None,
            })
        except Exception as exc:
            err = {
                'id': f"Q{case_id}",
                'taxonomy_mode': mode,
                'question': question,
                'error': f"{type(exc).__name__}: {str(exc)}",
            }
            errors.append(err)
            results.append({
                'id': f"Q{case_id}",
                'taxonomy_mode': mode,
                'question': question,
                'answer': '',
                'sources': [],
                'retrieved_context': '',
                'assertions': {},
                'judge_verdict': 'FAIL',
                'judge_reason': 'Execution failed before semantic judging could run.',
                'human_label': '',
                'agreement': False,
                'error': f"{type(exc).__name__}: {str(exc)}",
            })

    # Only after the judge verdicts are captured do we read and compare labels.
    label_list = json.loads((BASE / 'labels_27.json').read_text(encoding='utf-8'))
    label_by_id = {item['id']: item['human_label'] for item in label_list}

    agreements = 0
    disagreements = []
    for row in results:
        qid = row['id']
        human_label = label_by_id.get(qid, '').upper()
        row['human_label'] = human_label
        row['agreement'] = row['judge_verdict'].upper() == human_label
        if row['agreement']:
            agreements += 1
        else:
            disagreements.append(row['id'])

    mode_counts = Counter()
    mode_judge_pass = Counter()
    mode_judge_fail = Counter()
    for row in results:
        mode = row['taxonomy_mode']
        mode_counts[mode] += 1
        if row['judge_verdict'].upper() == 'PASS':
            mode_judge_pass[mode] += 1
        else:
            mode_judge_fail[mode] += 1

    print('Mode                         Cases   Pass   Fail   Pass Rate')
    print('-------------------------------------------------------------')
    for mode in MODE_ORDER:
        cases = mode_counts[mode]
        if cases:
            passes = mode_judge_pass[mode]
            fails = mode_judge_fail[mode]
            pct = round((passes / cases) * 100, 2)
            print(f'{mode:<30} {cases:>5} {passes:>5} {fails:>5} {pct:>7}%')
    print('-------------------------------------------------------------')
    total = sum(mode_counts.values())
    total_pass = sum(mode_judge_pass.values())
    total_fail = sum(mode_judge_fail.values())
    print(f'{"TOTAL":<30} {total:>5} {total_pass:>5} {total_fail:>5} {round((total_pass / total) * 100, 2):>7}%')

    print('\nRAG evaluation result: current RAG answers executed via ask_question(question).')
    print('Judge-vs-human agreement: computed after all semantic Judge V2 verdicts are loaded and compared against labels_27.json.')

    judge_pass = sum(1 for row in results if row['judge_verdict'].upper() == 'PASS')
    judge_fail = sum(1 for row in results if row['judge_verdict'].upper() == 'FAIL')
    human_pass = sum(1 for item in label_list if item['human_label'].upper() == 'PASS')
    human_fail = sum(1 for item in label_list if item['human_label'].upper() == 'FAIL')
    agreement_pct = round((agreements / len(results)) * 100, 2) if results else 0.0

    print('\nJudge V2 section:')
    print(f'Judge PASS: {judge_pass}')
    print(f'Judge FAIL: {judge_fail}')
    print(f'Human/reference PASS: {human_pass}')
    print(f'Human/reference FAIL: {human_fail}')
    print(f'Agreement: {agreements}/{len(results)}')
    print(f'Agreement %: {agreement_pct:.2f}%')

    if errors:
        print('\nExecution failures:')
        for e in errors:
            print(f"{e['id']} [{e['taxonomy_mode']}]: {e['error']}")

    artifact = {
        'total_cases': len(results),
        'mode_counts': dict(mode_counts),
        'mode_judge_pass': dict(mode_judge_pass),
        'mode_judge_fail': dict(mode_judge_fail),
        'agreement': {
            'agreements': agreements,
            'disagreements': len(disagreements),
            'agreement_percentage': agreement_pct,
            'disagreement_ids': disagreements,
        },
        'cases': results,
        'errors': errors,
    }
    (BASE / 'week6_eval_results.json').write_text(json.dumps(artifact, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
