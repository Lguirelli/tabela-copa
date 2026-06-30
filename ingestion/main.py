from extractor import extract_fixtures
from worker import process_match
from normalizer import normalize_match
from storage import save_raw, save_silver

def run():
    result = extract_fixtures()
    save_raw(result)

    matches = normalize_match(result)

    for m in matches:
        process_match(m)

if __name__ == "__main__":
    run()