"""Compare held-out scorer event classifications with Guru-reviewed labels.

Input predictions are provider outputs joined to human labels by event_id.
This offline report cannot enable production scoring; it measures only the
submitted predictions on the supplied reviewed events.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

LABELS = {"correct", "incorrect", "uncertain"}


def _read_labels(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [{key: (value or "").strip() for key, value in row.items()} for row in rows if any(row.values())]


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _metric_row(rows: list[tuple[str, str]]) -> dict:
    # Gold/predicted labels are correct, incorrect, or uncertain. Model
    # abstentions are excluded from conditional accuracy but reduce coverage.
    determinate = [(gold, pred) for gold, pred in rows if gold in {"correct", "incorrect"}]
    covered = [(gold, pred) for gold, pred in determinate if pred in {"correct", "incorrect"}]
    tp = sum(gold == pred == "incorrect" for gold, pred in covered)
    tn = sum(gold == pred == "correct" for gold, pred in covered)
    fp = sum(gold == "correct" and pred == "incorrect" for gold, pred in covered)
    fn = sum(gold == "incorrect" and pred == "correct" for gold, pred in covered)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * tp, 2 * tp + fp + fn)
    return {
        "determinate_events": len(determinate), "covered_events": len(covered),
        "abstained_events": len(determinate) - len(covered),
        "coverage": _ratio(len(covered), len(determinate)),
        "accuracy_when_covered": _ratio(tp + tn, len(covered)),
        "true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn,
        "precision_incorrect": precision, "recall_incorrect": recall,
        "specificity_correct": _ratio(tn, tn + fp), "f1_incorrect": f1,
    }


def evaluate(labels_path: Path, predictions_path: Path) -> dict:
    labels = _read_labels(labels_path)
    payload = json.loads(predictions_path.read_text(encoding="utf-8"))
    predictions = payload.get("events", [])
    if not isinstance(predictions, list):
        raise ValueError("predictions JSON must contain an events array")
    by_event: dict[str, dict] = {}
    errors: list[str] = []
    for index, prediction in enumerate(predictions, 1):
        event_id = str(prediction.get("event_id", "")).strip()
        if not event_id or event_id in by_event:
            errors.append(f"Prediction row {index}: missing or duplicate event_id")
            continue
        if prediction.get("predicted_label") not in LABELS:
            errors.append(f"Prediction {event_id}: predicted_label must be correct, incorrect, or uncertain")
            continue
        confidence = prediction.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"Prediction {event_id}: confidence must be in [0,1]")
            continue
        by_event[event_id] = prediction

    seen: set[str] = set()
    rows_by_category: dict[str, list[tuple[str, str]]] = defaultdict(list)
    timing_errors: list[tuple[int, int]] = []
    missing_predictions = 0
    for row in labels:
        event_id = row.get("event_id", "")
        if not event_id or event_id in seen:
            errors.append(f"Human labels: missing or duplicate event_id {event_id!r}")
            continue
        seen.add(event_id)
        gold = row.get("label", "")
        category = row.get("issue_category", "unclassified")
        if gold not in LABELS:
            errors.append(f"Human label {event_id}: label must be correct, incorrect, or uncertain")
            continue
        prediction = by_event.get(event_id)
        predicted = prediction.get("predicted_label") if prediction else "uncertain"
        if prediction is None:
            missing_predictions += 1
        rows_by_category[category].append((gold, predicted))
        if prediction is not None:
            try:
                gold_start, gold_end = int(row["start_ms"]), int(row["end_ms"])
                pred_start, pred_end = int(prediction["start_ms"]), int(prediction["end_ms"])
                if gold_start >= 0 and gold_end > gold_start and pred_start >= 0 and pred_end > pred_start:
                    timing_errors.append((abs(gold_start - pred_start), abs(gold_end - pred_end)))
            except (KeyError, TypeError, ValueError):
                pass
    orphan_ids = sorted(set(by_event) - seen)
    if orphan_ids:
        errors.append(f"Predictions contain {len(orphan_ids)} event_id values absent from human labels")

    category_metrics = {category: _metric_row(rows) for category, rows in sorted(rows_by_category.items())}
    all_rows = [item for rows in rows_by_category.values() for item in rows]
    result = {
        "benchmark_status": "invalid" if errors else "completed",
        "provider_id": payload.get("provider_id", "unknown"),
        "provider_version": payload.get("provider_version", "unknown"),
        "score_enabled": False,
        "event_count": len(labels),
        "missing_prediction_count": missing_predictions,
        "overall": _metric_row(all_rows),
        "by_issue_category": category_metrics,
        "timestamp_error_ms": {
            "paired_events": len(timing_errors),
            "start_mae": round(sum(item[0] for item in timing_errors) / len(timing_errors), 2) if timing_errors else None,
            "end_mae": round(sum(item[1] for item in timing_errors) / len(timing_errors), 2) if timing_errors else None,
        },
        "errors": errors,
        "limitations": [
            "This is an offline benchmark on supplied labels, not a validation of label quality or population generalization.",
            "Uncertain human labels are excluded; model abstentions lower coverage and are not counted as correct.",
            "Metrics do not authorize production feedback or lesson unlocks without independent calibration and review.",
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-csv", type=Path, required=True)
    parser.add_argument("--predictions-json", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.labels_csv, args.predictions_json)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["benchmark_status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
