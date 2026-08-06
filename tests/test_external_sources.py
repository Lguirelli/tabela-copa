from pathlib import Path

import pandas as pd

from sports_engine.sources import _football_data_rows
from worldcup_brain.config import TemporalConfig
from worldcup_brain.preworldcup import _latest_rankings


def test_football_data_parser_keeps_provider_timestamps() -> None:
    rows = _football_data_rows(
        {
            "matches": [{
                "id": 10,
                "utcDate": "2026-06-11T19:00:00Z",
                "lastUpdated": "2026-06-11T21:00:00Z",
                "status": "FINISHED",
                "stage": "GROUP_STAGE",
                "matchday": 1,
                "competition": {"name": "World Cup", "code": "WC"},
                "homeTeam": {"id": 1, "name": "Mexico"},
                "awayTeam": {"id": 2, "name": "South Africa"},
                "score": {"winner": "HOME_TEAM", "fullTime": {"home": 2, "away": 0}},
            }]
        },
        "https://api.example.test",
    )
    assert rows[0]["external_match_id"] == 10
    assert rows[0]["published_at"] == "2026-06-11T21:00:00Z"
    assert rows[0]["home_score"] == 2


def test_future_ranking_snapshot_is_not_visible(tmp_path: Path) -> None:
    external = tmp_path / "rankings.csv"
    pd.DataFrame([
        {"team": "Brasil", "rank": 3, "points": 1800, "published_at": "2026-06-01T00:00:00Z", "source": "official"},
        {"team": "Brasil", "rank": 1, "points": 1900, "published_at": "2026-07-20T00:00:00Z", "source": "official"},
    ]).to_csv(external, index=False)
    config = TemporalConfig({"paths": {"fifa_rankings": "rankings.csv"}}, root=tmp_path)
    selected = _latest_rankings(config, pd.Timestamp("2026-06-10T23:59:59Z"))
    assert int(selected["brasil"]["rank"]) == 3
