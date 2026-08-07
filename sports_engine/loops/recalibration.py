from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import CompetitionConfig, ROOT
from ..io import file_sha256, find_column, read_json, read_table, utc_now, write_json, write_json_copies
from ..lineage import metadata
from ..modeling import design_matrix, fit_ridge, predict_ridge


def run(config: CompetitionConfig) -> dict[str, Any]:
    predictions_path=config.dataset("predictions"); results_path=config.dataset("results")
    pred=read_table(predictions_path); real=read_table(results_path)
    pid=find_column(pred,"jogo","match_id"); rid=find_column(real,"jogo","match_id"); g1=find_column(real,"gols1_real"); g2=find_column(real,"gols2_real")
    if not all([pid,rid,g1,g2]): raise ValueError("Recalibration requires match IDs and real goals")
    frame=pred.merge(real[[rid,g1,g2]],left_on=pid,right_on=rid,how="inner").sort_values(pid).reset_index(drop=True)
    minimum=int(config.engine.get("minimum_matches_for_training",30))
    registry_path = config.scoped_path("models", "features_registry.json")
    registry_alias = ROOT / "models" / "features_registry.json"
    registry=read_json(registry_path, read_json(registry_alias, {}))
    features=[item["feature"] for item in registry.get("features",[]) if item.get("feature") in frame.columns]
    if not features:
        features=[col for col in frame.columns if col.startswith("feature_") and "simulad" not in col.lower()]
    status="SKIPPED"; reason=None; model=None
    if len(frame)<minimum or not features:
        reason=f"Need at least {minimum} matches and one evidence-backed feature; found {len(frame)} matches and {len(features)} features."
    else:
        split=max(int(len(frame)*0.8),minimum); split=min(split,len(frame)-1)
        train=frame.iloc[:split]; test=frame.iloc[split:]
        X_train,means,scales=design_matrix(train,features); X_test,_,_=design_matrix(test,features,means,scales)
        y_diff=(pd.to_numeric(train[g1])-pd.to_numeric(train[g2])).to_numpy(dtype=float); y_total=(pd.to_numeric(train[g1])+pd.to_numeric(train[g2])).to_numpy(dtype=float)
        c_diff=fit_ridge(X_train,y_diff,alpha=2.0); c_total=fit_ridge(X_train,y_total,alpha=2.0)
        actual_diff=(pd.to_numeric(test[g1])-pd.to_numeric(test[g2])).to_numpy(dtype=float); actual_total=(pd.to_numeric(test[g1])+pd.to_numeric(test[g2])).to_numpy(dtype=float)
        pred_diff=predict_ridge(X_test,c_diff); pred_total=np.maximum(predict_ridge(X_test,c_total),0)
        xg1=find_column(test,"xg1_modelo"); xg2=find_column(test,"xg2_modelo")
        if xg1 and xg2:
            base1=pd.to_numeric(test[xg1],errors="coerce").fillna(0).to_numpy(); base2=pd.to_numeric(test[xg2],errors="coerce").fillna(0).to_numpy()
            base_diff=base1-base2; base_total=base1+base2
        else:
            base_diff=np.zeros(len(test)); base_total=np.repeat(float(np.mean(y_total)),len(test))
        metrics={
            "baseline_goal_difference_mae":float(np.mean(np.abs(base_diff-actual_diff))),"recalibrated_goal_difference_mae":float(np.mean(np.abs(pred_diff-actual_diff))),
            "baseline_total_goals_mae":float(np.mean(np.abs(base_total-actual_total))),"recalibrated_total_goals_mae":float(np.mean(np.abs(pred_total-actual_total))),
        }
        metrics["baseline_average_mae"]=(metrics["baseline_goal_difference_mae"]+metrics["baseline_total_goals_mae"])/2
        metrics["recalibrated_average_mae"]=(metrics["recalibrated_goal_difference_mae"]+metrics["recalibrated_total_goals_mae"])/2
        promoted=metrics["recalibrated_average_mae"]<metrics["baseline_average_mae"]
        signature_payload = {
            "competition_id": config.competition_id,
            "predictions_sha256": file_sha256(predictions_path),
            "results_sha256": file_sha256(results_path),
            "features": features,
            "feature_evidence": [
                {"feature": item.get("feature"), "correlation": item.get("correlation"), "sample_size": item.get("sample_size")}
                for item in registry.get("features", []) if item.get("feature") in features
            ],
        }
        signature = hashlib.sha256(json.dumps(signature_payload, sort_keys=True).encode("utf-8")).hexdigest()
        version = f"{config.competition_id}_{signature[:16]}"
        versions=ROOT/"models"/"model_versions"/config.competition_id
        versions.mkdir(parents=True,exist_ok=True)
        version_path=versions/f"{version}.json"
        previous = read_json(version_path, {})
        model={"version":version,"trained_at":previous.get("trained_at",utc_now()),"input_signature":signature,"competition_id":config.competition_id,"status":"PROMOTED" if promoted else "CANDIDATE_REJECTED","training_matches":len(train),"validation_matches":len(test),"features":features,"feature_means":means,"feature_scales":scales,"goal_difference_coefficients":c_diff.tolist(),"total_goals_coefficients":c_total.tolist(),"metrics":{key:round(value,6) for key,value in metrics.items()},"promotion_rule":"lower chronological holdout average MAE","data_lineage":previous.get("data_lineage",metadata("08_model_recalibration",config.competition_id,[predictions_path,results_path,registry_path],ROOT))}
        status=model["status"]
        write_json(model,version_path)
        if promoted: write_json(model,versions/"latest.json")
    report=metadata("08_model_recalibration",config.competition_id,[predictions_path,results_path],ROOT,{"status":status,"reason":reason,"model":model})
    write_json_copies(
        report,
        config.scoped_path("reports", "model_recalibration_report.json"),
        ROOT / "reports" / "model_recalibration_report.json",
    )
    return report
