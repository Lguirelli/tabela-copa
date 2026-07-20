from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .config import TemporalConfig
from .io import atomic_write_csv, atomic_write_json, lineage, read_csv, utc_now

KNOCKOUT_MARKERS = ("avos", "oitavas", "quartas", "semif", "3º", "final")


def parse_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _kickoff_utc(date_value: Any, time_value: Any, timezone_name: str) -> pd.Timestamp:
    date_text = pd.Timestamp(date_value).strftime("%Y-%m-%d")
    time_text = str(time_value).strip() if str(time_value).strip() else "12:00"
    if time_text == "24:00":
        naive = datetime.strptime(f"{date_text} 00:00", "%Y-%m-%d %H:%M") + timedelta(days=1)
    else:
        naive = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
    local = naive.replace(tzinfo=ZoneInfo(timezone_name))
    return pd.Timestamp(local.astimezone(ZoneInfo("UTC")))


def is_knockout(phase: Any) -> bool:
    text = str(phase).lower()
    return any(marker in text for marker in KNOCKOUT_MARKERS)


def build_timeline(config: TemporalConfig) -> pd.DataFrame:
    matches = read_csv(config.path("matches"))
    results = read_csv(config.path("results"))
    result_map = results.set_index("jogo", drop=False).to_dict(orient="index")
    timezone_name = str(config.get("schedule_timezone", "America/New_York"))
    lead = int(config.get("prediction_lead_minutes", 120))
    regular_delay = int(config.get("regular_match_result_delay_minutes", 210))
    knockout_delay = int(config.get("knockout_match_result_delay_minutes", 270))
    pre_cutoff = parse_timestamp(config.get("pre_tournament_cutoff"))
    parent_map = {int(key): value for key, value in (config.get("bracket_parents", {}) or {}).items()}

    rows: list[dict[str, Any]] = []
    result_available: dict[int, pd.Timestamp] = {}
    for _, match in matches.sort_values(["data", "horaET", "jogo"]).iterrows():
        match_id = int(match["jogo"])
        kickoff = _kickoff_utc(match["data"], match.get("horaET", "12:00"), timezone_name)
        knockout = is_knockout(match.get("fase"))
        result_time = kickoff + pd.Timedelta(minutes=knockout_delay if knockout else regular_delay)
        result_available[match_id] = result_time
        if match_id <= 72:
            fixture_known = pre_cutoff
        elif match_id in range(73, 89):
            # Round-of-32 pairings are only safe after the final group match is complete.
            fixture_known = result_available.get(72, kickoff)
        else:
            parents = [int(x) for x in parent_map.get(match_id, [])]
            known_candidates = [result_available[parent] for parent in parents if parent in result_available]
            fixture_known = max(known_candidates) if known_candidates else kickoff
        real = result_map.get(match_id, {})
        rows.append({
            "match_id": match_id,
            "date": str(match["data"]),
            "phase": match.get("fase", "NA"),
            "group": match.get("grupo", "NA"),
            "team1": match.get("equipe1", "NA"),
            "team2": match.get("equipe2", "NA"),
            "stadium": match.get("estadio", "NA"),
            "city": match.get("cidade", "NA"),
            "country": match.get("pais", "NA"),
            "kickoff_at": kickoff.isoformat(),
            "prediction_at": (kickoff - pd.Timedelta(minutes=lead)).isoformat(),
            "fixture_known_at": fixture_known.isoformat(),
            "result_available_at": result_time.isoformat(),
            "statistics_available_at": (result_time + pd.Timedelta(minutes=int(config.get("post_match_statistics_delay_minutes", 30)))).isoformat(),
            "is_knockout": bool(knockout),
            "result_team1_goals": real.get("gols1_real", "NA"),
            "result_team2_goals": real.get("gols2_real", "NA"),
            "result_winner": real.get("vencedor_real", "NA"),
            "penalty_score": real.get("placar_penaltis_real", "NA"),
            "penalty_winner": real.get("vencedor_penaltis_real", "NA"),
        })
    timeline = pd.DataFrame(rows).sort_values(["kickoff_at", "match_id"]).reset_index(drop=True)
    out = config.output("data", "temporal", "matches_timeline.csv")
    atomic_write_csv(timeline, out)
    atomic_write_json({
        "generated_at": utc_now(),
        "competition_id": config.get("competition_id"),
        "temporal_rules": {
            "prediction_lead_minutes": lead,
            "regular_result_delay_minutes": regular_delay,
            "knockout_result_delay_minutes": knockout_delay,
            "round_of_32_fixture_visibility": "after_match_72_result_available",
            "later_knockout_visibility": "after_parent_results_available",
        },
        "inputs": lineage([config.path("matches"), config.path("results")], config.root),
        "rows": len(timeline),
    }, config.output("data", "temporal", "timeline_manifest.json"))
    return timeline


def visible_results(timeline: pd.DataFrame, cutoff: Any) -> pd.DataFrame:
    cutoff_ts = parse_timestamp(cutoff)
    result_times = pd.to_datetime(timeline["result_available_at"], utc=True)
    return timeline[result_times <= cutoff_ts].copy()


def visible_fixture(row: pd.Series, cutoff: Any) -> tuple[str, str]:
    cutoff_ts = parse_timestamp(cutoff)
    known_at = parse_timestamp(row["fixture_known_at"])
    if known_at <= cutoff_ts:
        return str(row["team1"]), str(row["team2"])
    return "TBD", "TBD"


def assert_temporal_integrity(records: list[dict[str, Any]], cutoff: Any) -> None:
    cutoff_ts = parse_timestamp(cutoff)
    violations = []
    for record in records:
        available = record.get("available_at")
        if available and parse_timestamp(available) > cutoff_ts:
            violations.append(record)
    if violations:
        raise ValueError(f"Temporal leakage detected in {len(violations)} records")
