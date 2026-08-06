from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CompetitionConfig, ROOT
from ..io import find_column, is_missing, read_table, utc_now, write_json_copies
from ..lineage import metadata


def _match_ids(frame: pd.DataFrame) -> set[int]:
    if frame.empty:
        return set()
    column = find_column(frame, "jogo", "match_id")
    if not column:
        return set()
    values = pd.to_numeric(frame[column], errors="coerce").dropna().astype(int)
    return set(values.tolist())


def _coverage_for_dataset(config: CompetitionConfig, dataset_name: str, field: str, all_ids: set[int]) -> tuple[set[int], str]:
    if dataset_name == "configuration":
        return set(all_ids), "competition metadata is configured"
    try:
        path = config.dataset(dataset_name)
    except KeyError:
        return set(), "dataset is not configured"
    if not path.exists():
        return set(), f"dataset does not exist: {path.relative_to(ROOT)}"
    frame = read_table(path, required=False)
    if frame.empty:
        return set(), f"dataset is empty: {path.relative_to(ROOT)}"
    if dataset_name == "results":
        status = find_column(frame, "status_real", "status")
        score1 = find_column(frame, "gols1_real", "gols1", "home_score")
        score2 = find_column(frame, "gols2_real", "gols2", "away_score")
        id_col = find_column(frame, "jogo", "match_id")
        if not id_col:
            return set(), "results dataset has no match identifier"
        valid = frame.copy()
        if status:
            valid = valid[valid[status].astype(str).str.strip().isin(config.data.get("final_statuses", ["Finalizado"]))]
        if score1 and score2:
            valid = valid[~valid[score1].map(is_missing) & ~valid[score2].map(is_missing)]
            numeric1 = pd.to_numeric(valid[score1], errors="coerce")
            numeric2 = pd.to_numeric(valid[score2], errors="coerce")
            valid = valid[numeric1.notna() & numeric2.notna()]
        return _match_ids(valid), "validated final scores"
    id_col = find_column(frame, "jogo", "match_id")
    if not id_col:
        return set(), "provider dataset has no match identifier"
    valid = frame.copy()
    if field == "date":
        value_col = find_column(valid, "data", "date", "datetime_utc")
        if not value_col:
            return set(), "matches dataset has no date field"
        parsed = pd.to_datetime(valid[value_col], errors="coerce")
        valid = valid[~valid[value_col].map(is_missing) & parsed.notna()]
    elif field == "minutes":
        value_col = find_column(valid, "minutes", "minutos")
        if not value_col:
            return set(), "player statistics dataset has no minutes field"
        valid = valid[~valid[value_col].map(is_missing)]
    elif field == "performance":
        performance_cols = [find_column(valid, name) for name in ["rating", "goals", "gols", "assists", "assistencias", "shots", "finalizacoes", "xg", "xa"]]
        performance_cols = [col for col in performance_cols if col]
        if not performance_cols:
            return set(), "player statistics dataset has no performance fields"
        mask = pd.Series(False, index=valid.index)
        for col in performance_cols:
            mask = mask | ~valid[col].map(is_missing)
        valid = valid[mask]
    elif field in {"lineup", "participation"}:
        player_col = find_column(valid, "player_name", "jogador", "athlete")
        if player_col:
            valid = valid[~valid[player_col].map(is_missing)]
    return _match_ids(valid), "match identifiers found in provider dataset with field-level validation"


def run(config: CompetitionConfig) -> dict[str, Any]:
    matches_path = config.dataset("matches")
    matches = read_table(matches_path)
    all_ids = _match_ids(matches)
    if not all_ids:
        raise ValueError("No match IDs were found in the configured matches dataset")

    queue: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for entity, checks in config.data.get("required_data", {}).items():
        for check in checks:
            field = str(check["field"])
            provider = str(check.get("provider_dataset", ""))
            covered_ids, note = _coverage_for_dataset(config, provider, field, all_ids)
            affected = sorted(all_ids - covered_ids)
            if entity == "teams" and check.get("derivable") and config.dataset("results").exists():
                affected = []
                note = "derivable from historical results"
            singular = {"matches": "match", "teams": "team", "players": "player"}.get(entity, entity)
            item = {
                "entity": singular,
                "missing_field": field,
                "priority": check.get("priority", "medium"),
                "provider_dataset": provider,
                "total_matches": len(all_ids),
                "covered_matches": len(all_ids) - len(affected),
                "coverage_ratio": round((len(all_ids) - len(affected)) / len(all_ids), 6),
                "note": note,
            }
            coverage.append(item)
            if affected:
                queue.append({
                    "queue_id": f"{config.competition_id}:{entity}:{field}",
                    "competition_id": config.competition_id,
                    "entity": item["entity"],
                    "missing_field": field,
                    "priority": item["priority"],
                    "provider_dataset": provider,
                    "affected_count": len(affected),
                    "entity_ids": affected,
                    "entity_ids_truncated": False,
                    "status": "OPEN",
                    "created_at": utc_now(),
                })

    queue_path = config.scoped_path("data", "queues", "missing_data.json")
    queue_alias = ROOT / "data" / "queues" / "missing_data.json"
    report_path = config.scoped_path("reports", "data_completeness_report.json")
    report_alias = ROOT / "reports" / "data_completeness_report.json"
    payload = metadata("01_data_completeness", config.competition_id, [matches_path, config.dataset("results")], ROOT, {
        "summary": {
            "matches_evaluated": len(all_ids),
            "requirements_evaluated": len(coverage),
            "open_queue_items": len(queue),
            "missing_records_aggregated": sum(item["affected_count"] for item in queue),
            "priority_counts": dict(Counter(item["priority"] for item in queue)),
        },
        "coverage": coverage,
        "queue_path": queue_path.relative_to(ROOT).as_posix(),
    })
    write_json_copies({"generated_at": utc_now(), "competition_id": config.competition_id, "items": queue}, queue_path, queue_alias)
    write_json_copies(payload, report_path, report_alias)
    return payload
