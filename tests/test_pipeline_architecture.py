from pathlib import Path

import yaml

from sports_engine.config import ROOT


def test_single_writer_pipeline_and_no_two_hour_schedule():
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = sorted(workflow_dir.glob("*.yml"))
    assert [path.name for path in workflows] == ["ci.yml", "static.yml", "update_pipeline.yml"]

    update = (workflow_dir / "update_pipeline.yml").read_text(encoding="utf-8")
    assert "scripts/run_repository_pipeline.py" in update
    assert "schedule:" not in update
    assert "cron:" not in update
    assert "github.actor != 'github-actions[bot]'" in update
    assert "for path in data logs" not in update

    writers = []
    for path in workflows:
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        permissions = payload.get("permissions", {})
        if isinstance(permissions, dict) and permissions.get("contents") == "write":
            writers.append(path.name)
    assert writers == ["update_pipeline.yml"]


def test_legacy_implementation_is_isolated():
    assert not (ROOT / "neural_copa").exists()
    assert (ROOT / "legacy" / "neural_copa").is_dir()
    assert not (ROOT / "scripts" / "modelo_neural_diario.py").exists()
    assert (ROOT / "legacy" / "scripts" / "modelo_neural_diario.py").is_file()
