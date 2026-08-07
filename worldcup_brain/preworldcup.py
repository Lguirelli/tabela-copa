from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from sports_engine.io import normalize_text

from .config import TemporalConfig
from .io import atomic_write_csv, atomic_write_json, lineage, read_csv, utc_now


def _first_existing(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {normalize_text(col): col for col in frame.columns}
    for candidate in candidates:
        key = normalize_text(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _value(row: pd.Series, column: str | None, default: Any = "NA") -> Any:
    if not column:
        return default
    value = row.get(column, default)
    if pd.isna(value) or str(value).strip() == "":
        return default
    return value


<<<<<<< HEAD
def _latest_rankings(config: TemporalConfig, cutoff: pd.Timestamp) -> dict[str, pd.Series]:
    path = config.path("fifa_rankings")
    rankings = read_csv(path, required=False)
    if rankings.empty or "team" not in rankings.columns or "published_at" not in rankings.columns:
        return {}
    published = pd.to_datetime(rankings["published_at"], utc=True, errors="coerce")
    eligible = rankings[published <= cutoff].copy()
    if eligible.empty:
        return {}
    eligible["_published"] = pd.to_datetime(eligible["published_at"], utc=True, errors="coerce")
    eligible["_team"] = eligible["team"].map(normalize_text)
    eligible = eligible.sort_values("_published").drop_duplicates("_team", keep="last")
    return {row["_team"]: row for _, row in eligible.iterrows()}


def _recent_form(config: TemporalConfig, cutoff: pd.Timestamp) -> dict[str, dict[str, Any]]:
    path = config.path("external_matches")
    matches = read_csv(path, required=False)
    required = {"utc_date", "home_team", "away_team", "home_score", "away_score"}
    if matches.empty or not required.issubset(matches.columns):
        return {}
    dates = pd.to_datetime(matches["utc_date"], utc=True, errors="coerce")
    eligible = matches[dates < cutoff].copy()
    if "published_at" in eligible.columns:
        published = pd.to_datetime(eligible["published_at"], utc=True, errors="coerce")
        eligible = eligible[published <= cutoff]
    if "status" in eligible.columns:
        eligible = eligible[eligible["status"].astype(str).str.upper().isin({"FINISHED", "FT"})]
    eligible["_date"] = pd.to_datetime(eligible["utc_date"], utc=True, errors="coerce")
    eligible["_home_score"] = pd.to_numeric(eligible["home_score"], errors="coerce")
    eligible["_away_score"] = pd.to_numeric(eligible["away_score"], errors="coerce")
    eligible = eligible.dropna(subset=["_date", "_home_score", "_away_score"])
    histories: dict[str, list[dict[str, Any]]] = {}
    for _, match in eligible.sort_values("_date").iterrows():
        home, away = str(match["home_team"]), str(match["away_team"])
        hg, ag = float(match["_home_score"]), float(match["_away_score"])
        home_points = 3.0 if hg > ag else 1.0 if hg == ag else 0.0
        away_points = 3.0 if ag > hg else 1.0 if hg == ag else 0.0
        histories.setdefault(normalize_text(home), []).append({"points": home_points, "gf": hg, "ga": ag})
        histories.setdefault(normalize_text(away), []).append({"points": away_points, "gf": ag, "ga": hg})
    output: dict[str, dict[str, Any]] = {}
    for team, rows in histories.items():
        recent = rows[-10:]
        output[team] = {
            "recent_matches": len(recent),
            "recent_points_per_match": round(sum(row["points"] for row in recent) / len(recent), 6),
            "recent_goals_for": round(sum(row["gf"] for row in recent) / len(recent), 6),
            "recent_goals_against": round(sum(row["ga"] for row in recent) / len(recent), 6),
        }
    return output


def build_pre_worldcup_state(config: TemporalConfig) -> dict[str, Any]:
    cutoff_ts = pd.Timestamp(config.get("pre_tournament_cutoff")).tz_convert("UTC")
    cutoff = cutoff_ts.isoformat()
=======
def build_pre_worldcup_state(config: TemporalConfig) -> dict[str, Any]:
    cutoff = pd.Timestamp(config.get("pre_tournament_cutoff")).tz_convert("UTC").isoformat()
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
    strengths = read_csv(config.path("team_strengths"))
    tactics = read_csv(config.path("team_tactics"))
    players = read_csv(config.path("players"))
    matches = read_csv(config.path("matches"))
<<<<<<< HEAD
    ranking_index = _latest_rankings(config, cutoff_ts)
    recent_form = _recent_form(config, cutoff_ts)
=======
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3

    team_col = _first_existing(strengths, ["selecao", "seleção", "team"])
    if team_col is None:
        raise ValueError("No team column found in team_strengths")

    tactic_team_col = _first_existing(tactics, ["seleção", "selecao", "team"])
    tactic_index = {}
    if tactic_team_col:
        tactic_index = {normalize_text(row[tactic_team_col]): row for _, row in tactics.iterrows()}

    team_rows: list[dict[str, Any]] = []
    field_lineage: list[dict[str, Any]] = []
    strength_fields = {
        "coach": ["tecnico", "técnico"],
        "tactical_style": ["estilo_tecnico", "estilo técnico"],
        "base_system": ["sistema_base", "sistema base"],
        "initial_strength_proxy": ["forca_modelo_0_100", "força modelo 0 100"],
        "attack_proxy": ["ataque_score", "ataque score"],
        "midfield_proxy": ["meio_score", "meio score"],
        "defense_proxy": ["defesa_score", "defesa score"],
        "goalkeeper_proxy": ["goleiro_score", "goleiro score"],
        "experience_proxy": ["experiencia_score", "experiência score"],
        "possession_proxy": ["posse_valor", "posse valor"],
        "pressing_proxy": ["pressao_valor", "pressão valor"],
        "intensity_proxy": ["intensidade_valor", "intensidade valor"],
    }
    strength_cols = {name: _first_existing(strengths, candidates) for name, candidates in strength_fields.items()}

    for _, row in strengths.iterrows():
        team = str(row[team_col]).strip()
        tactic_row = tactic_index.get(normalize_text(team))
        payload: dict[str, Any] = {
            "team": team,
            "snapshot_at": cutoff,
            "temporal_status": "BACKFILLED_PRE_TOURNAMENT_FACT",
            "fifa_ranking": "NA",
<<<<<<< HEAD
            "fifa_points": "NA",
            "recent_matches": "NA",
            "recent_points_per_match": "NA",
=======
            "recent_matches": "NA",
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
            "qualifying_performance": "NA",
            "recent_goals_for": "NA",
            "recent_goals_against": "NA",
            "source_dataset": config.path("team_strengths").relative_to(config.root).as_posix(),
<<<<<<< HEAD
            "ranking_source": "NA",
            "recent_form_source": "NA",
=======
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
        }
        for field, column in strength_cols.items():
            payload[field] = _value(row, column)
        if tactic_row is not None:
            for field, candidates in {
                "coach": ["Técnico", "Tecnico"],
                "tactical_style": ["Estilo técnico", "Estilo tecnico"],
                "base_system": ["Sistema base"],
            }.items():
                if payload.get(field, "NA") == "NA":
                    payload[field] = _value(tactic_row, _first_existing(tactics, candidates))
<<<<<<< HEAD
        ranking = ranking_index.get(normalize_text(team))
        if ranking is not None:
            payload["fifa_ranking"] = _value(ranking, "rank")
            payload["fifa_points"] = _value(ranking, "points")
            payload["ranking_source"] = _value(ranking, "source")
        form = recent_form.get(normalize_text(team))
        if form:
            payload.update(form)
            payload["recent_form_source"] = config.path("external_matches").relative_to(config.root).as_posix()
        team_rows.append(payload)
        for field, value in payload.items():
            if field in {"team", "snapshot_at", "source_dataset", "ranking_source", "recent_form_source"}:
=======
        team_rows.append(payload)
        for field, value in payload.items():
            if field in {"team", "snapshot_at", "source_dataset"}:
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
                continue
            field_lineage.append({
                "entity_type": "team",
                "entity_id": team,
                "field": field,
                "value_status": "MISSING" if str(value) == "NA" else "AVAILABLE",
                "available_at": cutoff,
                "temporal_status": payload["temporal_status"] if str(value) != "NA" else "UNAVAILABLE",
                "source_path": payload["source_dataset"] if str(value) != "NA" else "NA",
            })

    player_team_col = _first_existing(players, ["Seleção", "selecao", "team"])
    player_name_col = _first_existing(players, ["Jogador", "player"])
    player_rows: list[dict[str, Any]] = []
    player_map = {
        "age": ["Idade em 26/06/2026", "idade"],
        "club": ["Clube", "club"],
        "club_country": ["País do clube", "pais do clube"],
        "position": ["Posição", "posicao"],
        "national_team_caps": ["Caps seleção", "caps selecao"],
        "national_team_goals": ["Gols seleção", "gols selecao"],
        "league_strength_proxy": ["Score liga/clube", "score liga clube"],
        "player_quality_proxy": ["Índice proxy 0-10", "indice proxy 0 10"],
    }
    player_cols = {name: _first_existing(players, candidates) for name, candidates in player_map.items()}
    for idx, row in players.iterrows():
        team = _value(row, player_team_col)
        name = _value(row, player_name_col, f"player_{idx+1}")
        payload = {
            "player_id": f"{normalize_text(team).replace(' ', '_')}::{normalize_text(name).replace(' ', '_')}",
            "team": team,
            "player_name": name,
            "snapshot_at": cutoff,
            "temporal_status": "BACKFILLED_PRE_TOURNAMENT_FACT",
            "recent_minutes": "NA",
            "recent_goals": "NA",
            "recent_assists": "NA",
            "offensive_participation": "NA",
            "defensive_performance": "NA",
            "injury_status": "NA",
            "physical_condition": "NA",
            "source_dataset": config.path("players").relative_to(config.root).as_posix(),
        }
        for field, column in player_cols.items():
            payload[field] = _value(row, column)
        player_rows.append(payload)

    # Context fields are only populated when directly derivable from the official schedule.
    context_rows = []
    for _, match in matches.iterrows():
        context_rows.append({
            "match_id": int(match["jogo"]),
            "team1": match.get("equipe1", "NA"),
            "team2": match.get("equipe2", "NA"),
            "stadium": match.get("estadio", "NA"),
            "city": match.get("cidade", "NA"),
            "country": match.get("pais", "NA"),
            "weather_forecast": "NA",
            "travel_distance_team1_km": "NA",
            "travel_distance_team2_km": "NA",
            "timezone_adjustment_team1_hours": "NA",
            "timezone_adjustment_team2_hours": "NA",
            "rest_days_team1": "NA",
            "rest_days_team2": "NA",
            "snapshot_at": cutoff,
            "source_dataset": config.path("matches").relative_to(config.root).as_posix(),
        })

    teams_frame = pd.DataFrame(team_rows).sort_values("team")
    players_frame = pd.DataFrame(player_rows).sort_values(["team", "player_name"])
    context_frame = pd.DataFrame(context_rows).sort_values("match_id")
    lineage_frame = pd.DataFrame(field_lineage)
    out_dir = config.output("data", "pre_worldcup_state")
    atomic_write_csv(teams_frame, out_dir / "teams.csv")
    atomic_write_csv(players_frame, out_dir / "players.csv")
    atomic_write_csv(context_frame, out_dir / "context.csv")
    atomic_write_csv(lineage_frame, out_dir / "field_lineage.csv")

    missing_requirements = []
    for field in config.get("pre_worldcup_field_policy", {}).get("unavailable_without_archived_source", []):
        missing_requirements.append({
            "entity": "competition",
            "entity_id": config.get("competition_id"),
            "missing_field": field,
            "priority": "high" if field in {"fifa_ranking", "recent_matches", "injuries", "qualifying_performance"} else "medium",
            "status": "OPEN",
            "required_before": cutoff,
            "allowed_resolution": "archived source with published_at <= required_before, otherwise NA",
        })
    atomic_write_json({
        "generated_at": utc_now(),
        "snapshot_at": cutoff,
        "mode": config.get("reconstruction_mode"),
        "strict_temporal_warning": "Backfilled facts are allowed only when they describe pre-tournament attributes and never include tournament outcomes.",
        "items": missing_requirements,
    }, out_dir / "missing_information_queue.json")

    manifest = {
        "generated_at": utc_now(),
        "snapshot_at": cutoff,
        "competition_id": config.get("competition_id"),
        "teams": len(teams_frame),
        "players": len(players_frame),
        "context_matches": len(context_frame),
        "available_team_fields": [col for col in teams_frame.columns if col not in {"team", "snapshot_at", "source_dataset"} and not (teams_frame[col].astype(str) == "NA").all()],
        "unavailable_fields": config.get("pre_worldcup_field_policy", {}).get("unavailable_without_archived_source", []),
<<<<<<< HEAD
        "inputs": lineage([
            config.path("team_strengths"), config.path("team_tactics"), config.path("players"),
            config.path("matches"), config.path("fifa_rankings"), config.path("external_matches"),
        ], config.root),
=======
        "inputs": lineage([config.path("team_strengths"), config.path("team_tactics"), config.path("players"), config.path("matches")], config.root),
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
    }
    atomic_write_json(manifest, out_dir / "manifest.json")
    return manifest
