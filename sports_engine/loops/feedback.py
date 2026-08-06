from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..config import CompetitionConfig, ROOT
from ..io import find_column, read_table, safe_float, write_json_copies
from ..lineage import metadata


def _outcome(g1: int, g2: int) -> str:
    return "team1" if g1 > g2 else "team2" if g2 > g1 else "draw"


def run(config: CompetitionConfig) -> dict[str, Any]:
    predictions_path=config.dataset("predictions"); results_path=config.dataset("results")
    pred=read_table(predictions_path); real=read_table(results_path)
    pid=find_column(pred,"jogo","match_id"); rid=find_column(real,"jogo","match_id")
    if not pid or not rid:
        raise ValueError("Predictions and results require a match identifier")
    merged=pred.merge(real,left_on=pid,right_on=rid,how="inner",suffixes=("_pred","_real"))
    g1r=find_column(merged,"gols1_real"); g2r=find_column(merged,"gols2_real")
    g1p=find_column(merged,"gols1_previsto","gols1_rede_neural"); g2p=find_column(merged,"gols2_previsto","gols2_rede_neural")
    p1=find_column(merged,"prob_vitoria_equipe1"); pd_col=find_column(merged,"prob_empate"); p2=find_column(merged,"prob_vitoria_equipe2")
    feature_cols=[col for col in pred.columns if col.startswith("feature_")]
    feature_scale={col:float(pd.to_numeric(pred[col],errors="coerce").std(ddof=0) or 1.0) for col in feature_cols}
    records=[]; briers=[]; exact=[]; outcome_correct=[]; goal_errors=[]
    for _,row in merged.iterrows():
        try: rg1=int(row[g1r]); rg2=int(row[g2r])
        except (TypeError,ValueError): continue
        pg1=int(round(float(row[g1p]))) if g1p and safe_float(row[g1p]) is not None else None
        pg2=int(round(float(row[g2p]))) if g2p and safe_float(row[g2p]) is not None else None
        actual=_outcome(rg1,rg2); predicted=_outcome(pg1,pg2) if pg1 is not None and pg2 is not None else "NA"
        probs={"team1":safe_float(row[p1]) if p1 else None,"draw":safe_float(row[pd_col]) if pd_col else None,"team2":safe_float(row[p2]) if p2 else None}
        brier=None
        if all(value is not None for value in probs.values()):
            brier=sum((float(probs[key])-(1.0 if key==actual else 0.0))**2 for key in probs)/3.0
            briers.append(brier)
        candidate="NA"; candidate_value=None
        scored=[]
        for col in feature_cols:
            value=safe_float(row.get(col))
            if value is not None:
                scored.append((abs(value)/feature_scale.get(col,1.0),col,value))
        if scored:
            _,candidate,candidate_value=max(scored)
        exact_match=pg1==rg1 and pg2==rg2 if pg1 is not None else False
        outcome_match=predicted==actual
        if pg1 is not None:
            goal_error=(abs(pg1-rg1)+abs(pg2-rg2))/2.0; goal_errors.append(goal_error)
        else: goal_error=None
        exact.append(exact_match); outcome_correct.append(outcome_match)
        records.append({
            "match_id":int(row[pid]),"predicted_score":f"{pg1}-{pg2}" if pg1 is not None else "NA","actual_score":f"{rg1}-{rg2}",
            "predicted_outcome":predicted,"actual_outcome":actual,"outcome_correct":outcome_match,"exact_score":exact_match,
            "mean_absolute_goal_error":round(goal_error,6) if goal_error is not None else None,"brier_score":round(brier,6) if brier is not None else None,
            "candidate_driver":candidate,"candidate_driver_value":candidate_value,
            "driver_method":"largest standardized feature signal; diagnostic only, not causal attribution",
        })
    payload=metadata("05_prediction_feedback",config.competition_id,[predictions_path,results_path],ROOT,{
        "summary":{
            "matches_compared":len(records),"outcome_accuracy":round(float(np.mean(outcome_correct)),6) if outcome_correct else None,
            "exact_score_accuracy":round(float(np.mean(exact)),6) if exact else None,"mean_absolute_goal_error":round(float(np.mean(goal_errors)),6) if goal_errors else None,
            "multiclass_brier_score":round(float(np.mean(briers)),6) if briers else None,
        },"errors":records,
    })
    write_json_copies(
        payload,
        config.scoped_path("models", "error_learning.json"),
        ROOT / "models" / "error_learning.json",
    )
    return payload
