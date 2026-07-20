import pandas as pd
import yaml

from worldcup_brain.config import load_config
from worldcup_brain.preworldcup import build_pre_worldcup_state
from worldcup_brain.temporal import build_timeline, parse_timestamp, visible_results


def test_timeline_prevents_result_leakage():
    config = load_config()
    timeline = build_timeline(config)
    assert len(timeline) == 104
    for _, row in timeline.iterrows():
        assert parse_timestamp(row["prediction_at"]) < parse_timestamp(row["result_available_at"])
        assert parse_timestamp(row["fixture_known_at"]) <= parse_timestamp(row["prediction_at"])


def test_current_match_result_is_not_visible_at_prediction():
    config = load_config()
    timeline = build_timeline(config)
    for _, row in timeline.iterrows():
        visible = visible_results(timeline, row["prediction_at"])
        assert int(row["match_id"]) not in set(visible["match_id"].astype(int))


def test_knockout_teams_are_hidden_until_prerequisites_finish():
    config = load_config()
    timeline = build_timeline(config).set_index("match_id")
    assert parse_timestamp(timeline.loc[73, "fixture_known_at"]) == parse_timestamp(timeline.loc[72, "result_available_at"])
    parents = config.get("bracket_parents")
    for match_id_text, parent_ids in parents.items():
        match_id = int(match_id_text)
        expected = max(parse_timestamp(timeline.loc[int(parent), "result_available_at"]) for parent in parent_ids)
        assert parse_timestamp(timeline.loc[match_id, "fixture_known_at"]) == expected


def test_pre_worldcup_missing_fields_remain_na():
    config = load_config()
    build_pre_worldcup_state(config)
    teams = pd.read_csv(config.output("data", "pre_worldcup_state", "teams.csv"))
    players = pd.read_csv(config.output("data", "pre_worldcup_state", "players.csv"))
    assert teams["fifa_ranking"].isna().all() or (teams["fifa_ranking"].astype(str) == "NA").all()
    assert players["injury_status"].isna().all() or (players["injury_status"].astype(str) == "NA").all()
    assert players["recent_minutes"].isna().all() or (players["recent_minutes"].astype(str) == "NA").all()


def test_temporal_workflows_are_valid_yaml():
    config = load_config()
    names = [
        "01_pre_worldcup_training.yml",
        "02_daily_tournament_simulation.yml",
        "03_post_match_learning.yml",
    ]
    for name in names:
        path = config.output(".github", "workflows", name)
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(payload, dict)
        assert "jobs" in payload


def test_generated_knowledge_ledger_has_no_future_records_when_present():
    config = load_config()
    path = config.output("data", "temporal", "prediction_knowledge_ledger.csv")
    if not path.exists() or path.stat().st_size == 0:
        return
    ledger = pd.read_csv(path)
    for _, row in ledger.iterrows():
        assert parse_timestamp(row["available_at"]) <= parse_timestamp(row["prediction_cutoff"])
        if row["record_type"] == "official_result":
            assert int(float(row["record_id"])) != int(row["prediction_match_id"])
