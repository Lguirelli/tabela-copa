
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def to_js_assignment(name: str, value) -> str:
    return f"window.{name} = {json.dumps(value, ensure_ascii=False, separators=(',', ':'))};\n"


def export_frontend(root: Path | None = None):
    root = Path(root or Path(__file__).resolve().parents[1])
    data_dir = root / "data" / "rede_neural"
    metrics_path = data_dir / "metricas_rede_neural.json"
    pred_path = data_dir / "previsoes_rede_neural.csv"
    hist_path = data_dir / "historico_treinamento.csv"
    schema_path = data_dir / "schema_features_rede_neural.csv"

    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    preds = pd.read_csv(pred_path).head(104).fillna("").to_dict(orient="records") if pred_path.exists() else []
    hist = pd.read_csv(hist_path).tail(120).fillna("").to_dict(orient="records") if hist_path.exists() else []
    schema = pd.read_csv(schema_path).fillna("").head(80).to_dict(orient="records") if schema_path.exists() else []

    js = "".join([
        to_js_assignment("WC2026_REDE_NEURAL_METRICAS", metrics),
        to_js_assignment("WC2026_REDE_NEURAL_PREVISOES", preds),
        to_js_assignment("WC2026_REDE_NEURAL_HISTORICO", hist),
        to_js_assignment("WC2026_REDE_NEURAL_SCHEMA", schema),
    ])
    (root / "src" / "rede-neural-data.js").write_text(js, encoding="utf-8")


if __name__ == "__main__":
    export_frontend()
    print("src/rede-neural-data.js atualizado")
