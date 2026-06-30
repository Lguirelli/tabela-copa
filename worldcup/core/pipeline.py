
from worldcup.core.etl import run_etl
from worldcup.core.model import predict_match
import json

def run():
    matches = run_etl()
    preds = [predict_match(m) for m in matches]

    with open("data/predictions.json","w") as f:
        json.dump(preds,f,indent=2)

    print("OK:", len(preds))

if __name__ == "__main__":
    run()
