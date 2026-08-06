from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from sports_engine.io import normalize_text

from .config import TemporalConfig
from .io import read_csv


_DATASET_CACHE: dict[tuple[str, int, int], pd.DataFrame] = {}


def _cached_dataset(config: TemporalConfig, dataset_name: str) -> pd.DataFrame:
    path = config.path(dataset_name)
    if not path.exists():
        return pd.DataFrame()
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _DATASET_CACHE.get(key)
    if cached is None:
        # Remove stale versions of the same path before caching the current file.
        for old_key in [item for item in _DATASET_CACHE if item[0] == str(path) and item != key]:
            _DATASET_CACHE.pop(old_key, None)
        cached = read_csv(path, required=False)
        _DATASET_CACHE[key] = cached
    return cached


def outcome_name(team1: str, team2: str, goals1: int, goals2: int) -> str:
    if goals1 > goals2:
        return team1
    if goals2 > goals1:
        return team2
    return "Empate"


def prediction_metrics(prediction: dict[str, Any], result: pd.Series) -> dict[str, Any]:
    team1, team2 = str(prediction["team1"]), str(prediction["team2"])
    g1, g2 = int(result["result_team1_goals"]), int(result["result_team2_goals"])
    actual = outcome_name(team1, team2, g1, g2)
    probs = [float(prediction["probability_team1_win"]), float(prediction["probability_draw"]), float(prediction["probability_team2_win"])]
    actual_index = 0 if actual == team1 else (1 if actual == "Empate" else 2)
    one_hot = np.zeros(3); one_hot[actual_index] = 1.0
    brier = float(np.mean((np.array(probs) - one_hot) ** 2))
    log_loss = float(-math.log(max(1e-12, probs[actual_index])))
    predicted_score = str(prediction["predicted_score"])
    score_match = predicted_score == f"{g1}-{g2}"
    result_winner = str(result.get("result_winner", actual))
    penalty_winner = str(result.get("penalty_winner", "NA"))
    actual_advancer = penalty_winner if penalty_winner not in {"NA", "nan", ""} else result_winner
    qualification_correct = prediction.get("predicted_advancer") == actual_advancer if prediction.get("predicted_advancer") != "NA" else "NA"
    return {
        "actual_outcome": actual,
        "actual_score": f"{g1}-{g2}",
        "actual_advancer": actual_advancer,
        "outcome_correct": prediction["predicted_outcome"] == actual,
        "score_correct": score_match,
        "qualification_correct": qualification_correct,
        "brier_score": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "goal_absolute_error": abs(int(predicted_score.split("-")[0]) - g1) + abs(int(predicted_score.split("-")[1]) - g2),
        "actual_index": actual_index,
        "raw_probabilities": probs,
        "total_goals": g1 + g2,
    }


def _match_stats(config: TemporalConfig, match_id: int) -> pd.DataFrame:
    stats = _cached_dataset(config, "team_match_stats")
    if stats.empty or "jogo" not in stats.columns:
        return pd.DataFrame()
    return stats[pd.to_numeric(stats["jogo"], errors="coerce") == match_id].copy()


def _match_events(config: TemporalConfig, match_id: int) -> pd.DataFrame:
    events = _cached_dataset(config, "events")
    if events.empty or "jogo" not in events.columns:
        return pd.DataFrame()
    return events[pd.to_numeric(events["jogo"], errors="coerce") == match_id].copy()




def _match_player_stats(config: TemporalConfig, match_id: int) -> pd.DataFrame:
    players = _cached_dataset(config, "player_match_stats")
    if players.empty:
        return pd.DataFrame()
    match_col = "match_id" if "match_id" in players.columns else ("jogo" if "jogo" in players.columns else None)
    if not match_col:
        return pd.DataFrame()
    return players[pd.to_numeric(players[match_col], errors="coerce") == match_id].copy()


def _individual_evidence(players: pd.DataFrame) -> list[dict[str, Any]]:
    if players.empty:
        return []
    fields = {
        "goals": ("goals", "stat_totalgoals"),
        "assists": ("assists", "stat_goalassists"),
        "shots": ("shots", "stat_totalshots"),
        "shots_on_target": ("stat_shotsontarget",),
        "saves": ("stat_saves",),
        "red_cards": ("stat_redcards",),
        "yellow_cards": ("stat_yellowcards",),
        "own_goals": ("stat_owngoals",),
    }
    resolved = {}
    for target, candidates in fields.items():
        resolved[target] = next((column for column in candidates if column in players.columns), None)
    rows = []
    for _, row in players.iterrows():
        observed = {}
        for target, column in resolved.items():
            if not column:
                continue
            value = pd.to_numeric(row.get(column), errors="coerce")
            if pd.notna(value) and float(value) != 0:
                observed[target] = int(value) if float(value).is_integer() else float(value)
        if not observed:
            continue
        rows.append({
            "team": row.get("team", row.get("selecao", "NA")),
            "player_id": row.get("player_id", row.get("athlete_id", "NA")),
            "player": row.get("player_name", row.get("player", row.get("jogador", "NA"))),
            "position": row.get("position", "NA"),
            "starter": row.get("starter", "NA"),
            "observed_stats": observed,
            "source": row.get("source", "NA"),
        })
    def order(item: dict[str, Any]) -> tuple[float, ...]:
        stats = item["observed_stats"]
        return (
            float(stats.get("goals", 0)),
            float(stats.get("assists", 0)),
            float(stats.get("saves", 0)),
            float(stats.get("shots_on_target", 0)),
            float(stats.get("shots", 0)),
            -float(stats.get("red_cards", 0)),
        )
    return sorted(rows, key=order, reverse=True)[:12]

