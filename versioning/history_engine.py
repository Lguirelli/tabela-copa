
import json, hashlib
from datetime import datetime

def hash_data(data):
    return hashlib.md5(str(data).encode()).hexdigest()

def save_snapshot(path, data):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    h = hash_data(data)
    out = f"{path}/snapshot_{ts}_{h}.json"
    with open(out,"w") as f:
        json.dump({"timestamp":ts,"hash":h,"data":data},f,indent=2)
    return out
