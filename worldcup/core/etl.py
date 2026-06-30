
import json

def run_etl():
    with open("data/matches.json","r") as f:
        return json.load(f)