def _team_stat(stats: pd.DataFrame, team: str, field: str) -> float | None:
    if stats.empty or field not in stats.columns:
        return None
    team_col = "team_norm" if "team_norm" in stats.columns else "team_espn"
    rows = stats[stats[team_col].astype(str).map(normalize_text) == normalize_text(team)]
    if rows.empty:
        return None
    value = pd.to_numeric(rows.iloc[0][field], errors="coerce")
    return None if pd.isna(value) else float(value)


def causal_analysis(config: TemporalConfig, prediction: dict[str, Any], result: pd.Series) -> dict[str, Any]:
    match_id = int(result["match_id"])
    team1, team2 = prediction["team1"], prediction["team2"]
    g1, g2 = int(result["result_team1_goals"]), int(result["result_team2_goals"])
    stats = _match_stats(config, match_id)
    events = _match_events(config, match_id)
    players = _match_player_stats(config, match_id)
    first_goal = None
    red_cards = {team1: 0, team2: 0}
    substitutions = {team1: 0, team2: 0}
    if not events.empty:
        scoring = events[events.get("scoring_play", False).astype(str).str.lower().isin({"true", "1"})] if "scoring_play" in events.columns else pd.DataFrame()
        if not scoring.empty:
            row = scoring.iloc[0]
            first_goal = {"team": row.get("team_espn", row.get("team", "NA")), "clock": row.get("clock", "NA"), "player": row.get("player", "NA"), "text": row.get("text", "NA")}
        type_series = events.get("type_text", events.get("type", pd.Series(index=events.index, dtype=str))).astype(str).str.lower()
        team_series = events.get("team", events.get("team_espn", pd.Series(index=events.index, dtype=str))).astype(str).map(normalize_text)
        red_flag = events.get("red_card", pd.Series(False, index=events.index)).astype(str).str.lower().isin({"true", "1"})
        substitution_flag = events.get("substitution", pd.Series(False, index=events.index)).astype(str).str.lower().isin({"true", "1"})
        for team in (team1, team2):
            team_mask = team_series == normalize_text(team)
            red_cards[team] = int((team_mask & (red_flag | type_series.str.contains("red card|cartão vermelho", regex=True))).sum())
            substitutions[team] = int((team_mask & (substitution_flag | type_series.str.contains("substitution|substituição", regex=True))).sum())
    for team in (team1, team2):
        stats_red = _team_stat(stats, team, "stat_redCards")
        if stats_red is not None:
            red_cards[team] = int(stats_red)

    individual_evidence = _individual_evidence(players)
    stat_fields = ["stat_possessionPct", "stat_totalShots", "stat_shotsOnTarget", "stat_redCards", "stat_yellowCards", "stat_saves"]
    team_stats = {team: {field: _team_stat(stats, team, field) for field in stat_fields} for team in (team1, team2)}
    shots1 = team_stats[team1].get("stat_totalShots")
    shots2 = team_stats[team2].get("stat_totalShots")
    sot1 = team_stats[team1].get("stat_shotsOnTarget")
    sot2 = team_stats[team2].get("stat_shotsOnTarget")
    eff1 = g1 / shots1 if shots1 and shots1 > 0 else None
    eff2 = g2 / shots2 if shots2 and shots2 > 0 else None

    factors = []
    if red_cards[team1] != red_cards[team2]:
        factors.append({"factor": "red_card_imbalance", "direction": team2 if red_cards[team1] > red_cards[team2] else team1, "evidence": red_cards, "strength": "high"})
    if sot1 is not None and sot2 is not None and abs(sot1 - sot2) >= 3:
        factors.append({"factor": "shots_on_target_dominance", "direction": team1 if sot1 > sot2 else team2, "evidence": {team1: sot1, team2: sot2}, "strength": "medium"})
    if eff1 is not None and eff2 is not None and abs(eff1 - eff2) >= 0.12:
        factors.append({"factor": "finishing_efficiency", "direction": team1 if eff1 > eff2 else team2, "evidence": {team1: round(eff1, 4), team2: round(eff2, 4)}, "strength": "medium"})
    if first_goal:
        factors.append({"factor": "first_goal", "direction": first_goal["team"], "evidence": first_goal, "strength": "contextual"})
    if str(result.get("penalty_winner", "NA")) not in {"NA", "nan", ""}:
        factors.append({"factor": "penalty_shootout", "direction": result.get("penalty_winner"), "evidence": result.get("penalty_score"), "strength": "decisive"})
    if not factors:
        factors.append({"factor": "scoreline_only", "direction": outcome_name(team1, team2, g1, g2), "evidence": f"{g1}-{g2}", "strength": "low"})

    return {
        "match_id": match_id,
        "question": "Por que este jogo terminou assim?",
        "answer_scope": "Associations supported by available match evidence; not a causal proof.",
        "first_goal": first_goal or "NA",
        "red_cards": red_cards,
        "substitutions_detected": substitutions,
        "team_stats": team_stats,
        "individual_evidence": individual_evidence,
        "efficiency": {team1: round(eff1, 6) if eff1 is not None else "NA", team2: round(eff2, 6) if eff2 is not None else "NA"},
        "important_factors": factors,
        "primary_factor": factors[0],
        "evidence_status": "POST_MATCH_BACKFILLED_FACT" if not stats.empty or not events.empty or not players.empty else "RESULT_ONLY",
    }


