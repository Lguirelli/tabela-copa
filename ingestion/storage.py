import json, os
from datetime import datetime

def save_raw(data):
    os.makedirs("data/raw", exist_ok=True)
    path = f"data/raw/raw_{datetime.now().timestamp()}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path

def save_silver(data):
    os.makedirs("data/silver", exist_ok=True)
    path = f"data/silver/silver_{datetime.now().timestamp()}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path