from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PAGES = [
    "rede-neural.html",
    "modelo-evolucao.html",
    "modelo-previsoes.html",
    "modelo-aprendizado.html",
    "modelo-simulacoes.html",
    "modelo-versoes.html",
]


def load_bundle() -> dict:
    path = ROOT / "src" / "model-analytics-data.js"
    text = path.read_text(encoding="utf-8")
    prefix = "window.WC2026_MODEL_ANALYTICS = "
    assert text.startswith(prefix)
    assert text.endswith(";\n")
    return json.loads(text[len(prefix):-2])


def test_model_dashboard_bundle_is_complete_and_temporal() -> None:
    payload = load_bundle()
    predictions = payload["predictions"]
    assert payload["summary"]["matches"] == 104
    assert len(predictions) == 104
    assert {row["matchId"] for row in predictions} == set(range(1, 105))
    assert len(payload["dailyEvolution"]) == 35
    assert len(payload["versions"]) >= 36
    assert len(payload["semanticVersions"]) >= 6
    assert len(payload["simulations"]) == 35
    assert payload["summary"]["activeConflicts"] == 0
    for prediction in predictions:
        prediction_at = datetime.fromisoformat(prediction["predictionAt"])
        kickoff_at = datetime.fromisoformat(prediction["kickoffAt"])
        assert prediction_at < kickoff_at
        assert prediction["actualScore"]
        assert 0 <= prediction["probabilityTeam1Win"] <= 1
        assert 0 <= prediction["probabilityDraw"] <= 1
        assert 0 <= prediction["probabilityTeam2Win"] <= 1


def test_model_pages_and_navigation_are_self_contained() -> None:
    expected_links = set(MODEL_PAGES)
    for filename in MODEL_PAGES:
        path = ROOT / filename
        assert path.exists(), filename
        html = path.read_text(encoding="utf-8")
        assert 'src/model-analytics-data.js' in html
        assert 'src/model-pages.js' in html
        hrefs = set(re.findall(r'href="([^"]+\.html)"', html))
        assert expected_links.issubset(hrefs)
        for href in hrefs:
            assert (ROOT / href).exists(), f"{filename}: link quebrado {href}"


def test_model_exporter_is_deterministic() -> None:
    first = (ROOT / "src" / "model-analytics-data.js").read_bytes()
    namespace: dict[str, object] = {"__name__": "not_main", "__file__": str(ROOT / "scripts" / "export_model_dashboard.py")}
    source = (ROOT / "scripts" / "export_model_dashboard.py").read_text(encoding="utf-8")
    exec(compile(source, "export_model_dashboard.py", "exec"), namespace)
    payload = namespace["build"]()
    body = "window.WC2026_MODEL_ANALYTICS = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + ";\n"
    assert first == body.encode("utf-8")
