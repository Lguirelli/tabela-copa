from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import TemporalConfig
from .io import atomic_write_json, read_json, utc_now


def _correlation(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def discover_features(config: TemporalConfig, evaluated_rows: list[dict[str, Any]]) -> dict[str, Any]:
    minimum = int(config.get("minimum_matches_for_feature_discovery", 24))
    threshold = float(config.get("feature_correlation_threshold", 0.12))
    p_threshold = float(config.get("feature_permutation_pvalue", 0.05))
    if len(evaluated_rows) < minimum:
        result = {"status": "INSUFFICIENT_DATA", "samples": len(evaluated_rows), "accepted": [], "evaluated": []}
        atomic_write_json(result, config.output("models", "temporal_feature_discovery.json"))
        return result
    feature_names = sorted({key for row in evaluated_rows for key in row.get("features", {})})
    y = np.array([float(row["actual_goal_diff"]) for row in evaluated_rows], dtype=float)
    rng = np.random.default_rng(int(config.get("random_seed", 2026)))
    evaluated = []
    accepted = []
    for feature in feature_names:
        values = np.array([float(row.get("features", {}).get(feature, 0.0)) for row in evaluated_rows], dtype=float)
        corr = _correlation(values, y)
        permutations = []
        for _ in range(300):
            permutations.append(abs(_correlation(values, rng.permutation(y))))
        p_value = float((sum(value >= abs(corr) for value in permutations) + 1) / (len(permutations) + 1))
        midpoint = len(values) // 2
        first = _correlation(values[:midpoint], y[:midpoint])
        second = _correlation(values[midpoint:], y[midpoint:])
        stable = first == 0 or second == 0 or np.sign(first) == np.sign(second)
        status = "ACCEPTED" if abs(corr) >= threshold and p_value <= p_threshold and stable else "REJECTED"
        item = {
            "feature": feature,
            "status": status,
            "correlation_with_goal_difference": round(corr, 6),
            "permutation_p_value": round(p_value, 6),
            "chronological_first_half_correlation": round(first, 6),
            "chronological_second_half_correlation": round(second, 6),
            "stable_direction": bool(stable),
            "sample_size": len(values),
            "evidence_rule": f"abs(correlation)>={threshold}, permutation_p<={p_threshold}, stable chronological direction",
            "temporal_provenance": "feature values were frozen at each pre-match cutoff",
        }
        evaluated.append(item)
        if status == "ACCEPTED":
            accepted.append(item)
    payload = {
        "generated_at": utc_now(),
        "competition_id": config.get("competition_id"),
        "status": "COMPLETED",
        "samples": len(evaluated_rows),
        "accepted": accepted,
        "evaluated": evaluated,
    }
    atomic_write_json(payload, config.output("models", "temporal_feature_discovery.json"))

    registry_path = config.output("models", "features_registry.json")
    registry = read_json(registry_path, {}) or {}
    registry["temporal_worldcup_2026"] = {
        "generated_at": payload["generated_at"],
        "acceptance_rule": {"minimum_samples": minimum, "correlation_threshold": threshold, "permutation_p_value": p_threshold},
        "features": accepted,
        "evaluated_candidates": evaluated,
    }
    atomic_write_json(registry, registry_path)
    return payload
