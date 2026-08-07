from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    identity=np.eye(X.shape[1]); identity[0,0]=0.0
    return np.linalg.pinv(X.T@X+alpha*identity)@X.T@y


def predict_ridge(X: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    return X@coefficients


def design_matrix(frame: pd.DataFrame, features: list[str], means: dict[str,float] | None=None, scales: dict[str,float] | None=None) -> tuple[np.ndarray,dict[str,float],dict[str,float]]:
    numeric=frame[features].apply(pd.to_numeric,errors="coerce").fillna(0.0)
    if means is None: means={col:float(numeric[col].mean()) for col in features}
    if scales is None: scales={col:float(numeric[col].std(ddof=0) or 1.0) for col in features}
    standardized=np.column_stack([(numeric[col].to_numpy()-means[col])/scales[col] for col in features]) if features else np.empty((len(frame),0))
    X=np.column_stack([np.ones(len(frame)),standardized])
    return X,means,scales


def model_predict(frame: pd.DataFrame, model: dict[str,Any]) -> tuple[np.ndarray,np.ndarray]:
    features=model["features"]; X,_,_=design_matrix(frame,features,model["feature_means"],model["feature_scales"])
    diff=predict_ridge(X,np.array(model["goal_difference_coefficients"],dtype=float)); total=predict_ridge(X,np.array(model["total_goals_coefficients"],dtype=float))
    total=np.maximum(total,0.0); g1=np.maximum((total+diff)/2.0,0.05); g2=np.maximum((total-diff)/2.0,0.05)
    return g1,g2
