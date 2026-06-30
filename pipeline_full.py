
import pandas as pd
from model.real_probabilistic_model import RealModel
from versioning.history_engine import save_snapshot

def run():
    df = pd.read_csv("data/database/team_strengths.csv")
    model = RealModel(df)

    matches = pd.read_csv("data/matches.csv")

    preds = []
    for _,r in matches.iterrows():
        preds.append(model.predict(r["team1"], r["team2"]))

    save_snapshot("data/history/predictions", preds)
    return preds
