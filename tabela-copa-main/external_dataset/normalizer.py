def normalize_match(result):
    if not result or not result.get("data"):
        return []

    data = result["data"]
    out = []

    try:
        matches = data.get("response", data)

        for m in matches:
            out.append({
                "match_id": m.get("id"),
                "home_team": m.get("home", {}).get("name"),
                "away_team": m.get("away", {}).get("name"),
                "score": m.get("score"),
                "stage": m.get("stage"),
                "date": m.get("date"),
                "source": result.get("source")
            })
    except:
        pass

    return out