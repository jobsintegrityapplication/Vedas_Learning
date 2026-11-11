import csv
import json

from poc.score_pronunciation_benchmark import evaluate


def test_benchmark_reports_confusion_coverage_and_timing_without_enabling_scores(tmp_path):
    labels_path = tmp_path / "labels.csv"
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "issue_category", "label", "start_ms", "end_ms"])
        writer.writeheader()
        writer.writerows([
            {"event_id": "e1", "issue_category": "vowel_length", "label": "incorrect", "start_ms": "100", "end_ms": "500"},
            {"event_id": "e2", "issue_category": "vowel_length", "label": "correct", "start_ms": "600", "end_ms": "900"},
            {"event_id": "e3", "issue_category": "dental_retroflex", "label": "incorrect", "start_ms": "1000", "end_ms": "1500"},
        ])
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps({
        "provider_id": "phonetic-test", "provider_version": "v1", "events": [
            {"event_id": "e1", "predicted_label": "incorrect", "confidence": 0.9, "start_ms": 120, "end_ms": 520},
            {"event_id": "e2", "predicted_label": "incorrect", "confidence": 0.8, "start_ms": 610, "end_ms": 910},
        ],
    }), encoding="utf-8")

    report = evaluate(labels_path, predictions_path)
    assert report["benchmark_status"] == "completed"
    assert report["score_enabled"] is False
    assert report["overall"]["true_positive"] == 1
    assert report["overall"]["false_positive"] == 1
    assert report["overall"]["abstained_events"] == 1
    assert report["overall"]["coverage"] == 0.6667
    assert report["timestamp_error_ms"] == {"paired_events": 2, "start_mae": 15.0, "end_mae": 15.0}


def test_benchmark_rejects_duplicate_prediction_ids(tmp_path):
    labels_path = tmp_path / "labels.csv"
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "issue_category", "label"])
        writer.writeheader()
        writer.writerow({"event_id": "e1", "issue_category": "aspiration", "label": "incorrect"})
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps({"events": [
        {"event_id": "e1", "predicted_label": "incorrect", "confidence": 0.9},
        {"event_id": "e1", "predicted_label": "correct", "confidence": 0.9},
    ]}), encoding="utf-8")

    report = evaluate(labels_path, predictions_path)
    assert report["benchmark_status"] == "invalid"
    assert any("duplicate event_id" in error for error in report["errors"])
    assert report["score_enabled"] is False
