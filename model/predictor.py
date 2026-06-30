
import json
import random

def load_warehouse():
    path = "data/processed/matches_enriched.json"
    with open(path, "r") as f:
        return json.load(f)

def compute_probability(match):
    base = 0.5

    stats = match.get("team_stats", {})

    signal = 0.0
    try:
        for t in stats:
            if isinstance(stats[t], dict):
                signal += float(stats[t].get("xG", 0) or 0)
    except:
        pass

    boost = min(signal / 5.0, 0.15)

    p1 = base + boost - 0.05
    p2 = base - boost + 0.05

    draw = max(0.10, 1 - (p1 + p2))

    return {
        "match_id": match.get("match_id"),
        "team_1_win": round(p1, 3),
        "team_2_win": round(p2, 3),
        "draw": round(draw, 3)
    }

def run_predictions():
    data = load_warehouse()
    return [compute_probability(m) for m in data]
