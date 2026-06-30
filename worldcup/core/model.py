
def predict_match(m):
    base = {"A":70,"B":60,"C":65,"D":55}
    a = base.get(m["team1"],60)
    b = base.get(m["team2"],60)

    pa = a/(a+b)
    return {
        "match_id": m["match_id"],
        "team1": m["team1"],
        "team2": m["team2"],
        "p_team1": round(pa,3),
        "p_team2": round(1-pa,3)
    }
