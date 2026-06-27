
from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import torch
try:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except Exception:
    pass

from .config import NeuralCopaConfig
from .data_utils import build_match_dataset, transform_numeric, safe_round_goals, winner_name
from .modeling import CopaMatchNet


def run_inference(root: Path | None = None) -> pd.DataFrame:
    config = NeuralCopaConfig()
    root = Path(root or config.root)
    ckpt_path = root / "data" / "rede_neural" / "modelo_rede_neural_copa.pt"
    if not ckpt_path.exists():
        raise RuntimeError("Checkpoint não encontrado. Rode: python scripts/treinar_rede_neural_copa.py")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    dataset, _, _ = build_match_dataset(root)
    numeric_features = ckpt["numeric_features"]
    scaler = ckpt["scaler"]
    cfg = ckpt.get("config", {})
    model = CopaMatchNet(
        num_teams=len(ckpt["team_map"]),
        num_numeric_features=len(numeric_features),
        embedding_dim=cfg.get("embedding_dim", 8),
        hidden_dim_1=cfg.get("hidden_dim_1", 96),
        hidden_dim_2=cfg.get("hidden_dim_2", 64),
        hidden_dim_3=cfg.get("hidden_dim_3", 32),
        dropout=0.0,
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    with torch.no_grad():
        x_num = torch.tensor(transform_numeric(dataset, numeric_features, scaler), dtype=torch.float32)
        t1 = torch.tensor(dataset["team1_id"].to_numpy(), dtype=torch.long)
        t2 = torch.tensor(dataset["team2_id"].to_numpy(), dtype=torch.long)
        raw = model(t1, t2, x_num).cpu().numpy()
    rows = []
    max_goals = cfg.get("max_goals", 7)
    for (_, r), (diff, total) in zip(dataset.iterrows(), raw):
        g1f = (float(total) + float(diff)) / 2.0
        g2f = (float(total) - float(diff)) / 2.0
        g1, g2 = safe_round_goals(g1f, g2f, max_goals=max_goals)
        rows.append({
            "jogo": int(r["jogo"]),
            "data": r.get("data", ""),
            "fase": r.get("fase", ""),
            "equipe1": r.get("equipe1", ""),
            "equipe2": r.get("equipe2", ""),
            "placar_rede_neural_puro": f"{g1}-{g2}",
            "vencedor_rede_neural_puro": winner_name(r.get("equipe1", ""), r.get("equipe2", ""), g1, g2),
        })
    out = pd.DataFrame(rows)
    out_path = root / "data" / "rede_neural" / "inferencia_rede_neural_pura.csv"
    out.to_csv(out_path, index=False)
    return out


if __name__ == "__main__":
    df = run_inference()
    print(f"Inferência gerada para {len(df)} jogos")
