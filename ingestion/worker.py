import time
from fallback import FallbackEngine
from config import API_SOURCES
from normalizer import normalize_match
from storage import save_raw, save_silver

engine = FallbackEngine()

def process_match(match):
    attempts = 0
    result = None

    while attempts < 10:
        result = engine.fetch(API_SOURCES["fixtures"], {"match_id": match.get("id")})

        if result["status"] == "success":
            break

        attempts += 1
        time.sleep(5)

    save_raw(result)
    silver = normalize_match(result)

    if silver:
        save_silver(silver)