API_SOURCES = {
    "fixtures": [
        {"name": "api_football", "url": "https://api-football-v1.p.rapidapi.com/v3/fixtures"},
        {"name": "balldontlie", "url": "https://api.balldontlie.io/v1/fixtures"},
        {"name": "isports", "url": "https://api.isportsapi.com/football/fixtures"}
    ]
}

MAX_RETRIES = 3
TIMEOUT = 10
BACKOFF = 2