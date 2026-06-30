
import time
from ingestion.main import run_pipeline

def stream():
    while True:
        print("Running scheduled ETL cycle...")
        run_pipeline()
        time.sleep(3600)  # hourly

if __name__ == "__main__":
    stream()
