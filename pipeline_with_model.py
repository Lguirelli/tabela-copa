
from ingestion.main import run_pipeline
from model.predictor import run_predictions
import json

def execute_full():
    print("Running ETL...")
    run_pipeline()

    print("Running predictions...")
    preds = run_predictions()

    with open("data/processed/predictions.json", "w") as f:
        json.dump(preds, f, indent=2)

    print("Done.")

if __name__ == "__main__":
    execute_full()
