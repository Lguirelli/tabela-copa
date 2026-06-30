from ingestion.main import run_ingestion
from neural_copa.run_pipeline import run

def main():
    run_ingestion()
    run()

if __name__ == "__main__":
    main()
