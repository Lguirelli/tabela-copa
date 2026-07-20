from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from ..config import CompetitionConfig, ROOT
from ..io import find_column, read_json, read_table, safe_float, write_json_copies, write_table_copies
from ..lineage import metadata
from ..modeling import model_predict


def run(config: CompetitionConfig) -> dict[str, Any]:
    predictions_path=config.dataset("predictions")
    pred=read_table(predictions_path)
    latest_path=ROOT/"models"/"model_versions"/config.competition_id/"latest.json"
    latest=read_json(latest_path,{})
    use_recalibrated=latest.get("status")=="PROMOTED" and all(col in pred.columns for col in latest.get("features",[]))
    if use_recalibrated:
        lambda1,lambda2=model_predict(pred,latest)
    else:
        x1=find_column(pred,"xg1_modelo","gols1_neural_float"); x2=find_column(pred,"xg2_modelo","gols2_neural_float")
        if not x1 or not x2: raise ValueError("Simulation requires expected goals or a promoted recalibration model")
        lambda1=pd.to_numeric(pred[x1],errors="coerce").fillna(1.2).clip(lower=0.05).to_numpy()
        lambda2=pd.to_numeric(pred[x2],errors="coerce").fillna(1.0).clip(lower=0.05).to_numpy()
    iterations=int(config.engine.get("monte_carlo_iterations",12000)); seed=int(config.engine.get("random_seed",2026))
    id_col=find_column(pred,"jogo","match_id"); phase_col=find_column(pred,"fase","phase"); team1=find_column(pred,"equipe1","team1"); team2=find_column(pred,"equipe2","team2")
    real_col=find_column(pred,"possui_real")
    summaries=[]; distributions=[]
    knockout={str(item).lower() for item in config.data.get("knockout_phases",[])}
    for index,row in pred.iterrows():
        match_id=int(row[id_col]) if id_col else index+1; rng=np.random.default_rng(seed+match_id)
        g1=rng.poisson(float(lambda1[index]),iterations); g2=rng.poisson(float(lambda2[index]),iterations)
        p1=float(np.mean(g1>g2)); pdra=float(np.mean(g1==g2)); p2=float(np.mean(g2>g1))
        scores=Counter(zip(g1.tolist(),g2.tolist())); top=[{"score":f"{a}-{b}","probability":round(count/iterations,6)} for (a,b),count in scores.most_common(10)]
        phase=str(row.get(phase_col,"")) if phase_col else ""
        is_knockout=phase.lower() in knockout or any(token in phase.lower() for token in ["final","oitavas","quartas","semifinal","32 avos"])
        probability_extra_time = pdra if is_knockout else 0.0
        probability_penalties = 0.0
        probability_team1_extra_time = 0.0
        probability_team2_extra_time = 0.0
        if is_knockout:
            tied_90 = g1 == g2
            extra1 = rng.poisson(float(lambda1[index]) / 3.0, iterations)
            extra2 = rng.poisson(float(lambda2[index]) / 3.0, iterations)
            probability_team1_extra_time = float(np.mean(tied_90 & (extra1 > extra2)))
            probability_team2_extra_time = float(np.mean(tied_90 & (extra2 > extra1)))
            probability_penalties = float(np.mean(tied_90 & (extra1 == extra2)))
        penalty_team1=safe_float(row.get("prob_penaltis_equipe1")) if "prob_penaltis_equipe1" in row.index else None
        summaries.append({
            "match_id":match_id,"competition_id":config.competition_id,"team1":row.get(team1,"NA") if team1 else "NA","team2":row.get(team2,"NA") if team2 else "NA","phase":phase,
            "expected_goals_team1":round(float(lambda1[index]),6),"expected_goals_team2":round(float(lambda2[index]),6),
            "probability_team1_win":round(p1,6),"probability_draw":round(pdra,6),"probability_team2_win":round(p2,6),
            "probability_extra_time":round(probability_extra_time,6),
            "probability_team1_win_in_extra_time":round(probability_team1_extra_time,6),
            "probability_team2_win_in_extra_time":round(probability_team2_extra_time,6),
            "probability_penalty_decision":round(probability_penalties,6),
            "probability_team1_win_penalties":penalty_team1,
            "mean_total_goals":round(float(np.mean(g1+g2)),6),"iterations":iterations,"model_source":"promoted_recalibration" if use_recalibrated else "configured_expected_goals",
            "simulation_role":"retrospective_validation" if str(row.get(real_col,"")).lower() in {"sim","yes","true"} else "forecast",
        })
        distributions.append({"match_id":match_id,"top_scorelines":top})
    out_dir=config.scoped_path("models", "simulations")
    alias_dir=ROOT/"models"/"simulations"
    write_table_copies(pd.DataFrame(summaries),out_dir/"latest.csv",alias_dir/"latest.csv")
    payload=metadata("07_simulation_update",config.competition_id,[predictions_path]+([latest_path] if latest_path.exists() else []),ROOT,{
        "summary":{"matches_simulated":len(summaries),"iterations_per_match":iterations,"recalibrated_model_used":use_recalibrated},
        "distributions":distributions,
        "summary_csv":(out_dir/"latest.csv").relative_to(ROOT).as_posix(),
        "compatibility_summary_csv":"models/simulations/latest.csv",
    })
    write_json_copies(payload,out_dir/"latest.json",alias_dir/"latest.json")
    return payload
