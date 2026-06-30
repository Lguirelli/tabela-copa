
from worldcup.ingestion.main import run_pipeline
from worldcup.model.real_probabilistic_model import RealModel
import pandas as pd

def run():
    print("RUNNING FULL ARCH PIPELINE")

    # ETL
    data = run_pipeline()

    print("PIPELINE DONE (ETL STEP)")

if __name__ == "__main__":
    run()
