from __future__ import annotations

import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analysis import causal_analysis, game_learning, prediction_metrics, result_significance
from .config import TemporalConfig
from .data_check import check_pre_match_data, write_missing_queue
from .features import discover_features
from .io import atomic_write_csv, atomic_write_json, lineage, read_csv, read_json, sha256, utc_now
from .model import ModelParameters, TemporalPoissonEloModel
from .preworldcup import build_pre_worldcup_state
from .simulation import run_daily_simulation
from .state import TournamentState
from .temporal import assert_temporal_integrity, build_timeline, parse_timestamp, visible_results


PREDICTION_INDEX_COLUMNS = [
    "match_id", "date", "phase", "team1", "team2", "prediction_at",
    "predicted_outcome", "predicted_score", "probability_team1_win",
    "probability_draw", "probability_team2_win", "predicted_advancer",
    "confidence", "readiness_score", "prior_results_used", "temporal_status",
]
LEARNING_INDEX_COLUMNS = [
    "match_id", "date", "team1", "team2", "outcome_correct", "score_correct",
    "qualification_correct", "brier_score", "log_loss", "goal_absolute_error",
    "primary_factor", "significance",
]
KNOWLEDGE_LEDGER_COLUMNS = [
    "prediction_match_id", "prediction_cutoff", "record_type", "record_id",
    "available_at", "source",
]
DAILY_EVOLUTION_COLUMNS = [
    "date", "cutoff", "results_observed", "outcome_accuracy", "mean_log_loss",
    "mean_brier_score", "probability_temperature", "base_goals",
    "recalibration_accepted", "simulation_file",
]


def prepare(config: TemporalConfig) -> dict[str, Any]:
    pre = build_pre_worldcup_state(config)
    timeline = build_timeline(config)
    return {
        "generated_at": utc_now(),
        "pre_worldcup_state": pre,
        "timeline_rows": len(timeline),
        "status": "READY",
    }


def _clean_generated(config: TemporalConfig) -> None:
    for directory in (
        config.output("predictions", "pre_match"),
        config.output("learning", "game_analysis"),
        config.output("learning", "causal_analysis"),
        config.output("learning", "result_significance"),
        config.output("models", "versions"),
        config.output("simulations", "daily"),
    ):
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.glob("*.json"):
            path.unlink()
        for path in directory.glob("*.csv"):
            path.unlink()


def _save_model_version(
    config: TemporalConfig,
    model: TemporalPoissonEloModel,
    label: str,
    cutoff: Any,
    evaluated: list[dict[str, Any]],
    recalibration: dict[str, Any] | None,
) -> dict[str, Any]:
    recent = evaluated[-20:]
    metrics = {
        "samples": len(evaluated),
        "mean_log_loss": round(float(np.mean([item["log_loss"] for item in evaluated])), 8) if evaluated else "NA",
        "mean_brier_score": round(float(np.mean([item["brier_score"] for item in evaluated])), 8) if evaluated else "NA",
        "outcome_accuracy": round(float(np.mean([item["outcome_correct"] for item in evaluated])), 8) if evaluated else "NA",
        "recent_20_log_loss": round(float(np.mean([item["log_loss"] for item in recent])), 8) if recent else "NA",
    }
    payload = {
        "generated_at": utc_now(),
        "version": label,
        "training_cutoff": parse_timestamp(cutoff).isoformat(),
        "competition_id": config.get("competition_id"),
        "model_parameters": model.parameters.payload(),
        "metrics": metrics,
        "recalibration": recalibration or {"accepted": False, "reason": "initial_version"},
        "team_state": model.state.snapshot(),
        "temporal_integrity": "State contains only results whose result_available_at is not later than training_cutoff.",
    }
    path = config.output("models", "versions", f"{label}.json")
    atomic_write_json(payload, path)
    return payload



