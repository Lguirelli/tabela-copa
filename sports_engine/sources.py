from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .config import CompetitionConfig, ROOT
from .io import find_column, is_missing, normalize_text, read_table, utc_now, write_table


def _network_int(config: CompetitionConfig, key: str, env_name: str, default: int) -> int:
    raw = os.getenv(env_name, config.engine.get(key, default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, value)


def _network_timeout(config: CompetitionConfig) -> int:
    return _network_int(config, "network_timeout_seconds", "SPORTS_ENGINE_NETWORK_TIMEOUT", 8)


def _network_retries(config: CompetitionConfig) -> int:
    return _network_int(config, "network_retries", "SPORTS_ENGINE_NETWORK_RETRIES", 1)


def _scoreboard_rows(payload: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        if len(competitors) != 2:
            continue
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
        status = event.get("status", {}).get("type", {})
        if not status.get("completed"):
            continue
        rows.append({
            "external_event_id": event.get("id"),
            "date": str(event.get("date", ""))[:10],
            "home_team": home.get("team", {}).get("displayName"),
            "away_team": away.get("team", {}).get("displayName"),
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "status": status.get("description") or status.get("name"),
            "source_url": source_url,
            "collected_at": utc_now(),
        })
    return rows


def fetch_espn_scoreboard(source: dict[str, Any], config: CompetitionConfig) -> dict[str, Any]:
    url = str(source.get("url", "")).strip()
    if not url:
        return {"success": False, "reason": "source URL is empty"}
    payload = _request_json(
        url,
        timeout=_network_timeout(config),
        retries=_network_retries(config),
    )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    raw_dir = ROOT / "data" / "raw" / config.competition_id / str(source["id"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{utc_now().replace(':', '').replace('+00:00', 'Z')}_{sha[:12]}.json"
    raw_path.write_bytes(raw)
    rows = _scoreboard_rows(payload, url)
    staging = ROOT / "data" / "staging" / config.competition_id / "scoreboard_results.csv"
    write_table(pd.DataFrame(rows), staging)
    return {"success": True, "raw_path": raw_path.relative_to(ROOT).as_posix(), "staging_path": staging.relative_to(ROOT).as_posix(), "records": len(rows), "sha256": sha}



def _sync_catalog_mirrors(canonical_path: Path) -> list[str]:
    catalog_path = ROOT / "data" / "catalog.json"
    if not catalog_path.exists() or not canonical_path.exists():
        return []
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    relative = canonical_path.relative_to(ROOT).as_posix()
    synced: list[str] = []
    for definition in catalog.get("datasets", {}).values():
        if definition.get("canonical") != relative:
            continue
        for mirror in definition.get("mirrors", []):
            mirror_path = ROOT / str(mirror)
            mirror_path.parent.mkdir(parents=True, exist_ok=True)
            mirror_path.write_bytes(canonical_path.read_bytes())
            synced.append(mirror_path.relative_to(ROOT).as_posix())
    return synced

def merge_scoreboard_results(config: CompetitionConfig, staging_path: Path) -> dict[str, Any]:
    matches = read_table(config.dataset("matches"))
    results_path = config.dataset("results")
    results = read_table(results_path, required=False)
    staged = read_table(staging_path, required=False)
    if staged.empty:
        return {"inserted": 0, "reason": "staging is empty"}
    match_id = find_column(matches, "jogo", "match_id")
    team1 = find_column(matches, "equipe1", "team1", "home_team")
    team2 = find_column(matches, "equipe2", "team2", "away_team")
    date_col = find_column(matches, "data", "date")
    if not all([match_id, team1, team2, date_col]):
        return {"inserted": 0, "reason": "matches dataset lacks identifiers/date/teams"}
    existing_ids = set()
    if not results.empty:
        result_id = find_column(results, "jogo", "match_id")
        if result_id:
            existing_ids = set(pd.to_numeric(results[result_id], errors="coerce").dropna().astype(int))
    additions: list[dict[str, Any]] = []
    for _, match in matches.iterrows():
        mid = int(match[match_id])
        if mid in existing_ids:
            continue
        t1 = normalize_text(match[team1]); t2 = normalize_text(match[team2]); date = str(match[date_col])[:10]
        candidate = None; orientation = None
        for _, ext in staged.iterrows():
            if str(ext.get("date", ""))[:10] != date:
                continue
            home = normalize_text(ext.get("home_team")); away = normalize_text(ext.get("away_team"))
            if {home, away} == {t1, t2}:
                candidate = ext
                orientation = "home_is_team1" if home == t1 else "away_is_team1"
                break
        if candidate is None:
            continue
        g1 = candidate["home_score"] if orientation == "home_is_team1" else candidate["away_score"]
        g2 = candidate["away_score"] if orientation == "home_is_team1" else candidate["home_score"]
        try:
            g1, g2 = int(g1), int(g2)
        except (TypeError, ValueError):
            continue
        winner = match[team1] if g1 > g2 else match[team2] if g2 > g1 else "Empate"
        additions.append({
            "jogo": mid, "data": date, "fase": match.get(find_column(matches, "fase", "phase") or "", "NA"),
            "equipe1": match[team1], "equipe2": match[team2], "gols1_real": g1, "gols2_real": g2,
            "placar_real": f"{g1}-{g2}", "vencedor_real": winner, "status_real": "Finalizado",
            "fonte": candidate.get("source_url", "NA"), "placar_original": f"{match[team1]} {g1} x {g2} {match[team2]}",
            "placar_penaltis_real": "NA", "vencedor_penaltis_real": "NA", "source_secondary": "NA",
        })
    synced_mirrors: list[str] = []
    if additions:
        combined = pd.concat([results, pd.DataFrame(additions)], ignore_index=True, sort=False)
        id_col = find_column(combined, "jogo", "match_id") or "jogo"
        combined[id_col] = pd.to_numeric(combined[id_col], errors="coerce")
        combined = combined.sort_values(id_col).drop_duplicates(id_col, keep="first")
        write_table(combined, results_path)
        synced_mirrors.extend(_sync_catalog_mirrors(results_path))
        status_col = find_column(matches, "status")
        if status_col:
            inserted_ids = {int(row["jogo"]) for row in additions}
            numeric_ids = pd.to_numeric(matches[match_id], errors="coerce")
            matches.loc[numeric_ids.isin(inserted_ids), status_col] = "Finalizado"
            write_table(matches, config.dataset("matches"))
            synced_mirrors.extend(_sync_catalog_mirrors(config.dataset("matches")))
    return {"inserted": len(additions), "synced_mirrors": sorted(set(synced_mirrors))}


def _request_json(url: str, timeout: int, retries: int = 1) -> dict[str, Any]:
    import time
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                timeout=(min(5, timeout), timeout),
                headers={"User-Agent": "sports-engine-repository/1.0"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # network errors are recorded by the caller
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 2))
    assert last_error is not None
    raise last_error


def _team_alias_lookup() -> dict[str, str]:
    aliases: dict[str, str] = {}
    path = ROOT / "data" / "mappings" / "team_name_aliases.csv"
    if path.exists():
        frame = read_table(path, required=False)
        repo_col = find_column(frame, "repo_team")
        alias_col = find_column(frame, "alias")
        if repo_col and alias_col:
            for _, row in frame.iterrows():
                repo = str(row[repo_col]).strip()
                aliases[normalize_text(repo)] = repo
                aliases[normalize_text(row[alias_col])] = repo
    return aliases


def _canonical_team(value: Any, aliases: dict[str, str]) -> str:
    text = normalize_text(value)
    return aliases.get(text, str(value).strip() if not is_missing(value) else "NA")


def _event_id_map(config: CompetitionConfig, source: dict[str, Any]) -> dict[int, str]:
    path = ROOT / str(source.get("event_map_path", "data/normalized/espn_matches.csv"))
    mapping_frame = read_table(path, required=False)
    matches = read_table(config.dataset("matches"))
    if mapping_frame.empty or matches.empty:
        return {}
    external_col = find_column(mapping_frame, "espn_event_id", "external_event_id", "event_id")
    mapped_id_col = find_column(mapping_frame, "jogo", "match_id")
    map_home = find_column(mapping_frame, "home_team", "home_team_espn")
    map_away = find_column(mapping_frame, "away_team", "away_team_espn")
    repo1 = find_column(mapping_frame, "repo_equipe1")
    repo2 = find_column(mapping_frame, "repo_equipe2")
    match_id = find_column(matches, "jogo", "match_id")
    team1 = find_column(matches, "equipe1", "team1")
    team2 = find_column(matches, "equipe2", "team2")
    if not all([external_col, match_id, team1, team2]):
        return {}
    aliases = _team_alias_lookup()
    schedule: dict[frozenset[str], list[tuple[int, pd.Timestamp | None]]] = {}
    match_date = find_column(matches, "data", "date")
    for _, row in matches.iterrows():
        key = frozenset({_canonical_team(row[team1], aliases), _canonical_team(row[team2], aliases)})
        parsed_date = pd.to_datetime(row.get(match_date), errors="coerce") if match_date else pd.NaT
        schedule.setdefault(key, []).append((int(row[match_id]), None if pd.isna(parsed_date) else parsed_date))
    output: dict[int, str] = {}
    for _, row in mapping_frame.iterrows():
        external = row.get(external_col)
        if is_missing(external):
            continue
        existing = row.get(mapped_id_col) if mapped_id_col else None
        if not is_missing(existing):
            try:
                output[int(float(existing))] = str(int(float(external)))
                continue
            except (TypeError, ValueError):
                pass
        left = row.get(repo1) if repo1 and not is_missing(row.get(repo1)) else row.get(map_home) if map_home else None
        right = row.get(repo2) if repo2 and not is_missing(row.get(repo2)) else row.get(map_away) if map_away else None
        key = frozenset({_canonical_team(left, aliases), _canonical_team(right, aliases)})
        candidates = schedule.get(key, [])
        selected: int | None = None
        if len(candidates) == 1:
            selected = candidates[0][0]
        elif candidates:
            map_date_col = find_column(mapping_frame, "date", "datetime_utc")
            external_date = pd.to_datetime(row.get(map_date_col), errors="coerce") if map_date_col else pd.NaT
            if not pd.isna(external_date):
                ranked = sorted(
                    [(abs((candidate_date.normalize() - external_date.normalize()).days), candidate_id) for candidate_id, candidate_date in candidates if candidate_date is not None],
                    key=lambda item: item[0],
                )
                if ranked and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]) and ranked[0][0] <= 1:
                    selected = ranked[0][1]
        if selected is not None:
            output[selected] = str(int(float(external)))
    return output


def _team_from_summary_block(block: dict[str, Any], aliases: dict[str, str]) -> str:
    team = block.get("team") or {}
    return _canonical_team(team.get("displayName") or team.get("name") or block.get("displayName"), aliases)


def _parse_stat_value(stat: dict[str, Any]) -> Any:
    value = stat.get("value")
    if value is not None:
        return value
    display = stat.get("displayValue")
    if display is None:
        return None
    text = str(display).strip().replace("%", "")
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return display


def _parse_espn_summary(payload: dict[str, Any], match_id: int, event_id: str, source_url: str, source_file: str) -> dict[str, list[dict[str, Any]]]:
    aliases = _team_alias_lookup()
    events: list[dict[str, Any]] = []
    plays = payload.get("plays") or payload.get("commentary") or []
    for play in plays:
        type_obj = play.get("type") or {}
        participants = play.get("participants") or []
        athlete = None
        if participants:
            athlete_obj = participants[0].get("athlete") or {}
            athlete = athlete_obj.get("displayName") or athlete_obj.get("shortName")
        team_obj = play.get("team") or {}
        team_name = _canonical_team(team_obj.get("displayName") or team_obj.get("name"), aliases)
        period_obj = play.get("period") or {}
        clock_obj = play.get("clock") or {}
        events.append({
            "jogo": match_id,
            "espn_event_id": event_id,
            "event_id": play.get("id"),
            "period": period_obj.get("number") if isinstance(period_obj, dict) else period_obj,
            "clock": clock_obj.get("displayValue") if isinstance(clock_obj, dict) else clock_obj,
            "type": type_obj.get("id") or type_obj.get("name"),
            "type_text": type_obj.get("text") or type_obj.get("name"),
            "team": normalize_text(team_name) if team_name != "NA" else "NA",
            "team_espn": team_obj.get("displayName") or team_obj.get("name") or "NA",
            "player": athlete or "NA",
            "text": play.get("text") or play.get("shortText") or "NA",
            "scoring_play": bool(play.get("scoringPlay", False)),
            "shootout": bool(play.get("shootout", False)),
            "source_file": source_file,
            "source_url": source_url,
            "collected_at": utc_now(),
        })

    team_stats: list[dict[str, Any]] = []
    for block in (payload.get("boxscore") or {}).get("teams", []) or []:
        row: dict[str, Any] = {
            "jogo": match_id,
            "espn_event_id": event_id,
            "team_espn": (block.get("team") or {}).get("displayName") or "NA",
            "team_norm": normalize_text(_team_from_summary_block(block, aliases)),
            "source_file": source_file,
            "source_url": source_url,
            "collected_at": utc_now(),
        }
        for stat in block.get("statistics") or []:
            name = stat.get("name") or stat.get("label")
            if name:
                row[f"stat_{name}"] = _parse_stat_value(stat)
        team_stats.append(row)

    lineups: list[dict[str, Any]] = []
    player_stats: list[dict[str, Any]] = []
    roster_blocks = payload.get("rosters") or []
    for block in roster_blocks:
        team_name = _team_from_summary_block(block, aliases)
        for entry in block.get("roster") or []:
            athlete = entry.get("athlete") or {}
            player_id = athlete.get("id")
            player_name = athlete.get("displayName") or athlete.get("fullName") or athlete.get("shortName") or "NA"
            position = (entry.get("position") or {}).get("abbreviation") or (athlete.get("position") or {}).get("abbreviation") or "NA"
            starter = entry.get("starter")
            lineups.append({
                "competition_id": "NA",
                "season": "NA",
                "match_id": match_id,
                "team": team_name,
                "player_id": player_id or "NA",
                "player_name": player_name,
                "starter": starter if starter is not None else "NA",
                "position": position,
                "source": source_url,
                "source_collected_at": utc_now(),
            })
            stats_dict: dict[str, Any] = {}
            for stat in entry.get("statistics") or []:
                name = stat.get("name") or stat.get("label")
                if name:
                    stats_dict[str(name)] = _parse_stat_value(stat)
            def first_stat(*names: str) -> Any:
                for name in names:
                    if name in stats_dict:
                        return stats_dict[name]
                return "NA"
            player_stats.append({
                "competition_id": "NA",
                "season": "NA",
                "match_id": match_id,
                "team": team_name,
                "player_id": player_id or "NA",
                "player_name": player_name,
                "minutes": first_stat("minutes", "MIN"),
                "goals": first_stat("goals", "G"),
                "assists": first_stat("goalAssists", "assists", "A"),
                "shots": first_stat("totalShots", "shots"),
                "xg": first_stat("expectedGoals", "xG"),
                "xa": first_stat("expectedAssists", "xA"),
                "rating": first_stat("rating"),
                "source": source_url,
                "source_collected_at": utc_now(),
            })
    return {"events": events, "team_stats": team_stats, "lineups": lineups, "player_stats": player_stats}


def _record_key(row: pd.Series, columns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(normalize_text(row.get(column)) for column in columns)


def _append_new_records(
    target: Path,
    rows: list[dict[str, Any]],
    key_candidates: tuple[tuple[str, ...], ...],
) -> int:
    """Append only unseen records, preserving every observed row already stored."""
    if not rows:
        return 0
    existing = read_table(target, required=False)
    incoming = pd.DataFrame(rows)
    incoming.columns = [str(col).replace("\ufeff", "") for col in incoming.columns]

    key_columns: tuple[str, ...] | None = None
    for candidate in key_candidates:
        if all(column in incoming.columns for column in candidate) and (
            existing.empty or all(column in existing.columns for column in candidate)
        ):
            key_columns = candidate
            break
    if key_columns is None:
        raise ValueError(f"No compatible deduplication key for {target}")

    existing_keys: set[tuple[str, ...]] = set()
    if not existing.empty:
        existing_keys = {_record_key(row, key_columns) for _, row in existing.iterrows()}

    accepted_rows: list[pd.Series] = []
    seen = set(existing_keys)
    for _, row in incoming.iterrows():
        key = _record_key(row, key_columns)
        if key in seen:
            continue
        seen.add(key)
        accepted_rows.append(row)

    if not accepted_rows:
        return 0
    accepted = pd.DataFrame(accepted_rows).reset_index(drop=True)
    combined = pd.concat([existing, accepted], ignore_index=True, sort=False)
    write_table(combined, target)
    return len(accepted)


def fetch_espn_summaries(source: dict[str, Any], config: CompetitionConfig, match_ids: list[int]) -> dict[str, Any]:
    template = str(source.get("summary_url_template", "")).strip()
    if not template:
        return {"success": False, "reason": "summary_url_template is empty"}
    event_map = _event_id_map(config, source)
    timeout = _network_timeout(config)
    retries = _network_retries(config)
    parsed = {"events": [], "team_stats": [], "lineups": [], "player_stats": []}
    fetched_matches: list[int] = []
    failures: list[dict[str, Any]] = []
    raw_dir = ROOT / "data" / "raw" / config.competition_id / str(source.get("id", "espn_summary"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    for match_id in sorted(set(int(value) for value in match_ids)):
        event_id = event_map.get(match_id)
        if not event_id:
            failures.append({"match_id": match_id, "reason": "external event ID not mapped"})
            continue
        url = template.format(event_id=event_id)
        try:
            payload = _request_json(url, timeout=timeout, retries=retries)
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            sha = hashlib.sha256(raw).hexdigest()
            filename = f"match_{match_id}_event_{event_id}_{sha[:12]}.json"
            raw_path = raw_dir / filename
            if not raw_path.exists():
                raw_path.write_bytes(raw)
            result = _parse_espn_summary(payload, match_id, event_id, url, filename)
            for key in parsed:
                parsed[key].extend(result[key])
            fetched_matches.append(match_id)
        except Exception as exc:
            failures.append({"match_id": match_id, "event_id": event_id, "reason": f"{type(exc).__name__}: {exc}"})
    # Add competition metadata after parsing, without fabricating sport statistics.
    for row in parsed["lineups"] + parsed["player_stats"]:
        row["competition_id"] = config.competition_id
        row["season"] = config.season
    inserted = {
        "events": _append_new_records(
            config.dataset("events"),
            parsed["events"],
            (("jogo", "event_id"), ("jogo", "period", "clock", "type_text", "team", "player", "text")),
        ),
        "statistics": _append_new_records(
            config.dataset("team_match_stats"),
            parsed["team_stats"],
            (("jogo", "team_norm"), ("jogo", "team_espn")),
        ),
        "lineup": _append_new_records(
            config.dataset("lineups"),
            parsed["lineups"],
            (("match_id", "team", "player_id"), ("match_id", "team", "player_name")),
        ),
        "participation": 0,
        "minutes": _append_new_records(
            config.dataset("player_match_stats"),
            parsed["player_stats"],
            (("match_id", "team", "player_id"), ("match_id", "team", "player_name")),
        ),
        "performance": 0,
    }
    inserted["participation"] = inserted["lineup"]
    inserted["performance"] = inserted["minutes"]
    return {
        "success": bool(fetched_matches),
        "fetched_matches": fetched_matches,
        "failures": failures,
        "inserted_rows": inserted,
        "event_map_coverage": len(event_map),
    }
