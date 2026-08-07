from __future__ import annotations

from typing import Any

import pandas as pd

from sports_engine.io import normalize_text

from .config import TemporalConfig
from .io import atomic_write_json, read_csv, utc_now
from .temporal import parse_timestamp


_DATASET_CACHE: dict[tuple[str, int, int], pd.DataFrame] = {}


def _cached_dataset(config: TemporalConfig, name: str) -> pd.DataFrame:
    """Read a configured CSV once per file version during a replay run."""
    path = config.path(name)
    if not path.exists():
        return pd.DataFrame()
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    cached = _DATASET_CACHE.get(key)
    if cached is not None:
        return cached
    # Discard stale cache entries for the same path.
    for old_key in [item for item in _DATASET_CACHE if item[0] == key[0] and item != key]:
        _DATASET_CACHE.pop(old_key, None)
    frame = read_csv(path, required=False)
    _DATASET_CACHE[key] = frame
    return frame


def _available_rows(frame: pd.DataFrame, cutoff: Any, time_columns: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty:
        return frame
    cutoff_ts = parse_timestamp(cutoff)
    for column in time_columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], utc=True, errors="coerce")
            return frame[values <= cutoff_ts].copy()
    return frame.iloc[0:0].copy()


def check_pre_match_data(
    config: TemporalConfig,
    match: pd.Series,
    cutoff: Any,
    team_profiles: pd.DataFrame,
    visible_prior_results: pd.DataFrame,
) -> dict[str, Any]:
    team1, team2 = str(match["team1"]), str(match["team2"])
    profile_names = {normalize_text(value) for value in team_profiles["team"].astype(str)}
    lineups = _available_rows(_cached_dataset(config, "lineups"), cutoff, ("available_at", "source_collected_at"))
    availability = _available_rows(_cached_dataset(config, "player_availability"), cutoff, ("available_at", "source_collected_at", "observation_date"))
    news = _available_rows(_cached_dataset(config, "archived_news"), cutoff, ("published_at",))
    officials = _available_rows(_cached_dataset(config, "match_officials"), cutoff, ("available_at", "source_collected_at"))
    weather = _available_rows(_cached_dataset(config, "pre_match_weather"), cutoff, ("available_at",))

    checks = []
    checks.append({
        "field": "team_identity",
        "status": "AVAILABLE" if team1 != "TBD" and team2 != "TBD" else "MISSING",
        "priority": "blocking",
        "source": "data/temporal/matches_timeline.csv",
    })
    checks.append({
        "field": "kickoff_time",
        "status": "AVAILABLE" if str(match.get("kickoff_at", "")) else "MISSING",
        "priority": "blocking",
        "source": "data/temporal/matches_timeline.csv",
    })
    profiles_available = normalize_text(team1) in profile_names and normalize_text(team2) in profile_names
    checks.append({
        "field": "initial_team_profile",
        "status": "AVAILABLE" if profiles_available else "MISSING",
        "priority": "blocking",
        "source": "data/pre_worldcup_state/teams.csv",
    })
    for field, frame, source in (
        ("confirmed_lineup", lineups, "data/platform/lineups.csv"),
        ("player_availability", availability, "data/platform/player_availability.csv"),
        ("archived_news", news, "data/temporal/archived_news.csv"),
    ):
        if frame.empty:
            available = False
        else:
            team_col = next((col for col in ("team", "team_norm") if col in frame.columns), None)
            available = bool(team_col and frame[team_col].astype(str).map(normalize_text).isin({normalize_text(team1), normalize_text(team2)}).any())
        checks.append({"field": field, "status": "AVAILABLE" if available else "NA_SOURCE_EXHAUSTED", "priority": "non_blocking", "source": source})
    official_match_col = next((col for col in ("match_id", "jogo") if col in officials.columns), None)
    official_available = bool(
        official_match_col
        and not officials[pd.to_numeric(officials[official_match_col], errors="coerce") == int(match["match_id"])].empty
    )
    weather_match_col = next((col for col in ("match_id", "jogo") if col in weather.columns), None)
    weather_available = bool(
        weather_match_col
        and not weather[pd.to_numeric(weather[weather_match_col], errors="coerce") == int(match["match_id"])].empty
    )
    checks.extend([
        {"field": "weather", "status": "AVAILABLE" if weather_available else "NA_SOURCE_EXHAUSTED", "priority": "non_blocking", "source": "data/context/pre_match_weather.csv"},
        {"field": "travel", "status": "NA_SOURCE_EXHAUSTED", "priority": "non_blocking", "source": "NA"},
        {"field": "referee", "status": "AVAILABLE" if official_available else "NA_SOURCE_EXHAUSTED", "priority": "non_blocking", "source": "data/platform/match_officials.csv"},
        {"field": "recent_tournament_form", "status": "AVAILABLE" if len(visible_prior_results) > 0 else "NA_NOT_YET_OBSERVED", "priority": "non_blocking", "source": "temporally visible official results"},
    ])
    blocking_missing = [item for item in checks if item["priority"] == "blocking" and item["status"] != "AVAILABLE"]
    available_count = sum(item["status"] == "AVAILABLE" for item in checks)
    readiness = available_count / max(1, len(checks))
    return {
        "match_id": int(match["match_id"]),
        "cutoff": parse_timestamp(cutoff).isoformat(),
        "team1": team1,
        "team2": team2,
        "status": "BLOCKED" if blocking_missing else ("READY" if readiness >= 0.8 else "READY_WITH_NA"),
        "readiness_score": round(readiness, 6),
        "checks": checks,
        "blocking_missing": blocking_missing,
    }


def write_missing_queue(config: TemporalConfig, check_results: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for result in check_results:
        for check in result["checks"]:
            if check["status"] == "AVAILABLE":
                continue
            items.append({
                "entity": "match",
                "entity_id": result["match_id"],
                "team1": result["team1"],
                "team2": result["team2"],
                "missing_field": check["field"],
                "priority": "high" if check["priority"] == "blocking" else "medium",
                "status": "OPEN" if check["status"] == "MISSING" else "NA_AFTER_SOURCE_EXHAUSTION",
                "required_before": result["cutoff"],
                "source_candidate": check["source"],
                "temporal_rule": "source record must have published_at/available_at <= required_before",
            })
    payload = {
        "generated_at": utc_now(),
        "competition_id": config.get("competition_id"),
        "items": items,
        "summary": {
            "matches_checked": len(check_results),
            "open_blocking": sum(item["status"] == "OPEN" and item["priority"] == "high" for item in items),
            "na_after_source_exhaustion": sum(item["status"] == "NA_AFTER_SOURCE_EXHAUSTION" for item in items),
        },
    }
    atomic_write_json(payload, config.output("data", "temporal", "missing_information_queue.json"))
    atomic_write_json(payload, config.output("data", "queues", "missing_information_queue.json"))
    return payload
