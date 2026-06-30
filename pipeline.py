
import json
import math
from datetime import datetime

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def load_data():
    try:
        with open("data/matches.json","r") as f:
            return json.load(f)
    except:
        return [
            {"match_id":1,"team1":"A","team2":"B"},
            {"match_id":2,"team1":"C","team2":"D"}
        ]

def team_strength(team):
    base = {
        "A": 70, "B": 65, "C": 60, "D": 75
    }
    return base.get(team, 60)

def predict(match):
    a = team_strength(match["team1"])
    b = team_strength(match["team2"])

    score = (a - b) / 10
    p_a = sigmoid(score)
    p_b = 1 - p_a

    return {
        "match_id": match["match_id"],
        "team1": match["team1"],
        "team2": match["team2"],
        "p_team1": round(p_a,3),
        "p_team2": round(p_b,3),
        "draw": round(max(0.05, 1 - (p_a + p_b)),3)
    }

def run():
    matches = load_data()
    preds = [predict(m) for m in matches]

    out = {
        "generated_at": datetime.now().isoformat(),
        "predictions": preds
    }

    with open("data/predictions.json","w") as f:
        json.dump(out,f,indent=2)

    print("Pipeline executed:", len(preds))

if __name__ == "__main__":
    run()