def _write_semantic_model_versions(config: TemporalConfig, timeline: pd.DataFrame) -> dict[str, str]:
    semantic_matches = {
        "model_after_group_stage": 72,
        "model_after_round_of_32": 88,
        "model_after_round_of_16": 96,
        "model_after_quarterfinals": 100,
        "model_after_semifinals": 102,
        "model_final": 104,
    }
    aliases: dict[str, str] = {}
    out_dir = config.output("models", "versions", "semantic")
    for alias, match_id in semantic_matches.items():
        row = timeline[timeline["match_id"] == match_id].iloc[0]
        local_date = parse_timestamp(row["result_available_at"]).tz_convert(str(config.get("schedule_timezone", "America/New_York"))).strftime("%Y-%m-%d")
        source = config.output("models", "versions", f"model_after_{local_date}.json")
        if not source.exists():
            continue
        payload = read_json(source, {})
        payload["version"] = alias
        payload["alias_of"] = source.relative_to(config.root).as_posix()
        payload["semantic_checkpoint_match_id"] = match_id
        target = out_dir / f"{alias}.json"
        atomic_write_json(payload, target)
        aliases[alias] = target.relative_to(config.root).as_posix()
    return aliases


def _initial_outlook(config: TemporalConfig, timeline: pd.DataFrame, model: TemporalPoissonEloModel) -> dict[str, Any]:
    cutoff = parse_timestamp(config.get("pre_tournament_cutoff"))
    rows = []
    for _, match in timeline[timeline["match_id"] <= 72].iterrows():
        prediction = model.predict(str(match["team1"]), str(match["team2"]), match["kickoff_at"], False)
        rows.append({
            "match_id": int(match["match_id"]),
            "date": match["date"],
            "team1": match["team1"],
            "team2": match["team2"],
            "predicted_outcome": prediction["predicted_outcome"],
            "predicted_score": prediction["predicted_score"],
            "probability_team1_win": prediction["probability_team1_win"],
            "probability_draw": prediction["probability_draw"],
            "probability_team2_win": prediction["probability_team2_win"],
            "confidence": prediction["confidence"],
            "cutoff": cutoff.isoformat(),
        })
    frame = pd.DataFrame(rows)
    atomic_write_csv(frame, config.output("predictions", "pre_worldcup_group_predictions.csv"))
    simulation = run_daily_simulation(config, timeline, model, cutoff)
    atomic_write_json(simulation, config.output("predictions", "initial_tournament_outlook.json"))
    return {"group_predictions": len(frame), "simulation": simulation}


def _knowledge_records(
    config: TemporalConfig,
    match: pd.Series,
    cutoff: Any,
    visible: pd.DataFrame,
    data_check: dict[str, Any],
) -> list[dict[str, Any]]:
    cutoff_ts = parse_timestamp(cutoff)
    pre_cutoff = parse_timestamp(config.get("pre_tournament_cutoff"))
    records = [
        {"record_type": "team_profile", "record_id": str(match["team1"]), "available_at": pre_cutoff.isoformat(), "source": "data/pre_worldcup_state/teams.csv"},
        {"record_type": "team_profile", "record_id": str(match["team2"]), "available_at": pre_cutoff.isoformat(), "source": "data/pre_worldcup_state/teams.csv"},
        {"record_type": "fixture", "record_id": int(match["match_id"]), "available_at": match["fixture_known_at"], "source": "data/temporal/matches_timeline.csv"},
    ]
    for _, row in visible.iterrows():
        records.append({
            "record_type": "official_result",
            "record_id": int(row["match_id"]),
            "available_at": row["result_available_at"],
            "source": "data/resultados_reais.csv",
        })
    for check in data_check["checks"]:
        if check["status"] == "AVAILABLE" and check["field"] in {"confirmed_lineup", "player_availability", "archived_news"}:
            records.append({
                "record_type": check["field"],
                "record_id": f"match_{int(match['match_id'])}",
                "available_at": cutoff_ts.isoformat(),
                "source": check["source"],
            })
    assert_temporal_integrity(records, cutoff_ts)
    return records


