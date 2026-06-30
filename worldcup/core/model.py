
def predict_match(match):
    a = match["team1"]
    b = match["team2"]

    base = {"A":70,"B":60,"C":65,"D":55}

    pa = base.get(a,60) / (base.get(a,60)+base.get(b,60))
    return {
        "match_id": match["match_id"],
        "team1": a,
        "team2": b,
        "p_team1": round(pa,3),
        "p_team2": round(1-pa,3)
    }
