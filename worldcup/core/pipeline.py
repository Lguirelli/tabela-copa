
from worldcup.core.etl import run_etl
from worldcup.core.model import predict_match
import json

def run():
    matches = run_etl()

    preds = []
    for m in matches:
        preds.append(predict_match(m))

    with open("data/predictions.json","w") as f:
        json.dump(preds,f,indent=2)

    print("PIPELINE OK:", len(preds))

if __name__ == "__main__":
    run()
