from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from .config import CompetitionConfig, ROOT
from .io import find_column, is_missing, normalize_text, read_json, read_table, utc_now, write_json_copies, write_table
from .lineage import metadata

_SUBSTITUTION_RE = re.compile(r"substitution,.*?\.\s*(.+?)\s+replaces\s+(.+?)(?:\.|$)", re.IGNORECASE)
_CLOCK_RE = re.compile(r"(?P<base>\d{1,3})(?:\+(?P<added>\d{1,2}))?")
_EXTRA_TIME_MARKERS = ("prorroga", "extra time", "aet", "após prorrogação", "apos prorrogacao")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return normalize_text(value) in {"1", "true", "yes", "sim", "y"}


def _clock_minute(value: Any) -> int | None:
    if is_missing(value):
        return None
    text = str(value)
    numbers = [int(item) for item in re.findall(r"\d+", text)]
    if not numbers:
        return None
    if "+" in text and len(numbers) >= 2:
        return numbers[0] + numbers[1]
    return numbers[0]


def _person_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(value)).strip()


def _clean_replaced_name(value: str) -> str:
    text = re.split(r"\s+(?:because|due|following)\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return text.strip(" .")


def _match_durations(config: CompetitionConfig, events: pd.DataFrame) -> dict[int, int]:
    durations: dict[int, int] = {}
    results = read_table(config.dataset("results"), required=False)
    result_id = find_column(results, "jogo", "match_id")
    original = find_column(results, "placar_original", "decision_method", "method")
    if result_id and original:
        for _, row in results.iterrows():
            try:
                match_id = int(float(row[result_id]))
            except (TypeError, ValueError):
                continue
            text = normalize_text(row.get(original))
            if any(marker in text for marker in _EXTRA_TIME_MARKERS):
                durations[match_id] = 120

    event_id = find_column(events, "jogo", "match_id")
    period_col = find_column(events, "period")
    shootout_col = find_column(events, "shootout")
    if event_id and period_col:
        periods = pd.to_numeric(events[period_col], errors="coerce")
        usable = events.copy()
        usable["__period"] = periods
        if shootout_col:
            usable = usable[~usable[shootout_col].map(_truthy)]
        for match_id, group in usable.groupby(event_id):
            try:
                numeric_id = int(float(match_id))
            except (TypeError, ValueError):
                continue
            if group["__period"].max(skipna=True) >= 3:
                durations[numeric_id] = 120
    return durations


def _event_minutes(events: pd.DataFrame) -> tuple[dict[tuple[int, str, str], int], dict[tuple[int, str, str], int], dict[tuple[int, str, str], int]]:
    substitutions_in: dict[tuple[int, str, str], int] = {}
    substitutions_out: dict[tuple[int, str, str], int] = {}
    dismissals: dict[tuple[int, str, str], int] = {}
    match_col = find_column(events, "jogo", "match_id")
    team_col = find_column(events, "team", "team_norm")
    player_col = find_column(events, "player", "player_name")
    text_col = find_column(events, "text")
    clock_col = find_column(events, "clock", "minute")
    substitution_col = find_column(events, "substitution")
    red_col = find_column(events, "red_card")
    if not match_col or not clock_col:
        return substitutions_in, substitutions_out, dismissals

    for _, row in events.iterrows():
        try:
            match_id = int(float(row[match_col]))
        except (TypeError, ValueError):
            continue
        minute = _clock_minute(row.get(clock_col))
        if minute is None:
            continue
        team = normalize_text(row.get(team_col)) if team_col else ""
        if substitution_col and _truthy(row.get(substitution_col)) and text_col:
            match = _SUBSTITUTION_RE.search(str(row.get(text_col, "")))
            if match:
                event_player = row.get(player_col) if player_col else None
                player_in = _person_key(event_player) if not is_missing(event_player) else _person_key(match.group(1))
                player_out = _person_key(_clean_replaced_name(match.group(2)))
                substitutions_in[(match_id, team, player_in)] = minute
                substitutions_out[(match_id, team, player_out)] = minute
        if red_col and _truthy(row.get(red_col)) and player_col:
            player = _person_key(row.get(player_col))
            if player:
                dismissals[(match_id, team, player)] = minute
    return substitutions_in, substitutions_out, dismissals


def _lookup_minute(mapping: dict[tuple[int, str, str], int], match_id: int, team: Any, player: Any) -> int | None:
    team_key = normalize_text(team)
    player_key = _person_key(player)
    exact = mapping.get((match_id, team_key, player_key))
    if exact is not None:
        return exact
    # Team aliases and transliterations occasionally differ between feeds. First
    # try an exact player-name match within the match, then a conservative unique
    # fuzzy match for spelling variants such as Jin-Seop/Jin-Seob.
    candidates = [(name, minute) for (mid, _team, name), minute in mapping.items() if mid == match_id]
    exact_name = [minute for name, minute in candidates if name == player_key]
    if len(exact_name) == 1:
        return exact_name[0]
    ranked = sorted(
        ((SequenceMatcher(None, player_key, name).ratio(), name, minute) for name, minute in candidates),
        reverse=True,
    )
    if not ranked or ranked[0][0] < 0.72:
        return None
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    if ranked[0][0] - second < 0.06:
        return None
    return ranked[0][2]


def _stable_source(row: pd.Series) -> str:
    source = row.get("source")
    return str(source).strip() if not is_missing(source) else "lineup_and_match_events"


def _preserve_generated_at_when_unchanged(report: dict[str, Any], existing_path: Path) -> dict[str, Any]:
    """Keep reports byte-stable when a repeated derivation changes no facts."""
    existing = read_json(existing_path, {}) or {}
    if not isinstance(existing, dict):
        return report
    current_body = {key: value for key, value in report.items() if key != "generated_at"}
    existing_body = {key: value for key, value in existing.items() if key != "generated_at"}
    if current_body == existing_body and existing.get("generated_at"):
        report["generated_at"] = existing["generated_at"]
    return report


def derive_player_facts(config: CompetitionConfig) -> dict[str, Any]:
    """Fill traceable post-match player facts without inventing observed values.

    Minutes are derived only from the published match roster, substitution events,
    dismissal events and the known 90/120-minute match duration. Existing observed
    minutes are never overwritten. Availability means only that a player was named in
    the matchday squad; it is not backdated as pre-match injury information.
    """
    lineups_path = config.dataset("lineups")
    stats_path = config.dataset("player_match_stats")
    availability_path = config.dataset("player_availability")
    events_path = config.dataset("events")

    lineups = read_table(lineups_path, required=False)
    events = read_table(events_path, required=False)
    stats = read_table(stats_path, required=False)
    availability = read_table(availability_path, required=False)

    if lineups.empty:
        report = metadata("02a_derived_player_facts", config.competition_id, [lineups_path], ROOT, {
            "summary": {"status": "SKIPPED", "reason": "lineups dataset is empty", "minutes_filled": 0, "availability_rows_added": 0}
        })
        report = _preserve_generated_at_when_unchanged(report, ROOT / "reports" / "derived_player_facts_report.json")
        write_json_copies(report, config.scoped_path("reports", "derived_player_facts_report.json"), ROOT / "reports" / "derived_player_facts_report.json")
        return report

    lineup_match = find_column(lineups, "match_id", "jogo")
    lineup_team = find_column(lineups, "team", "team_norm")
    lineup_player = find_column(lineups, "player_name", "player")
    lineup_player_id = find_column(lineups, "player_id", "athlete_id")
    if not all([lineup_match, lineup_team, lineup_player]):
        raise ValueError("Lineups dataset lacks match_id, team or player_name")

    substitutions_in, substitutions_out, dismissals = _event_minutes(events)
    durations = _match_durations(config, events)

    if stats.empty:
        stats = pd.DataFrame(columns=[
            "competition_id", "season", "match_id", "team", "player_id", "player_name", "minutes", "source", "source_collected_at"
        ])
    stats_match = find_column(stats, "match_id", "jogo") or "match_id"
    stats_team = find_column(stats, "team", "team_norm") or "team"
    stats_player = find_column(stats, "player_name", "player") or "player_name"
    stats_player_id = find_column(stats, "player_id", "athlete_id") or "player_id"
    minutes_col = find_column(stats, "minutes", "minutos") or "minutes"
    for column in (stats_match, stats_team, stats_player, stats_player_id, minutes_col):
        if column not in stats.columns:
            stats[column] = pd.NA
    for column in ("minutes_method", "minutes_data_quality", "minutes_derived_from"):
        if column not in stats.columns:
            stats[column] = pd.NA

    stats_keys: dict[tuple[int, str, str], int] = {}
    for index, row in stats.iterrows():
        try:
            match_id = int(float(row.get(stats_match)))
        except (TypeError, ValueError):
            continue
        player_identifier = row.get(stats_player_id)
        identity = f"id:{normalize_text(player_identifier)}" if not is_missing(player_identifier) else f"name:{normalize_text(row.get(stats_player))}"
        stats_keys[(match_id, normalize_text(row.get(stats_team)), identity)] = index

    minutes_filled = 0
    stats_rows_added = 0
    unresolved_minutes = 0
    for _, lineup in lineups.iterrows():
        try:
            match_id = int(float(lineup.get(lineup_match)))
        except (TypeError, ValueError):
            continue
        team = lineup.get(lineup_team)
        player = lineup.get(lineup_player)
        player_identifier = lineup.get(lineup_player_id) if lineup_player_id else pd.NA
        identity = f"id:{normalize_text(player_identifier)}" if not is_missing(player_identifier) else f"name:{normalize_text(player)}"
        key = (match_id, normalize_text(team), identity)
        index = stats_keys.get(key)
        if index is None:
            index = len(stats)
            row = {column: pd.NA for column in stats.columns}
            row.update({
                "competition_id": config.competition_id,
                "season": config.season,
                stats_match: match_id,
                stats_team: team,
                stats_player_id: player_identifier,
                stats_player: player,
                "source": _stable_source(lineup),
                "source_collected_at": lineup.get("source_collected_at", pd.NA),
            })
            stats.loc[index] = row
            stats_keys[key] = index
            stats_rows_added += 1

        if not is_missing(stats.at[index, minutes_col]):
            continue

        duration = durations.get(match_id, 90)
        starter = _truthy(lineup.get("starter"))
        subbed_in = _truthy(lineup.get("subbed_in"))
        subbed_out = _truthy(lineup.get("subbed_out"))
        in_minute = _lookup_minute(substitutions_in, match_id, team, player)
        out_minute = _lookup_minute(substitutions_out, match_id, team, player)
        dismissal_minute = _lookup_minute(dismissals, match_id, team, player)
        method = ""
        minutes: int | None = None

        if starter:
            exit_minute = out_minute if subbed_out else dismissal_minute
            if exit_minute is not None:
                minutes = max(0, min(duration, exit_minute))
                method = "starter_until_substitution" if out_minute is not None else "starter_until_dismissal"
            elif subbed_out:
                unresolved_minutes += 1
            else:
                minutes = duration
                method = "starter_full_match"
        elif subbed_in:
            if in_minute is None:
                unresolved_minutes += 1
            else:
                exit_minute = out_minute or dismissal_minute or duration
                minutes = max(0, min(duration, exit_minute) - min(duration, in_minute))
                method = "substitute_interval"
        else:
            minutes = 0
            method = "unused_matchday_substitute"

        if minutes is None:
            continue
        stats.at[index, minutes_col] = int(minutes)
        stats.at[index, "minutes_method"] = method
        stats.at[index, "minutes_data_quality"] = "DERIVED_POST_MATCH"
        stats.at[index, "minutes_derived_from"] = "lineups+substitution_events+match_duration"
        minutes_filled += 1

    write_table(stats, stats_path)
    minute_values = pd.to_numeric(stats[minutes_col], errors="coerce")
    derived_mask = stats["minutes_data_quality"].astype(str).eq("DERIVED_POST_MATCH")
    minutes_non_null_total = int(minute_values.notna().sum())
    minutes_derived_total = int((minute_values.notna() & derived_mask).sum())
    minutes_observed_total = int((minute_values.notna() & ~derived_mask).sum())
    minutes_unresolved_total = int(minute_values.isna().sum())

    if availability.empty:
        availability = pd.DataFrame(columns=[
            "competition_id", "season", "match_id", "observation_date", "team", "player_id", "player_name", "status", "reason",
            "expected_return", "source", "source_collected_at", "available_at", "temporal_status", "data_quality", "derived_from"
        ])
    for column in ("match_id", "available_at", "temporal_status", "data_quality", "derived_from"):
        if column not in availability.columns:
            availability[column] = pd.NA

    existing_availability: set[tuple[int, str, str]] = set()
    availability_match = find_column(availability, "match_id", "jogo") or "match_id"
    availability_team = find_column(availability, "team", "team_norm") or "team"
    availability_player = find_column(availability, "player_name", "player") or "player_name"
    for _, row in availability.iterrows():
        try:
            match_id = int(float(row.get(availability_match)))
        except (TypeError, ValueError):
            continue
        existing_availability.add((match_id, normalize_text(row.get(availability_team)), normalize_text(row.get(availability_player))))

    match_dates: dict[int, str] = {}
    matches = read_table(config.dataset("matches"), required=False)
    matches_id = find_column(matches, "jogo", "match_id")
    matches_date = find_column(matches, "data", "date")
    if matches_id and matches_date:
        for _, row in matches.iterrows():
            try:
                match_dates[int(float(row[matches_id]))] = str(row[matches_date])[:10]
            except (TypeError, ValueError):
                continue

    new_availability_rows: list[dict[str, Any]] = []
    for _, lineup in lineups.iterrows():
        try:
            match_id = int(float(lineup.get(lineup_match)))
        except (TypeError, ValueError):
            continue
        team = lineup.get(lineup_team)
        player = lineup.get(lineup_player)
        key = (match_id, normalize_text(team), normalize_text(player))
        if key in existing_availability:
            continue
        collected_at = lineup.get("source_collected_at", lineup.get("available_at", pd.NA))
        new_availability_rows.append({
            "competition_id": config.competition_id,
            "season": config.season,
            "match_id": match_id,
            "observation_date": match_dates.get(match_id, str(collected_at)[:10] if not is_missing(collected_at) else "NA"),
            "team": team,
            "player_id": lineup.get(lineup_player_id) if lineup_player_id else "NA",
            "player_name": player,
            "status": "AVAILABLE_MATCHDAY_SQUAD",
            "reason": "Named in published match roster",
            "expected_return": "NA",
            "source": _stable_source(lineup),
            "source_collected_at": collected_at,
            "available_at": collected_at,
            "temporal_status": "POST_MATCH_DERIVED_FACT",
            "data_quality": "DERIVED_POST_MATCH",
            "derived_from": "lineups",
        })
        existing_availability.add(key)

    if new_availability_rows:
        availability = pd.concat([availability, pd.DataFrame(new_availability_rows)], ignore_index=True, sort=False)
        availability = availability.drop_duplicates(["match_id", "team", "player_name"], keep="first")
    write_table(availability, availability_path)

    report = metadata(
        "02a_derived_player_facts",
        config.competition_id,
        [lineups_path, events_path, config.dataset("matches"), config.dataset("results")],
        ROOT,
        {
            "summary": {
                "status": "COMPLETED",
                "lineup_rows": len(lineups),
                "minutes_filled_this_run": minutes_filled,
                "minutes_non_null_total": minutes_non_null_total,
                "minutes_derived_total": minutes_derived_total,
                "minutes_observed_total": minutes_observed_total,
                "minutes_unresolved": minutes_unresolved_total,
                "minutes_derivation_attempts_unresolved_this_run": unresolved_minutes,
                "player_stat_rows_added": stats_rows_added,
                "availability_rows_added": len(new_availability_rows),
                "availability_rows_total": len(availability),
            },
            "rules": {
                "observed_minutes_are_preserved": True,
                "derived_minutes_are_labeled": True,
                "availability_scope": "Published matchday squad only; not a historical injury report.",
                "temporal_safety": "source_collected_at/available_at are preserved, so post-match facts cannot resolve older pre-match snapshots.",
            },
        },
    )
    report = _preserve_generated_at_when_unchanged(report, ROOT / "reports" / "derived_player_facts_report.json")
    write_json_copies(report, config.scoped_path("reports", "derived_player_facts_report.json"), ROOT / "reports" / "derived_player_facts_report.json")
    return report
