import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSHEET_PATH = ROOT / "evaluation" / "blind_labeling.json"
LABELS_PATH = ROOT / "evaluation" / "labels_27.json"
METADATA_PATH = ROOT / "evaluation" / "blind_labeling_metadata.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_blind_worksheet_has_only_repository_cases_and_no_judge_output():
    worksheet = load_json(WORKSHEET_PATH)
    dataset_namespace = {}
    exec((ROOT / "evaluation" / "evaluation_dataset.py").read_text(encoding="utf-8"), dataset_namespace)
    dataset = dataset_namespace["EVALUATION_DATASET"]

    assert len(worksheet) == 27
    expected_ids = [f"Q{item['id']}" for item in dataset]
    ids = [case["id"] for case in worksheet]
    assert ids == expected_ids
    assert len(ids) == len(set(ids))

    required_fields = {"id", "taxonomy_mode", "question", "answer", "context", "human_label", "human_reason"}
    forbidden_fields = {"verdict", "reason", "judge_verdict", "judge_reason", "score", "confidence", "agreement"}

    for case in worksheet:
        assert required_fields <= case.keys()
        assert case["id"]
        assert case["taxonomy_mode"]
        assert case["question"]
        assert case["human_label"] is None
        assert case["human_reason"] is None
        assert not forbidden_fields.intersection(case)


def test_label_template_is_unassigned():
    labels = load_json(LABELS_PATH)
    assert len(labels) == 27
    assert len({item["id"] for item in labels}) == 27
    assert all(item["human_label"] is None for item in labels)
    assert all(item["human_reason"] is None for item in labels)


def test_metadata_marks_pre_judge_stage():
    metadata = load_json(METADATA_PATH)
    assert metadata == {
        "stage": "human_labeling_pre_judge",
        "cases": 27,
        "judge_v1_executed": False,
        "human_labels_completed": False,
    }
