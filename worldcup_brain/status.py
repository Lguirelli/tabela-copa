from __future__ import annotations

from typing import Any

from .config import TemporalConfig
from .io import atomic_write_json, read_csv, read_json, utc_now


def build(config: TemporalConfig) -> dict[str, Any]:
    validation = read_json(config.output("reports", "temporal_validation_report.json"), {}) or {}
    learning = read_json(config.output("reports", "worldcup_learning_report.json"), {}) or {}
    audit = read_json(config.output("reports", "worldcup_temporal_repository_audit.json"), {}) or {}
    queue = read_json(config.output("data", "temporal", "missing_information_queue.json"), {}) or {}
    enrichment = read_json(config.output("logs", "temporal_enrichment_log.json"), {}) or {}
    predictions = read_csv(config.output("predictions", "pre_match", "index.csv"), required=False)
    learned = read_csv(config.output("learning", "game_analysis", "index.csv"), required=False)
    versions = list(config.output("models", "versions").glob("*.json"))
    semantic_versions = list(config.output("models", "versions", "semantic").glob("*.json"))
    comparison = learning.get("pre_worldcup_vs_progressive_learning", {})
    accepted_features = learning.get("important_variables", [])
    lineups = read_csv(config.path("lineups"), required=False)
    player_stats = read_csv(config.path("player_match_stats"), required=False)
    availability = read_csv(config.path("player_availability"), required=False)
    officials = read_csv(config.path("match_officials"), required=False)
    status = "READY_WITH_LIMITATIONS" if validation.get("status") == "VALID" else "INVALID"
    payload = {
        "generated_at": utc_now(),
        "project_status": status,
        "competition_id": config.get("competition_id"),
        "architecture": "event-driven walk-forward temporal reconstruction",
        "implemented": [
            "pre-World Cup team, player and context snapshot",
            "per-record available_at knowledge control",
            "pre-match prediction files for every match",
            "post-match error learning for every match",
            "causal-association analysis and result significance classification",
            "statistical feature discovery without synthetic variables",
            "daily and semantic model versions",
            "group qualification and knockout Monte Carlo simulations",
            "timestamp-safe missing-information collection",
            "three dedicated GitHub Actions workflows",
            "complete post-match ESPN coverage for events, team statistics, player statistics, observed lineups and main referees",
        ],
        "execution_summary": {
            "predictions": len(predictions),
            "post_match_learning_analyses": len(learned),
            "daily_model_versions": len(versions),
            "semantic_model_versions": len(semantic_versions),
            "knowledge_ledger_records": validation.get("summary", {}).get("knowledge_records", 0),
            "accepted_temporal_features": len(accepted_features),
            "temporal_validation_status": validation.get("status", "NOT_RUN"),
            "observed_lineup_rows": len(lineups),
            "player_match_stat_rows": len(player_stats),
            "player_availability_rows": len(availability),
            "match_official_rows": len(officials),
        },
        "learning_comparison": comparison,
        "temporal_guarantees": validation.get("checks", {}),
        "data_limitations": [
            "FIFA ranking and recent pre-Cup match form lack archived timestamps in the supplied repository.",
            "Pre-Cup injuries, physical condition and recent player minutes remain NA without archived sources.",
            "Observed lineups and player match statistics were collected after the tournament and are not backdated into historical pre-match snapshots.",
            "Player minutes, xG, xA, ratings and historical availability remain NA because the supplied source does not contain them.",
            "Causal outputs describe observed associations and decisive events, not experimental causal proof.",
        ],
        "missing_information": queue.get("summary", {}),
        "latest_enrichment": enrichment.get("summary", {}),
        "audit_risks": audit.get("risk_summary", {}),
        "final_report": "reports/worldcup_learning_report.json",
        "validation_report": "reports/temporal_validation_report.json",
        "audit_report": "reports/worldcup_temporal_repository_audit.json",
        "next_steps": [
            "Add archived pre-Cup rankings, results, injury reports and player-minute datasets with published_at timestamps.",
            "Add archived pre-match lineup and availability publications with trustworthy timestamps to resolve historical pre-match gaps.",
            "Add a source for player minutes, xG, xA or ratings without replacing the observed ESPN records.",
            "Evaluate the learned feature set on another tournament before generalizing causal interpretations.",
        ],
    }
    atomic_write_json(payload, config.output("reports", "worldcup_temporal_system_status.json"))
    existing_path = config.output("reports", "final_system_status.json")
    existing = read_json(existing_path, {}) or {}
    existing["temporal_worldcup_brain"] = payload
    existing["generated_at"] = payload["generated_at"]
    atomic_write_json(existing, existing_path)
    return payload
