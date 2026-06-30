
import json
import os

CACHE_PATH = "data/state/ingestion_state.json"

def load_state():
    if not os.path.exists(CACHE_PATH):
        return {"processed_matches": {}}
    with open(CACHE_PATH, "r") as f:
        return json.load(f)

def save_state(state):
    with open(CACHE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def is_new_or_updated(match, state):
    mid = match.get("match_id")
    if not mid:
        return False

    prev = state.get("processed_matches", {}).get(mid)
    if not prev:
        return True

    return prev.get("hash") != str(match.get("result")) + str(match.get("xG", ""))

def mark_processed(match, state):
    mid = match.get("match_id")
    if not mid:
        return

    state.setdefault("processed_matches", {})[mid] = {
        "hash": str(match.get("result")) + str(match.get("xG", "")),
        "updated_at": None
    }