def replay(config: TemporalConfig, as_of: Any | None = None, clean: bool = True) -> dict[str, Any]:
    prepare(config)
    if clean:
        _clean_generated(config)
    timeline = read_csv(config.output("data", "temporal", "matches_timeline.csv"))
    team_profiles = read_csv(config.output("data", "pre_worldcup_state", "teams.csv"))
    state = TournamentState(team_profiles)
    model = TemporalPoissonEloModel(state, ModelParameters(), int(config.get("random_seed", 2026)))
    replay_limit = parse_timestamp(as_of) if as_of else pd.Timestamp.max.tz_localize("UTC")

    initial_version = _save_model_version(
        config, model, "model_pre_worldcup", config.get("pre_tournament_cutoff"), [], None
    )
    initial_outlook = _initial_outlook(config, timeline, model)

    events: list[tuple[pd.Timestamp, int, str, int]] = []
    for _, match in timeline.iterrows():
        match_id = int(match["match_id"])
        events.extend([
            (parse_timestamp(match["prediction_at"]), 2, "prediction", match_id),
            (parse_timestamp(match["result_available_at"]), 0, "result", match_id),
            (parse_timestamp(match["statistics_available_at"]), 1, "analysis", match_id),
        ])
    events = [event for event in events if event[0] <= replay_limit]
    events.sort(key=lambda item: (item[0], item[1], item[3]))
    grouped: dict[str, list[tuple[pd.Timestamp, int, str, int]]] = defaultdict(list)
    schedule_timezone = str(config.get("schedule_timezone", "America/New_York"))
    for event in events:
        grouped[event[0].tz_convert(schedule_timezone).strftime("%Y-%m-%d")].append(event)

    timeline_index = {int(row["match_id"]): row for _, row in timeline.iterrows()}
    predictions: dict[int, dict[str, Any]] = {}
    metrics_by_match: dict[int, dict[str, Any]] = {}
    check_results: list[dict[str, Any]] = []
    evaluation_records: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    team_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    knowledge_ledger: list[dict[str, Any]] = []
    prediction_index_rows: list[dict[str, Any]] = []
    learning_index_rows: list[dict[str, Any]] = []
    daily_evolution: list[dict[str, Any]] = []

    for day in sorted(grouped):
        day_events = sorted(grouped[day], key=lambda item: (item[0], item[1], item[3]))
        result_events = 0
        for event_time, _, event_type, match_id in day_events:
            match = timeline_index[match_id]
            if event_type == "prediction":
                if parse_timestamp(match["fixture_known_at"]) > event_time:
                    continue
                visible = visible_results(timeline, event_time)
                data_check = check_pre_match_data(config, match, event_time, team_profiles, visible)
                check_results.append(data_check)
                if data_check["status"] == "BLOCKED":
                    continue
                knowledge = _knowledge_records(config, match, event_time, visible, data_check)
                pred = model.predict(str(match["team1"]), str(match["team2"]), match["kickoff_at"], bool(match["is_knockout"]))
                pred.update({
                    "match_id": match_id,
                    "competition_id": config.get("competition_id"),
                    "date": match["date"],
                    "phase": match["phase"],
                    "group": match.get("group", "NA"),
                    "kickoff_at": match["kickoff_at"],
                    "prediction_at": event_time.isoformat(),
                    "data_readiness": data_check,
                    "data_available_at_prediction": knowledge,
                    "prior_result_ids": [int(value) for value in visible["match_id"].tolist()],
                    "temporal_integrity": {
                        "cutoff": event_time.isoformat(),
                        "max_input_available_at": max(parse_timestamp(row["available_at"]) for row in knowledge).isoformat(),
                        "current_match_result_used": False,
                        "status": "PASS",
                    },
                })
                predictions[match_id] = pred
                atomic_write_json(pred, config.output("predictions", "pre_match", f"match_{match_id:03d}.json"))
                prediction_index_rows.append({
                    "match_id": match_id,
                    "date": match["date"],
                    "phase": match["phase"],
                    "team1": pred["team1"],
                    "team2": pred["team2"],
                    "prediction_at": pred["prediction_at"],
                    "predicted_outcome": pred["predicted_outcome"],
                    "predicted_score": pred["predicted_score"],
                    "probability_team1_win": pred["probability_team1_win"],
                    "probability_draw": pred["probability_draw"],
                    "probability_team2_win": pred["probability_team2_win"],
                    "predicted_advancer": pred["predicted_advancer"],
                    "confidence": pred["confidence"],
                    "readiness_score": data_check["readiness_score"],
                    "prior_results_used": len(pred["prior_result_ids"]),
                    "temporal_status": "PASS",
                })
                for record in knowledge:
                    knowledge_ledger.append({
                        "prediction_match_id": match_id,
                        "prediction_cutoff": event_time.isoformat(),
                        **record,
                    })
            elif event_type == "result":
                if match_id not in predictions:
                    continue
                result_events += 1
                pred = predictions[match_id]
                metrics = prediction_metrics(pred, match)
                adjustment = model.update_after_result(
                    pred["team1"], pred["team2"], int(match["result_team1_goals"]), int(match["result_team2_goals"]), match["kickoff_at"], match["result_available_at"]
                )
                metrics["model_adjustment"] = adjustment
                metrics_by_match[match_id] = metrics
                evaluation_records.append(metrics)
                feature_rows.append({
                    "match_id": match_id,
                    "features": pred["features"],
                    "actual_goal_diff": int(match["result_team1_goals"]) - int(match["result_team2_goals"]),
                    "prediction_at": pred["prediction_at"],
                    **metrics,
                })
            elif event_type == "analysis":
                if match_id not in predictions or match_id not in metrics_by_match:
                    continue
                pred = predictions[match_id]
                metrics = metrics_by_match[match_id]
                causal = causal_analysis(config, pred, match)
                learning = game_learning(pred, metrics, causal, metrics["model_adjustment"])
                combined_history = team_history[pred["team1"]] + team_history[pred["team2"]]
                significance = result_significance(pred, metrics, causal, combined_history)
                atomic_write_json(causal, config.output("learning", "causal_analysis", f"match_{match_id:03d}.json"))
                atomic_write_json(learning, config.output("learning", "game_analysis", f"match_{match_id:03d}.json"))
                atomic_write_json(significance, config.output("learning", "result_significance", f"match_{match_id:03d}.json"))
                history_item = {"match_id": match_id, **metrics, "significance": significance["classification"]}
                team_history[pred["team1"]].append(history_item)
                team_history[pred["team2"]].append(history_item)
                learning_index_rows.append({
                    "match_id": match_id,
                    "date": match["date"],
                    "team1": pred["team1"],
                    "team2": pred["team2"],
                    "outcome_correct": metrics["outcome_correct"],
                    "score_correct": metrics["score_correct"],
                    "qualification_correct": metrics["qualification_correct"],
                    "brier_score": metrics["brier_score"],
                    "log_loss": metrics["log_loss"],
                    "goal_absolute_error": metrics["goal_absolute_error"],
                    "primary_factor": causal["primary_factor"]["factor"],
                    "significance": significance["classification"],
                })
        if result_events:
            recalibration = model.recalibrate(evaluation_records)
            cutoff = max(item[0] for item in day_events)
            version = _save_model_version(config, model, f"model_after_{day}", cutoff, evaluation_records, recalibration)
            simulation = run_daily_simulation(config, timeline, model, cutoff)
            atomic_write_json(simulation, config.output("simulations", "daily", f"simulation_after_{day}.json"))
            daily_evolution.append({
                "date": day,
                "cutoff": cutoff.isoformat(),
                "results_observed": len(evaluation_records),
                "outcome_accuracy": version["metrics"]["outcome_accuracy"],
                "mean_log_loss": version["metrics"]["mean_log_loss"],
                "mean_brier_score": version["metrics"]["mean_brier_score"],
                "probability_temperature": model.parameters.probability_temperature,
                "base_goals": model.parameters.base_goals,
                "recalibration_accepted": recalibration.get("accepted", False),
                "simulation_file": f"simulations/daily/simulation_after_{day}.json",
            })

    prediction_index = pd.DataFrame(prediction_index_rows, columns=PREDICTION_INDEX_COLUMNS)
    learning_index = pd.DataFrame(learning_index_rows, columns=LEARNING_INDEX_COLUMNS)
    knowledge_frame = pd.DataFrame(knowledge_ledger, columns=KNOWLEDGE_LEDGER_COLUMNS)
    evolution_frame = pd.DataFrame(daily_evolution, columns=DAILY_EVOLUTION_COLUMNS)
    if not prediction_index.empty:
        prediction_index = prediction_index.sort_values("match_id")
    if not learning_index.empty:
        learning_index = learning_index.sort_values("match_id")
    atomic_write_csv(prediction_index, config.output("predictions", "pre_match", "index.csv"))
    atomic_write_csv(learning_index, config.output("learning", "game_analysis", "index.csv"))
    atomic_write_csv(knowledge_frame, config.output("data", "temporal", "prediction_knowledge_ledger.csv"))
    atomic_write_csv(evolution_frame, config.output("models", "daily_model_evolution.csv"))
    queue = write_missing_queue(config, check_results)
    features = discover_features(config, feature_rows)
    semantic_versions = _write_semantic_model_versions(config, timeline)
    report = build_learning_report(config, timeline, prediction_index, learning_index, evolution_frame, model, initial_outlook, features)
    report["semantic_model_versions"] = semantic_versions
    atomic_write_json(report, config.output("reports", "worldcup_learning_report.json"))
    return {
        "generated_at": utc_now(),
        "competition_id": config.get("competition_id"),
        "as_of": replay_limit.isoformat() if replay_limit != pd.Timestamp.max.tz_localize("UTC") else "FULL_REPLAY",
        "predictions": len(prediction_index),
        "results_learned": len(learning_index),
        "model_versions": len(list(config.output("models", "versions").glob("*.json"))),
        "semantic_model_versions": semantic_versions,
        "missing_information": queue["summary"],
        "feature_discovery": {"status": features.get("status"), "accepted": len(features.get("accepted", []))},
        "report": report,
    }


