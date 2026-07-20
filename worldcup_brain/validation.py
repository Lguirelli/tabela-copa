from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .config import TemporalConfig
from .io import atomic_write_json, read_csv, read_json, utc_now
from .temporal import parse_timestamp


def validate(config: TemporalConfig, expect_complete: bool = True) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    timeline = read_csv(config.output("data", "temporal", "matches_timeline.csv"))
    predictions = read_csv(config.output("predictions", "pre_match", "index.csv"), required=False)
    learning = read_csv(config.output("learning", "game_analysis", "index.csv"), required=False)
    ledger = read_csv(config.output("data", "temporal", "prediction_knowledge_ledger.csv"), required=False)

    if len(timeline) != 104:
        issues.append({"severity": "ERROR", "check": "timeline_count", "value": len(timeline)})
    if expect_complete and len(predictions) != 104:
        issues.append({"severity": "ERROR", "check": "prediction_count", "value": len(predictions)})
    if expect_complete and len(learning) != 104:
        issues.append({"severity": "ERROR", "check": "learning_count", "value": len(learning)})
    if not predictions.empty and predictions["match_id"].duplicated().any():
        issues.append({"severity": "ERROR", "check": "duplicate_predictions"})
    if not learning.empty and learning["match_id"].duplicated().any():
        issues.append({"severity": "ERROR", "check": "duplicate_learning"})

    leakage_rows = []
    if not ledger.empty:
        for _, row in ledger.iterrows():
            cutoff = parse_timestamp(row["prediction_cutoff"])
            available = parse_timestamp(row["available_at"])
            if available > cutoff:
                leakage_rows.append({"prediction_match_id": int(row["prediction_match_id"]), "record_id": row["record_id"], "available_at": row["available_at"], "cutoff": row["prediction_cutoff"]})
            if str(row["record_type"]) == "official_result" and int(float(row["record_id"])) == int(row["prediction_match_id"]):
                leakage_rows.append({"prediction_match_id": int(row["prediction_match_id"]), "record_id": row["record_id"], "reason": "current_match_result_used"})
    if leakage_rows:
        issues.append({"severity": "ERROR", "check": "temporal_leakage", "rows": leakage_rows[:20], "count": len(leakage_rows)})

    knockout_visibility = []
    for _, row in timeline[timeline["match_id"] > 72].iterrows():
        if parse_timestamp(row["fixture_known_at"]) >= parse_timestamp(row["prediction_at"]):
            # Equality is valid; greater means the scheduled prediction could not know the teams.
            if parse_timestamp(row["fixture_known_at"]) > parse_timestamp(row["prediction_at"]):
                knockout_visibility.append(int(row["match_id"]))
    if knockout_visibility:
        issues.append({"severity": "ERROR", "check": "knockout_fixture_not_known_at_prediction", "matches": knockout_visibility})

    versions = sorted(config.output("models", "versions").glob("*.json"))
    cutoffs = []
    for path in versions:
        payload = read_json(path, {})
        if payload.get("training_cutoff"):
            cutoffs.append((path.name, parse_timestamp(payload["training_cutoff"])))
    cutoff_values = [item[1] for item in cutoffs]
    if len(cutoff_values) != len(set(cutoff_values)):
        issues.append({"severity": "ERROR", "check": "duplicate_model_version_cutoff"})

    workflow_names = {
        "01_pre_worldcup_training.yml",
        "02_daily_tournament_simulation.yml",
        "03_post_match_learning.yml",
    }
    workflow_dir = config.output(".github", "workflows")
    missing_workflows = [name for name in workflow_names if not (workflow_dir / name).exists()]
    if missing_workflows:
        issues.append({"severity": "ERROR", "check": "missing_workflows", "files": missing_workflows})
    for name in workflow_names - set(missing_workflows):
        try:
            payload = yaml.load((workflow_dir / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
            if not isinstance(payload, dict) or "jobs" not in payload:
                raise ValueError("jobs missing")
        except Exception as exc:
            issues.append({"severity": "ERROR", "check": "workflow_yaml", "file": name, "error": str(exc)})

    report = {
        "generated_at": utc_now(),
        "status": "VALID" if not any(item["severity"] == "ERROR" for item in issues) else "INVALID",
        "summary": {
            "timeline_matches": len(timeline),
            "predictions": len(predictions),
            "learning_analyses": len(learning),
            "knowledge_records": len(ledger),
            "model_versions": len(versions),
            "issues": len(issues),
        },
        "checks": {
            "no_future_records_in_predictions": not leakage_rows,
            "current_match_result_never_used": not any(row.get("reason") == "current_match_result_used" for row in leakage_rows),
            "knockout_fixture_visibility_valid": not knockout_visibility,
            "workflows_present_and_valid_yaml": not any(item["check"] in {"missing_workflows", "workflow_yaml"} for item in issues),
        },
        "issues": issues,
    }
    atomic_write_json(report, config.output("reports", "temporal_validation_report.json"))
    return report
