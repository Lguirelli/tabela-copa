from __future__ import annotations

from typing import Any

from .config import CompetitionConfig, ROOT
from .io import read_json, read_table, utc_now, write_json_copies
from .loops import completeness, enrichment, feedback, features, patterns, recalibration, simulation, validation


def run_all(config: CompetitionConfig) -> dict[str, Any]:
    steps: list[dict[str, Any]]=[]
    runners=[
        ("01_data_completeness",completeness.run),
        ("02_data_enrichment",enrichment.run),
        ("01_data_completeness_after_enrichment",completeness.run),
        ("03_data_validation",validation.run),
        ("04_pattern_discovery",patterns.run),
        ("05_prediction_feedback",feedback.run),
        ("06_feature_discovery",features.run),
        ("08_model_recalibration",recalibration.run),
        ("07_simulation_update",simulation.run),
    ]
    overall="READY"
    limitations=[]
    for name,runner in runners:
        try:
            result=runner(config); steps.append({"step":name,"status":"SUCCESS","summary":result.get("summary",result.get("status","completed"))})
            if name=="03_data_validation" and result.get("status") in {"INVALID", "CONFLICTING_DATA"}:
                overall="BLOCKED"
        except Exception as exc:
            steps.append({"step":name,"status":"FAILED","error":f"{type(exc).__name__}: {exc}"}); overall="PARTIAL"
    queue_path = config.scoped_path("data", "queues", "missing_data.json")
    queue = read_json(queue_path, {})
    if queue:
        open_items=[item for item in queue.get("items",[]) if item.get("status")=="OPEN"]
        if open_items:
            limitations.append(f"{len(open_items)} aggregated missing-data requirements remain open; unavailable values stay NA.")
            if overall == "READY":
                overall = "READY_WITH_LIMITATIONS"
    quarantined_path = ROOT / "data" / "conflicts" / "unmapped_espn_team_match_stats.csv"
    if quarantined_path.exists():
        quarantined = read_table(quarantined_path, required=False)
        if not quarantined.empty:
            limitations.append(
                f"{len(quarantined)} legacy external statistic rows remain quarantined as CONFLICTING_DATA and are excluded from analysis."
            )

    payload={
        "generated_at":utc_now(),"competition_id":config.competition_id,"project_status":overall,"improvements_realized":[
            "competition-driven configuration","eight executable analytical loops","missing-data queue and enrichment lineage","quality validation",
            "pattern and feature evidence registry", "prediction feedback",
            "Monte Carlo simulation with separate extra-time and penalty states",
            "versioned model recalibration", "competition-isolated artifacts",
            "incremental composite-key enrichment merges", "GitHub Actions registry orchestration",
        ],"steps":steps,"limitations":limitations,"next_steps":[
            "Configure reliable player-minutes and historical availability providers; observed lineups already cover all matches.",
            "Add a new competition block and canonical datasets to reuse the engine without code changes.",
            "Review promoted model versions before using them for high-stakes decisions.",
        ],
    }
    write_json_copies(
        payload,
        config.scoped_path("reports", "final_system_status.json"),
        ROOT / "reports" / "final_system_status.json",
    )
    return payload
