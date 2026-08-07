from __future__ import annotations

import os
from typing import Any

import pandas as pd

from sports_engine.config import load_competition
from sports_engine.loops import enrichment

from .config import TemporalConfig
from .io import atomic_write_json, read_csv, read_json, utc_now
from .temporal import parse_timestamp


FIELD_DATASETS = {
    "confirmed_lineup": ("lineups", ("available_at", "source_collected_at")),
    "player_availability": ("player_availability", ("available_at", "source_collected_at", "observation_date")),
    "archived_news": ("archived_news", ("published_at",)),
    "referee": ("match_officials", ("available_at", "source_collected_at")),
    "weather": ("pre_match_weather", ("available_at",)),
    "travel": (None, ()),
}


def _has_historical_record(config: TemporalConfig, field: str, required_before: Any, match_id: int, cache: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    mapping = FIELD_DATASETS.get(field)
    if not mapping or not mapping[0]:
        return False, "NO_CONFIGURED_PROVIDER"
    dataset_name, time_columns = mapping
    if dataset_name not in cache:
        cache[dataset_name] = read_csv(config.path(dataset_name), required=False)
    frame = cache[dataset_name]
    if frame.empty:
        return False, "SOURCE_EMPTY"
    cutoff = parse_timestamp(required_before)
    time_col = next((column for column in time_columns if column in frame.columns), None)
    if not time_col:
        return False, "MISSING_PUBLISHED_AT"
    timestamps = pd.to_datetime(frame[time_col], utc=True, errors="coerce")
    eligible = frame[timestamps <= cutoff]
    match_col = next((column for column in ("match_id", "jogo") if column in eligible.columns), None)
    if match_col:
        eligible = eligible[pd.to_numeric(eligible[match_col], errors="coerce") == match_id]
    return (not eligible.empty, "HISTORICAL_RECORD_FOUND" if not eligible.empty else "NO_RECORD_BEFORE_CUTOFF")


def collect_missing(config: TemporalConfig, as_of: Any | None = None, allow_network: bool = False) -> dict[str, Any]:
    queue_path = config.output("data", "temporal", "missing_information_queue.json")
    queue = read_json(queue_path, {"items": []}) or {"items": []}
    cutoff = parse_timestamp(as_of) if as_of else pd.Timestamp.now(tz="UTC")
    network_result: dict[str, Any] | None = None
    if allow_network:
        # The existing enrichment module may collect current/post-match public facts.
        # It is never allowed to backdate a record into a historical pre-match snapshot.
        previous = os.getenv("SPORTS_ENGINE_NETWORK")
        os.environ["SPORTS_ENGINE_NETWORK"] = "1"
        try:
            network_result = enrichment.run(load_competition(str(config.get("competition_id"))))
        finally:
            if previous is None:
                os.environ.pop("SPORTS_ENGINE_NETWORK", None)
            else:
                os.environ["SPORTS_ENGINE_NETWORK"] = previous

    log_items = []
    resolved = 0
    dataset_cache: dict[str, pd.DataFrame] = {}
    for item in queue.get("items", []):
        required_before = item.get("required_before", cutoff.isoformat())
        if parse_timestamp(required_before) > cutoff:
            log_items.append({**item, "collection_status": "NOT_DUE", "checked_at": cutoff.isoformat()})
            continue
        match_id = int(item.get("entity_id", 0)) if str(item.get("entity_id", "")).isdigit() else 0
        found, reason = _has_historical_record(config, str(item.get("missing_field")), required_before, match_id, dataset_cache)
        status = "RESOLVED" if found else "NA_AFTER_SOURCE_EXHAUSTION"
        resolved += int(found)
        log_items.append({
            **item,
            "collection_status": status,
            "reason": reason,
            "checked_at": cutoff.isoformat(),
            "historical_safety": "Only records timestamped no later than required_before can resolve a pre-match requirement.",
        })
    payload = {
        "generated_at": utc_now(),
        "cutoff": cutoff.isoformat(),
        "network_enabled": allow_network,
        "network_enrichment": network_result.get("summary", network_result) if network_result else "NOT_RUN",
        "summary": {
            "queue_items_checked": len(log_items),
            "historically_resolved": resolved,
            "kept_as_na": sum(item["collection_status"] == "NA_AFTER_SOURCE_EXHAUSTION" for item in log_items),
        },
        "items": log_items,
    }
    atomic_write_json(payload, config.output("logs", "temporal_enrichment_log.json"))
    return payload
