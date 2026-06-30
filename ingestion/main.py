
from ingestion.cache_store import load_state, save_state, is_new_or_updated, mark_processed
import json

def load_data():
    with open("data/processed/matches_enriched.json", "r") as f:
        return json.load(f)

def run_pipeline():
    data = load_data()
    state = load_state()

    updated = []

    for match in data:
        if is_new_or_updated(match, state):
            updated.append(match)
            mark_processed(match, state)

    save_state(state)
    print("Incremental ETL updated:", len(updated))
    return updated


if __name__ == '__main__':
    run_pipeline()
