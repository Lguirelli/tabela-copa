import pandas as pd

from sports_engine.config import load_competition
from sports_engine.io import read_table
from sports_engine.player_facts import _clock_minute, derive_player_facts


def test_clock_parser_handles_stoppage_time():
    assert _clock_minute("90+4'") == 94
    assert _clock_minute("67'") == 67
    assert _clock_minute("NA") is None


def test_derived_player_facts_are_traceable_and_cover_every_match():
    config = load_competition("world_cup_2026")
    report = derive_player_facts(config)
    assert report["summary"]["status"] == "COMPLETED"

    stats = read_table(config.dataset("player_match_stats"))
    minutes = pd.to_numeric(stats["minutes"], errors="coerce")
    covered = set(pd.to_numeric(stats.loc[minutes.notna(), "match_id"], errors="coerce").dropna().astype(int))
    assert len(covered) == 104
    derived = stats[stats["minutes_data_quality"] == "DERIVED_POST_MATCH"]
    assert not derived.empty
    assert derived["minutes_derived_from"].eq("lineups+substitution_events+match_duration").all()

    availability = read_table(config.dataset("player_availability"))
    assert set(pd.to_numeric(availability["match_id"], errors="coerce").dropna().astype(int)) == set(range(1, 105))
    assert availability["status"].eq("AVAILABLE_MATCHDAY_SQUAD").all()
    assert availability["temporal_status"].eq("POST_MATCH_DERIVED_FACT").all()
