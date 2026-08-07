from __future__ import annotations

from typing import Any

import pandas as pd

from ..analytics import build_team_match_frame, correlation, evidence_confidence
from ..config import CompetitionConfig, ROOT
from ..io import find_column, read_table, write_json_copies
from ..lineage import metadata


FACTOR_ALIASES = {
    "first_goal": ["first_goal"],
    "possession": ["stat_possessionPct", "posse_pct"],
    "shots": ["stat_totalShots", "finalizacoes"],
    "shots_on_target": ["stat_shotsOnTarget", "finalizacoes_alvo"],
    "yellow_cards": ["stat_yellowCards", "cartoes_amarelos"],
    "red_cards": ["stat_redCards", "cartoes_vermelhos"],
    "corners": ["stat_wonCorners", "escanteios"],
    "pass_accuracy": ["stat_passPct"],
    "tackles": ["stat_totalTackles"],
    "interceptions": ["stat_interceptions", "interceptacoes"],
    "xg": ["xg_pro"],
}


def run(config: CompetitionConfig) -> dict[str, Any]:
    results_path=config.dataset("results"); stats_path=config.dataset("team_match_stats"); events_path=config.dataset("events"); performance_path=config.dataset("performance")
    results=read_table(results_path); stats=read_table(stats_path,required=False); events=read_table(events_path,required=False); performance=read_table(performance_path,required=False)
    frame=build_team_match_frame(results,stats,events,performance)
    patterns=[]; unavailable=[]
    minimum=int(config.engine.get("minimum_samples_for_pattern",30))
    for factor, aliases in FACTOR_ALIASES.items():
        column=next((col for col in aliases if col in frame.columns),None)
        if not column:
            unavailable.append({"factor":factor,"reason":"field not available in configured datasets"}); continue
        corr,n=correlation(frame[column],frame["points"])
        if corr is None or n < minimum:
            unavailable.append({"factor":factor,"reason":f"insufficient valid samples ({n} < {minimum})"}); continue
        values=pd.to_numeric(frame[column],errors="coerce")
        winners=values[frame["outcome"]==1].dropna(); others=values[frame["outcome"]!=1].dropna()
        effect=None
        pooled=values.std(ddof=0)
        if len(winners) and len(others) and pooled and pooled>0:
            effect=float((winners.mean()-others.mean())/pooled)
        patterns.append({
            "factor":factor,
            "source_column":column,
            "impact":round(corr,6),
            "standardized_winner_difference":round(effect,6) if effect is not None else None,
            "confidence":evidence_confidence(corr,n),
            "sample_size":n,
            "target":"match_points",
            "method":"pearson_correlation_and_standardized_group_difference",
            "interpretation":"association, not causal attribution",
        })
    patterns.sort(key=lambda item:abs(item["impact"]),reverse=True)
    payload=metadata("04_pattern_discovery",config.competition_id,[results_path,stats_path,events_path,performance_path],ROOT,{
        "summary":{"team_match_rows":len(frame),"patterns_found":len(patterns),"unavailable_factors":len(unavailable)},
        "patterns":patterns,"unavailable":unavailable,
    })
    write_json_copies(
        payload,
        config.scoped_path("models", "patterns.json"),
        ROOT / "models" / "patterns.json",
    )
    return payload
