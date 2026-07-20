#!/usr/bin/env python3
"""Exporta artefatos do cérebro temporal para um único bundle JS do dashboard.

O frontend é estático e funciona no GitHub Pages sem servidor ou fetch assíncrono.
Nenhum dado é estimado neste exportador: ele apenas compacta os artefatos existentes.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "model-analytics-data.js"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any, default: Any = None) -> Any:
    if value is None or value == "" or str(value).upper() in {"NA", "NAN", "NONE"}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: Any = None) -> Any:
    val = number(value, default)
    if val is default:
        return default
    return int(val)


def round_value(value: Any, digits: int = 6) -> Any:
    val = number(value)
    return round(val, digits) if val is not None else None


def top_abs(mapping: dict[str, Any] | None, limit: int = 6) -> list[dict[str, Any]]:
    if not mapping:
        return []
    rows = []
    for key, value in mapping.items():
        val = number(value)
        if val is not None:
            rows.append({"factor": key, "contribution": round(val, 6)})
    return sorted(rows, key=lambda row: abs(row["contribution"]), reverse=True)[:limit]


def actual_winner(row: dict[str, str]) -> str:
    winner = (row.get("vencedor_penaltis_real") or "").strip()
    if winner and winner.lower() != "nan":
        return winner
    return (row.get("vencedor_real") or "Empate").strip()


def normalize_status(value: Any) -> str:
    if value is None:
        return "NA"
    return str(value)


def build() -> dict[str, Any]:
    report = load_json(ROOT / "reports" / "worldcup_learning_report.json", {})
    integration = load_json(ROOT / "reports" / "wc2026_complete_data_integration.json", {})
    completeness = load_json(ROOT / "reports" / "data_completeness_report.json", {})
    features_registry = load_json(ROOT / "models" / "features_registry.json", {})
    feature_discovery = load_json(ROOT / "models" / "temporal_feature_discovery.json", {})
    results = {integer(row.get("jogo")): row for row in load_csv(ROOT / "data" / "resultados_reais.csv")}
    matches = {integer(row.get("jogo")): row for row in load_csv(ROOT / "data" / "matches.csv")}
    learning_index = {integer(row.get("match_id")): row for row in load_csv(ROOT / "learning" / "game_analysis" / "index.csv")}

    predictions: list[dict[str, Any]] = []
    for path in sorted((ROOT / "predictions" / "pre_match").glob("match_*.json")):
        pred = load_json(path, {})
        match_id = integer(pred.get("match_id"))
        if match_id is None:
            continue
        result = results.get(match_id, {})
        fixture = matches.get(match_id, {})
        learning = load_json(ROOT / "learning" / "game_analysis" / f"match_{match_id:03d}.json", {})
        causal = load_json(ROOT / "learning" / "causal_analysis" / f"match_{match_id:03d}.json", {})
        significance = load_json(ROOT / "learning" / "result_significance" / f"match_{match_id:03d}.json", {})
        index_row = learning_index.get(match_id, {})
        readiness = pred.get("data_readiness") or {}
        missing_fields = [
            check.get("field")
            for check in readiness.get("checks", [])
            if str(check.get("status", "")).startswith("NA")
        ]
        team_stats = causal.get("team_stats") or {}
        first_goal = causal.get("first_goal") or {}
        if not isinstance(first_goal, dict):
            first_goal = {}
        primary = causal.get("primary_factor") or {}
        if not isinstance(primary, dict):
            primary = {"factor": str(primary)} if primary else {}
        predictions.append({
            "matchId": match_id,
            "date": pred.get("date") or fixture.get("data"),
            "phase": pred.get("phase") or fixture.get("fase"),
            "group": pred.get("group") or fixture.get("grupo"),
            "kickoffAt": pred.get("kickoff_at"),
            "predictionAt": pred.get("prediction_at"),
            "team1": pred.get("team1") or result.get("equipe1"),
            "team2": pred.get("team2") or result.get("equipe2"),
            "predictedOutcome": pred.get("predicted_outcome"),
            "predictedAdvancer": pred.get("predicted_advancer"),
            "predictedScore": pred.get("predicted_score"),
            "actualScore": result.get("placar_real"),
            "actualWinner": actual_winner(result),
            "penaltyScore": result.get("placar_penaltis_real") or None,
            "expectedGoalsTeam1": round_value(pred.get("expected_goals_team1"), 4),
            "expectedGoalsTeam2": round_value(pred.get("expected_goals_team2"), 4),
            "probabilityTeam1Win": round_value(pred.get("probability_team1_win"), 6),
            "probabilityDraw": round_value(pred.get("probability_draw"), 6),
            "probabilityTeam2Win": round_value(pred.get("probability_team2_win"), 6),
            "probabilityTeam1Advance": round_value(pred.get("probability_team1_advance"), 6),
            "probabilityTeam2Advance": round_value(pred.get("probability_team2_advance"), 6),
            "confidence": round_value(pred.get("confidence"), 6),
            "readinessStatus": readiness.get("status", "NA"),
            "readinessScore": round_value(readiness.get("readiness_score"), 4),
            "missingFields": missing_fields,
            "topScorelines": pred.get("top_scorelines", [])[:8],
            "featureContributions": top_abs(pred.get("feature_contributions"), 8),
            "features": pred.get("features", {}),
            "modelParameters": pred.get("model_parameters", {}),
            "outcomeCorrect": str(index_row.get("outcome_correct", "")).lower() == "true",
            "scoreCorrect": str(index_row.get("score_correct", "")).lower() == "true",
            "brierScore": round_value(learning.get("brier_score") or index_row.get("brier_score"), 6),
            "logLoss": round_value(learning.get("log_loss") or index_row.get("log_loss"), 6),
            "goalAbsoluteError": integer(learning.get("goal_absolute_error") or index_row.get("goal_absolute_error"), 0),
            "predictionError": learning.get("prediction_error"),
            "explanation": learning.get("explanation"),
            "modelAdjustment": learning.get("model_adjustment", {}),
            "primaryFactor": primary.get("factor") or index_row.get("primary_factor") or "NA",
            "primaryFactorDirection": primary.get("direction"),
            "primaryFactorStrength": primary.get("strength"),
            "significance": significance.get("classification") or index_row.get("significance") or "NA",
            "significanceConfidence": significance.get("confidence"),
            "surpriseIndex": round_value(significance.get("surprise_index"), 6),
            "firstGoal": {
                "team": first_goal.get("team"),
                "clock": first_goal.get("clock"),
                "player": first_goal.get("player"),
            } if first_goal else None,
            "teamStats": team_stats,
            "importantFactors": causal.get("important_factors", [])[:6],
            "evidenceStatus": causal.get("evidence_status", "NA"),
        })

    evolution = []
    for row in load_csv(ROOT / "models" / "daily_model_evolution.csv"):
        evolution.append({
            "date": row.get("date"),
            "cutoff": row.get("cutoff"),
            "resultsObserved": integer(row.get("results_observed"), 0),
            "outcomeAccuracy": round_value(row.get("outcome_accuracy"), 8),
            "meanLogLoss": round_value(row.get("mean_log_loss"), 8),
            "meanBrierScore": round_value(row.get("mean_brier_score"), 8),
            "probabilityTemperature": round_value(row.get("probability_temperature"), 6),
            "baseGoals": round_value(row.get("base_goals"), 6),
            "recalibrationAccepted": str(row.get("recalibration_accepted", "")).lower() == "true",
            "simulationFile": row.get("simulation_file"),
        })

    simulations = []
    evolution_by_date = {row["date"]: row for row in evolution}
    for path in sorted((ROOT / "simulations" / "daily").glob("simulation_after_*.json")):
        data = load_json(path, {})
        date = path.stem.replace("simulation_after_", "")
        knockout = data.get("knockout") or {}
        group = data.get("group_stage") or {}
        champions = knockout.get("champion_probabilities")
        if not isinstance(champions, list):
            champions = []
        qualification = group.get("qualification_probabilities")
        if not isinstance(qualification, list):
            qualification = []
        simulations.append({
            "date": date,
            "cutoff": data.get("cutoff"),
            "resultsObserved": evolution_by_date.get(date, {}).get("resultsObserved", 0),
            "knockoutStatus": knockout.get("status", "UNAVAILABLE"),
            "knockoutReason": knockout.get("reason"),
            "iterations": knockout.get("iterations") or group.get("iterations"),
            "champions": [{
                "team": item.get("team"),
                "champion": round_value(item.get("probability_champion"), 6),
                "final": round_value(item.get("probability_final"), 6),
                "semifinal": round_value(item.get("probability_semifinal"), 6),
            } for item in champions],
            "qualification": [{
                "team": item.get("team"),
                "group": item.get("group"),
                "qualify": round_value(item.get("probability_qualify"), 6),
                "first": round_value(item.get("probability_first"), 6),
                "second": round_value(item.get("probability_second"), 6),
                "third": round_value(item.get("probability_third"), 6),
            } for item in qualification],
        })

    versions = []
    for path in sorted((ROOT / "models" / "versions").glob("model_*.json")):
        data = load_json(path, {})
        versions.append({
            "version": data.get("version") or path.stem,
            "trainingCutoff": data.get("training_cutoff"),
            "parameters": data.get("model_parameters", {}),
            "metrics": data.get("metrics", {}),
            "recalibration": data.get("recalibration", {}),
            "temporalIntegrity": data.get("temporal_integrity"),
            "semantic": False,
        })
    semantic_versions = []
    semantic_dir = ROOT / "models" / "versions" / "semantic"
    if semantic_dir.exists():
        for path in sorted(semantic_dir.glob("*.json")):
            data = load_json(path, {})
            semantic_versions.append({
                "version": path.stem,
                "sourceVersion": data.get("alias_of") or data.get("version"),
                "trainingCutoff": data.get("training_cutoff"),
                "parameters": data.get("model_parameters", {}),
                "metrics": data.get("metrics", {}),
                "checkpointMatchId": data.get("semantic_checkpoint_match_id"),
                "temporalIntegrity": data.get("temporal_integrity"),
                "semantic": True,
            })

    factors = Counter(p.get("primaryFactor") for p in predictions if p.get("primaryFactor") not in {None, "NA"})
    significance = Counter(p.get("significance") for p in predictions if p.get("significance") not in {None, "NA"})
    readiness = Counter(p.get("readinessStatus") for p in predictions)

    initial = load_json(ROOT / "predictions" / "initial_tournament_outlook.json", {})
    initial_knockout = (initial.get("knockout") or {}).get("champion_probabilities")
    if not isinstance(initial_knockout, list):
        initial_knockout = []

    final_metrics = report.get("final_metrics", {})
    comparison = report.get("pre_worldcup_vs_progressive_learning", {})

    return {
        "generatedAt": report.get("generated_at") or integration.get("generated_at") or "NA",
        "competitionId": report.get("competition_id", "world_cup_2026"),
        "summary": {
            "matches": len(predictions),
            "outcomeCorrect": sum(1 for p in predictions if p["outcomeCorrect"]),
            "scoreCorrect": sum(1 for p in predictions if p["scoreCorrect"]),
            "recalibrationsAccepted": sum(1 for row in evolution if row["recalibrationAccepted"]),
            "modelVersions": len(versions),
            "semanticVersions": len(semantic_versions),
            "simulationSnapshots": len(simulations),
            "featuresAccepted": len(feature_discovery.get("accepted", [])),
            "activeConflicts": (integration.get("summary") or {}).get("active_conflicts", 0),
        },
        "finalMetrics": final_metrics,
        "comparison": comparison,
        "temporalSafety": report.get("temporal_safety", {}),
        "limitations": report.get("limitations", []),
        "dailyEvolution": evolution,
        "predictions": predictions,
        "features": report.get("important_variables") or feature_discovery.get("accepted", []),
        "featureRegistry": features_registry.get("features", []),
        "learning": {
            "factorDistribution": [{"factor": key, "count": value} for key, value in factors.most_common()],
            "significanceDistribution": [{"classification": key, "count": value} for key, value in significance.most_common()],
            "readinessDistribution": [{"status": key, "count": value} for key, value in readiness.most_common()],
            "largestErrors": report.get("largest_errors", []),
            "largestHits": report.get("largest_hits", []),
            "decisiveObservedFactors": report.get("decisive_observed_factors", {}),
        },
        "simulations": simulations,
        "initialChampionProbabilities": [{
            "team": item.get("team"),
            "champion": round_value(item.get("probability_champion"), 6),
            "final": round_value(item.get("probability_final"), 6),
            "semifinal": round_value(item.get("probability_semifinal"), 6),
        } for item in initial_knockout],
        "versions": versions,
        "semanticVersions": semantic_versions,
        "finalTeamState": report.get("final_team_state", []),
        "finalModelParameters": report.get("final_model_parameters", {}),
        "completeness": {
            "summary": completeness.get("summary", {}),
            "coverage": completeness.get("coverage", {}),
            "queuePath": completeness.get("queue_path"),
        },
        "integrationSummary": integration.get("summary", integration),
    }


def main() -> None:
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    body = "window.WC2026_MODEL_ANALYTICS = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + ";\n"
    OUTPUT.write_text(body, encoding="utf-8")
    print(f"Exportado: {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