def game_learning(prediction: dict[str, Any], metrics: dict[str, Any], causal: dict[str, Any], adjustment: dict[str, Any]) -> dict[str, Any]:
    contributions = prediction.get("feature_contributions", {})
    strongest = sorted(contributions.items(), key=lambda item: abs(float(item[1])), reverse=True)[:3]
    if metrics["outcome_correct"]:
        error = "direction_correct"
        explanation = "The highest-probability 1X2 outcome matched the observed result."
    else:
        error = "outcome_missed"
        explanation = "The observed 1X2 outcome differed from the model's highest-probability outcome."
    if causal.get("primary_factor", {}).get("factor") == "red_card_imbalance":
        explanation += " A red-card imbalance was observed and may explain part of the divergence."
    elif causal.get("primary_factor", {}).get("factor") == "finishing_efficiency":
        explanation += " Finishing efficiency differed materially between the teams."
    return {
        "match_id": prediction["match_id"],
        "prediction_error": error,
        "explanation": explanation,
        "predicted_outcome": prediction["predicted_outcome"],
        "actual_outcome": metrics["actual_outcome"],
        "brier_score": metrics["brier_score"],
        "log_loss": metrics["log_loss"],
        "goal_absolute_error": metrics["goal_absolute_error"],
        "strongest_pre_match_factors": [{"factor": key, "contribution": value} for key, value in strongest],
        "important_post_match_factor": causal.get("primary_factor"),
        "model_adjustment": adjustment,
        "learning_scope": "Online team-state update and conservative probability recalibration; no future matches used.",
    }


def result_significance(
    prediction: dict[str, Any], metrics: dict[str, Any], causal: dict[str, Any], team_history: list[dict[str, Any]]
) -> dict[str, Any]:
    top_prob = max(float(prediction["probability_team1_win"]), float(prediction["probability_draw"]), float(prediction["probability_team2_win"]))
    surprise = 1.0 - [float(prediction["probability_team1_win"]), float(prediction["probability_draw"]), float(prediction["probability_team2_win"])][metrics["actual_index"]]
    recent_same_direction = sum(item.get("outcome_correct") is False and item.get("actual_outcome") == metrics["actual_outcome"] for item in team_history[-3:])
    factor = causal.get("primary_factor", {}).get("factor")
    if len(team_history) < 2:
        classification = "erro_estatistico" if surprise < 0.45 else "acaso"
        confidence = "low"
    elif factor in {"red_card_imbalance", "penalty_shootout"} and surprise > 0.45:
        classification = "acaso"
        confidence = "medium"
    elif recent_same_direction >= 2 and surprise > 0.35:
        classification = "mudanca_estrutural"
        confidence = "medium"
    elif surprise > 0.50 and factor in {"shots_on_target_dominance", "finishing_efficiency"}:
        classification = "tendencia_real"
        confidence = "medium"
    else:
        classification = "erro_estatistico"
        confidence = "medium" if len(team_history) >= 3 else "low"
    return {
        "match_id": prediction["match_id"],
        "classification": classification,
        "confidence": confidence,
        "surprise_index": round(float(surprise), 6),
        "pre_match_top_probability": round(top_prob, 6),
        "quality_context": {
            "rating_diff": prediction.get("features", {}).get("rating_diff", "NA"),
            "schedule_strength_diff": prediction.get("features", {}).get("schedule_strength_diff", "NA"),
        },
        "repetition_evidence": recent_same_direction,
        "decisive_event": factor,
        "interpretation_rule": "Classification is evidence-based and provisional; it does not assert psychological or tactical causes without observations.",
    }
