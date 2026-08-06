#!/usr/bin/env python3
"""Reconcile legacy ESPN rows with repository match IDs and quarantine unmapped records."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from sports_engine.config import ROOT, load_competition
from sports_engine.io import find_column, read_table, utc_now, write_json, write_table
from sports_engine.sources import _event_id_map


def _normalized_external_id(value: object) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


def reconcile_file(path: Path, reverse_map: dict[str, int], quarantine: Path | None = None) -> dict[str, int]:
    frame = read_table(path, required=False)
    if frame.empty:
        return {"rows": 0, "mapped": 0, "quarantined": 0}
    match_col = find_column(frame, "jogo", "match_id")
    external_col = find_column(frame, "espn_event_id", "external_event_id")
    if not match_col or not external_col:
        return {"rows": len(frame), "mapped": 0, "quarantined": 0}

    missing = pd.to_numeric(frame[match_col], errors="coerce").isna()
    mapped_count = 0
    for index in frame.index[missing]:
        match_id = reverse_map.get(_normalized_external_id(frame.at[index, external_col]))
        if match_id is not None:
            frame.at[index, match_col] = match_id
            mapped_count += 1

    still_missing = pd.to_numeric(frame[match_col], errors="coerce").isna()
    quarantined_count = int(still_missing.sum())
    if quarantine is not None and quarantined_count:
        rejected = frame[still_missing].copy()
        rejected["validation_status"] = "CONFLICTING_DATA"
        rejected["conflict_reason"] = "External record cannot be tied to a repository match without a validated team/date mapping"
        rejected["quarantined_at"] = utc_now()
        write_table(rejected, quarantine)
        frame = frame[~still_missing].copy()

    numeric = pd.to_numeric(frame[match_col], errors="coerce")
    if numeric.notna().all():
        frame[match_col] = numeric.astype(int)
    write_table(frame, path)
    return {"rows": len(frame) + quarantined_count, "mapped": mapped_count, "quarantined": quarantined_count}


def main() -> int:
    config = load_competition("world_cup_2026")
    source = next(item for item in config.data.get("sources", []) if item.get("type") == "espn_summary")
    event_map = _event_id_map(config, source)
    reverse = {event_id: match_id for match_id, event_id in event_map.items()}
    results = {
        "events": reconcile_file(ROOT / "data/normalized/espn_match_events.csv", reverse),
        "team_match_stats": reconcile_file(
            ROOT / "data/normalized/espn_team_match_stats.csv",
            reverse,
            ROOT / "data/conflicts/unmapped_espn_team_match_stats.csv",
        ),
    }
    report = {
        "generated_at": utc_now(),
        "competition_id": config.competition_id,
        "mapping_source": "data/normalized/espn_matches.csv + data/matches.csv + team aliases",
        "policy": "Only deterministic mappings are applied; unresolved rows are quarantined and marked CONFLICTING_DATA.",
        "results": results,
    }
    write_json(report, ROOT / "reports/external_mapping_cleanup.json")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
