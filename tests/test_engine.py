from pathlib import Path

import yaml

from sports_engine.config import ROOT, load_competition, load_registry
from sports_engine.loops import completeness, feedback, features, patterns, recalibration, simulation, validation


def test_competition_configuration_loads():
    config = load_competition("world_cup_2026")
    assert config.name == "Copa do Mundo"
    assert config.dataset("matches").exists()
    assert config.dataset("results").exists()


def test_workflows_are_valid_yaml():
    workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
    assert {path.name for path in workflows} == {
        "ci.yml",
        "update_pipeline.yml",
        "static.yml",
    }
    for path in workflows:
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(payload, dict)
        assert "jobs" in payload


def test_completeness_creates_traceable_queue():
    config = load_competition("world_cup_2026")
    report = completeness.run(config)
    assert report["summary"]["matches_evaluated"] == 104
    assert (ROOT / "data" / "queues" / "missing_data.json").exists()
    assert (ROOT / "data" / "competitions" / "world_cup_2026" / "queues" / "missing_data.json").exists()


def test_validation_has_no_invalid_data():
    config = load_competition("world_cup_2026")
    report = validation.run(config)
    assert report["status"] in {"VALID", "CONFLICTING_DATA"}
    assert report["summary"]["invalid_issues"] == 0


def test_analytical_loops_generate_outputs():
    config = load_competition("world_cup_2026")
    assert patterns.run(config)["summary"]["team_match_rows"] > 0
    assert feedback.run(config)["summary"]["matches_compared"] == 104
    registry = features.run(config)
    assert "features" in registry
    recalibration.run(config)
    simulated = simulation.run(config)
    assert simulated["summary"]["matches_simulated"] == 104
    assert (ROOT / "models" / "simulations" / "latest.csv").exists()
    scoped_simulation = ROOT / "models" / "competitions" / "world_cup_2026" / "simulations" / "latest.csv"
    assert scoped_simulation.exists()
    import pandas as pd
    simulation_frame = pd.read_csv(scoped_simulation)
    knockout = simulation_frame[simulation_frame["probability_extra_time"] > 0]
    assert (knockout["probability_penalty_decision"] <= knockout["probability_extra_time"] + 1e-12).all()
