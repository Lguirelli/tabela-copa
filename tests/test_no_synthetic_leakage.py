import json

from sports_engine.config import ROOT
from sports_engine.config import load_competition
from sports_engine.loops import features


def test_feature_registry_excludes_simulated_fields():
    features.run(load_competition("world_cup_2026"))
    payload = json.loads((ROOT / "models" / "features_registry.json").read_text(encoding="utf-8"))
    assert all("simulad" not in item["feature"].lower() for item in payload["features"])
