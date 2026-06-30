import time
import requests
from config import MAX_RETRIES, TIMEOUT, BACKOFF
from logger import log

class FallbackEngine:

    def fetch(self, sources, params=None):
        last_error = None

        for source in sources:
            for attempt in range(MAX_RETRIES):
                try:
                    r = requests.get(source["url"], params=params, timeout=TIMEOUT)
                    if r.status_code == 200:
                        return {"data": r.json(), "source": source["name"], "status": "success"}
                except Exception as e:
                    last_error = str(e)
                    time.sleep(BACKOFF ** attempt)

        return {"data": None, "status": "failed", "error": last_error}