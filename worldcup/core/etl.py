
import json

def load_matches():
    try:
        with open("data/matches.json") as f:
            return json.load(f)
    except:
        return []

def run_etl():
    return load_matches()