def build_learning_report(
    config: TemporalConfig,
    timeline: pd.DataFrame,
    prediction_index: pd.DataFrame,
    learning_index: pd.DataFrame,
    evolution: pd.DataFrame,
    model: TemporalPoissonEloModel,
    initial_outlook: dict[str, Any],
    features: dict[str, Any],
) -> dict[str, Any]:
    if learning_index.empty:
        metrics = {}
        largest_errors = []
        largest_hits = []
    else:
        metrics = {
            "matches_evaluated": len(learning_index),
            "outcome_accuracy": round(float(learning_index["outcome_correct"].astype(bool).mean()), 6),
            "exact_score_accuracy": round(float(learning_index["score_correct"].astype(bool).mean()), 6),
            "mean_log_loss": round(float(pd.to_numeric(learning_index["log_loss"]).mean()), 6),
            "mean_brier_score": round(float(pd.to_numeric(learning_index["brier_score"]).mean()), 6),
            "mean_goal_absolute_error": round(float(pd.to_numeric(learning_index["goal_absolute_error"]).mean()), 6),
        }
        largest_errors = learning_index.sort_values("log_loss", ascending=False).head(10).to_dict(orient="records")
        largest_hits = learning_index.sort_values(["log_loss", "goal_absolute_error"]).head(10).to_dict(orient="records")
    final_rankings = sorted([
        {
            "team": state.team,
            "final_rating": round(state.rating, 4),
            "games_observed": state.games,
            "points": state.points,
            "goals_for": state.goals_for,
            "goals_against": state.goals_against,
            "form_points": round(state.form_points, 4),
        }
        for state in model.state.teams.values()
    ], key=lambda item: item["final_rating"], reverse=True)
    factor_counts = learning_index["primary_factor"].value_counts().to_dict() if not learning_index.empty else {}
    significance_counts = learning_index["significance"].value_counts().to_dict() if not learning_index.empty else {}

    initial_frame = read_csv(config.output("predictions", "pre_worldcup_group_predictions.csv"), required=False)
    initial_eval_rows = []
    timeline_lookup = timeline.set_index("match_id")
    for _, row in initial_frame.iterrows():
        match_id = int(row["match_id"])
        if match_id not in timeline_lookup.index:
            continue
        real = timeline_lookup.loc[match_id]
        g1, g2 = int(real["result_team1_goals"]), int(real["result_team2_goals"])
        actual_index = 0 if g1 > g2 else (1 if g1 == g2 else 2)
        probs = np.array([row["probability_team1_win"], row["probability_draw"], row["probability_team2_win"]], dtype=float)
        one_hot = np.zeros(3); one_hot[actual_index] = 1.0
        actual_outcome = row["team1"] if actual_index == 0 else ("Empate" if actual_index == 1 else row["team2"])
        initial_eval_rows.append({
            "outcome_correct": row["predicted_outcome"] == actual_outcome,
            "score_correct": str(row["predicted_score"]) == f"{g1}-{g2}",
            "log_loss": -math.log(max(1e-12, probs[actual_index])),
            "brier_score": float(np.mean((probs - one_hot) ** 2)),
        })
    initial_eval = pd.DataFrame(initial_eval_rows)
    sequential_group = learning_index[pd.to_numeric(learning_index["match_id"], errors="coerce") <= 72].copy() if not learning_index.empty else pd.DataFrame()

    def compact_metrics(frame: pd.DataFrame) -> dict[str, Any]:
        if frame.empty:
            return {"samples": 0}
        return {
            "samples": len(frame),
            "outcome_accuracy": round(float(frame["outcome_correct"].astype(bool).mean()), 6),
            "exact_score_accuracy": round(float(frame["score_correct"].astype(bool).mean()), 6),
            "mean_log_loss": round(float(pd.to_numeric(frame["log_loss"]).mean()), 6),
            "mean_brier_score": round(float(pd.to_numeric(frame["brier_score"]).mean()), 6),
        }

    initial_metrics = compact_metrics(initial_eval)
    progressive_metrics = compact_metrics(sequential_group)
    comparison = {
        "comparison_scope": "Same 72 group-stage matches: frozen pre-tournament model versus walk-forward predictions that used only earlier available results.",
        "frozen_pre_worldcup_model": initial_metrics,
        "progressive_walk_forward_model": progressive_metrics,
        "improvement": {
            "outcome_accuracy_delta": round(progressive_metrics.get("outcome_accuracy", 0) - initial_metrics.get("outcome_accuracy", 0), 6),
            "exact_score_accuracy_delta": round(progressive_metrics.get("exact_score_accuracy", 0) - initial_metrics.get("exact_score_accuracy", 0), 6),
            "log_loss_reduction": round(initial_metrics.get("mean_log_loss", 0) - progressive_metrics.get("mean_log_loss", 0), 6),
            "brier_score_reduction": round(initial_metrics.get("mean_brier_score", 0) - progressive_metrics.get("mean_brier_score", 0), 6),
        },
        "interpretation": "The final model is not retroactively evaluated on past matches; the valid comparison is frozen versus contemporaneous walk-forward prediction.",
    }

    report = {
        "generated_at": utc_now(),
        "competition_id": config.get("competition_id"),
        "objective": "Reconstruct the tournament using only information available at each historical cutoff.",
        "initial_pre_worldcup_outlook": {
            "group_matches_predicted": initial_outlook["group_predictions"],
            "initial_simulation_file": "predictions/initial_tournament_outlook.json",
            "initial_model_version": "models/versions/model_pre_worldcup.json",
        },
        "daily_evolution": evolution.to_dict(orient="records") if not evolution.empty else [],
        "pre_worldcup_vs_progressive_learning": comparison,
        "final_metrics": metrics,
        "largest_errors": largest_errors,
        "largest_hits": largest_hits,
        "important_variables": features.get("accepted", []),
        "decisive_observed_factors": factor_counts,
        "result_significance_distribution": significance_counts,
        "final_team_state": final_rankings,
        "final_model_parameters": model.parameters.payload(),
        "temporal_safety": {
            "current_match_result_in_prediction": False,
            "future_knockout_teams_hidden": True,
            "results_visible_only_after_result_available_at": True,
            "backfilled_data_policy": "Pre-tournament facts and post-match facts are explicitly labeled; no tournament outcome is backdated.",
        },
        "limitations": [
            "Pre-Cup FIFA ranking, recent national-team matches, injuries and player minutes were not present with archived timestamps and remain NA.",
            "Post-match causal outputs are evidence-based associations, not causal identification from a randomized design.",
            "Champion probabilities are intentionally unavailable before the round-of-32 teams become historically known; group qualification is simulated instead.",
            "Player-level post-match evidence covers all matches, but minutes, xG, xA and player ratings remain unavailable and stay NA.",
        ],
    }
    atomic_write_json(report, config.output("reports", "worldcup_learning_report.json"))
    return report
