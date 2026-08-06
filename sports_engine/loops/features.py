from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..analytics import correlation, evidence_confidence
from ..config import CompetitionConfig, ROOT
from ..io import find_column, read_json, read_table, write_json_copies
from ..lineage import metadata


CANDIDATE_GROUPS={
 "travel":["feature_travel_diff"],"rest":["feature_rest_diff"],"average_age":["feature_average_age_diff"],
 "experience":["feature_experience_diff"],"style":["feature_possession_diff","feature_pressing_diff","feature_intensity_diff"],
 "refereeing":["feature_referee_rigor_diff","feature_referee_penalty_diff"],"calendar":["feature_schedule_strength_diff"],
 "physical_load":["feature_fatigue_diff","feature_rest_diff"],"league_quality":["feature_league_diff"],
 "player_quality":["feature_player_quality_diff"],"recent_form":["feature_momentum_diff","feature_offensive_form_diff","feature_defensive_form_diff"],
}


def run(config: CompetitionConfig) -> dict[str, Any]:
    predictions_path=config.dataset("predictions"); results_path=config.dataset("results")
    pred=read_table(predictions_path); real=read_table(results_path)
    pid=find_column(pred,"jogo","match_id"); rid=find_column(real,"jogo","match_id")
    g1=find_column(real,"gols1_real"); g2=find_column(real,"gols2_real")
    if not all([pid,rid,g1,g2]): raise ValueError("Feature discovery requires match IDs and real goals")
    target=real[[rid,g1,g2]].copy(); target["target_outcome"]=np.sign(pd.to_numeric(target[g1],errors="coerce")-pd.to_numeric(target[g2],errors="coerce"))
    frame=pred.merge(target[[rid,"target_outcome"]],left_on=pid,right_on=rid,how="inner")
    threshold=float(config.engine.get("feature_correlation_threshold",0.08)); minimum=int(config.engine.get("minimum_matches_for_training",30))
    accepted=[]; evaluated=[]; unavailable=[]
    for concept,aliases in CANDIDATE_GROUPS.items():
        available=[col for col in aliases if col in frame.columns]
        if not available:
            unavailable.append({"concept":concept,"reason":"no observed or derived column is available"}); continue
        for col in available:
            if "simulad" in col.lower():
                evaluated.append({"feature":col,"concept":concept,"status":"REJECTED","reason":"synthetic fields are excluded"}); continue
            corr,n=correlation(frame[col],frame["target_outcome"])
            if corr is None or n<minimum:
                evaluated.append({"feature":col,"concept":concept,"status":"REJECTED","reason":f"insufficient samples ({n})"}); continue
            valid=frame[[col,"target_outcome"]].apply(pd.to_numeric,errors="coerce").dropna()
            midpoint=max(1,len(valid)//2); c1,_=correlation(valid.iloc[:midpoint][col],valid.iloc[:midpoint]["target_outcome"]); c2,_=correlation(valid.iloc[midpoint:][col],valid.iloc[midpoint:]["target_outcome"])
            stable=c1 is not None and c2 is not None and np.sign(c1)==np.sign(c2)
            status="ACCEPTED" if abs(corr)>=threshold and stable else "REJECTED"
            evidence={"feature":col,"concept":concept,"status":status,"correlation":round(corr,6),"sample_size":n,"stable_direction":bool(stable),"first_half_correlation":round(c1,6) if c1 is not None else None,"second_half_correlation":round(c2,6) if c2 is not None else None,"confidence":evidence_confidence(corr,n),"provenance":"derived from configured prediction features and real results","data_type":"derived"}
            evaluated.append(evidence)
            if status=="ACCEPTED": accepted.append(evidence)
    registry={"generated_at":metadata("06_feature_discovery",config.competition_id,[predictions_path,results_path],ROOT)["generated_at"],"competition_id":config.competition_id,"acceptance_rule":{"minimum_samples":minimum,"absolute_correlation_threshold":threshold,"requires_stable_direction_across_chronological_halves":True},"features":accepted,"evaluated_candidates":evaluated,"unavailable_concepts":unavailable}
    existing = read_json(ROOT / "models" / "features_registry.json", {}) or {}
    if "temporal_worldcup_2026" in existing:
        registry["temporal_worldcup_2026"] = existing["temporal_worldcup_2026"]
    write_json_copies(
        registry,
        config.scoped_path("models", "features_registry.json"),
        ROOT / "models" / "features_registry.json",
    )
    return registry
