
from ingestion.main import run_pipeline

def execute():
    print("Starting ETL + validation + enrichment pipeline")
    run_pipeline()
    print("Pipeline completed")

if __name__ == "__main__":
    execute()
