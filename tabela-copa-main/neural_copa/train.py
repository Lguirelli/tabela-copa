
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
try:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except Exception:
    pass
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .config import NeuralCopaConfig
from .data_utils import (
    build_match_dataset, build_scaler, save_json, set_seeds, transform_numeric,
    safe_round_goals, winner_label, winner_name
)
from .modeling import CopaMatchNet


def chronological_split(trainable: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    trainable = trainable.sort_values(["data", "jogo"]).reset_index(drop=True)
    if len(trainable) < 12:
        return trainable, trainable.iloc[0:0].copy()
    split = max(8, int(len(trainable) * 0.78))
    split = min(split, len(trainable) - 4)
    return trainable.iloc[:split].copy(), trainable.iloc[split:].copy()


def make_loader(df: pd.DataFrame, numeric_features: List[str], scaler: Dict[str, Dict[str, float]], batch_size: int = 16, shuffle: bool = True) -> DataLoader:
    x_num = torch.tensor(transform_numeric(df, numeric_features, scaler), dtype=torch.float32)
    t1 = torch.tensor(df["team1_id"].to_numpy(dtype=np.int64), dtype=torch.long)
    t2 = torch.tensor(df["team2_id"].to_numpy(dtype=np.int64), dtype=torch.long)
    y = torch.tensor(df[["target_goal_diff", "target_total_goals"]].to_numpy(dtype=np.float32), dtype=torch.float32)
    return DataLoader(TensorDataset(t1, t2, x_num, y), batch_size=batch_size, shuffle=shuffle)


def predict_raw(model: CopaMatchNet, df: pd.DataFrame, numeric_features: List[str], scaler: Dict[str, Dict[str, float]]) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        x_num = torch.tensor(transform_numeric(df, numeric_features, scaler), dtype=torch.float32)
        t1 = torch.tensor(df["team1_id"].to_numpy(dtype=np.int64), dtype=torch.long)
        t2 = torch.tensor(df["team2_id"].to_numpy(dtype=np.int64), dtype=torch.long)
        return model(t1, t2, x_num).cpu().numpy()


def metrics_for(df: pd.DataFrame, pred: np.ndarray, max_goals: int) -> Dict[str, float]:
    if df.empty:
        return {}
    rows = []
    for (_, r), (diff, total) in zip(df.iterrows(), pred):
        # Gera gols brutos e usa arredondamento seguro.
        g1f = (float(total) + float(diff)) / 2.0
        g2f = (float(total) - float(diff)) / 2.0
        pg1, pg2 = safe_round_goals(g1f, g2f, max_goals=max_goals)
        rg1, rg2 = int(r["gols1_real"]), int(r["gols2_real"])
        rows.append({
            "abs_diff_error": abs((rg1 - rg2) - (pg1 - pg2)),
            "abs_total_error": abs((rg1 + rg2) - (pg1 + pg2)),
            "total_goal_error": abs(rg1 - pg1) + abs(rg2 - pg2),
            "winner_ok": winner_label(rg1, rg2) == winner_label(pg1, pg2),
            "exact_score": rg1 == pg1 and rg2 == pg2,
        })
    m = pd.DataFrame(rows)
    return {
        "mae_goal_diff": round(float(m["abs_diff_error"].mean()), 4),
        "mae_total_goals": round(float(m["abs_total_error"].mean()), 4),
        "erro_medio_total_gols": round(float(m["total_goal_error"].mean()), 4),
        "acuracia_vencedor": round(float(m["winner_ok"].mean() * 100), 2),
        "placar_exato": round(float(m["exact_score"].mean() * 100), 2),
        "amostras": int(len(m)),
    }


def run_training(root: Path | None = None, config: NeuralCopaConfig | None = None) -> Dict:
    config = config or NeuralCopaConfig()
    root = Path(root or config.root)
    output_dir = root / "data" / "rede_neural"
    output_dir.mkdir(parents=True, exist_ok=True)

    set_seeds(config.seed)
    dataset, team_map, numeric_features = build_match_dataset(root)
    trainable = dataset[dataset["has_real"]].copy()
    train_df, val_df = chronological_split(trainable)
    scaler = build_scaler(train_df, numeric_features)

    train_loader = make_loader(train_df, numeric_features, scaler, batch_size=16, shuffle=True)
    val_loader = make_loader(val_df if not val_df.empty else train_df, numeric_features, scaler, batch_size=32, shuffle=False)

    model = CopaMatchNet(
        num_teams=len(team_map),
        num_numeric_features=len(numeric_features),
        embedding_dim=config.embedding_dim,
        hidden_dim_1=config.hidden_dim_1,
        hidden_dim_2=config.hidden_dim_2,
        hidden_dim_3=config.hidden_dim_3,
        dropout=config.dropout,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    criterion = nn.SmoothL1Loss(beta=0.8)

    best_state = None
    best_val = float("inf")
    patience_left = config.patience
    history = []

    for epoch in range(1, config.epochs + 1):
        model.train()
        train_loss = 0.0
        batches = 0
        for t1, t2, x_num, y in train_loader:
            optimizer.zero_grad(set_to_none=True)
            out = model(t1, t2, x_num)
            loss = criterion(out, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=4.0)
            optimizer.step()
            train_loss += float(loss.item())
            batches += 1
        train_loss /= max(1, batches)

        model.eval()
        val_loss = 0.0
        val_batches = 0
        with torch.no_grad():
            for t1, t2, x_num, y in val_loader:
                out = model(t1, t2, x_num)
                loss = criterion(out, y)
                val_loss += float(loss.item())
                val_batches += 1
        val_loss /= max(1, val_batches)
        history.append({"epoch": epoch, "train_loss": round(train_loss, 6), "val_loss": round(val_loss, 6)})

        if val_loss < best_val - 1e-5:
            best_val = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_left = config.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    train_pred = predict_raw(model, train_df, numeric_features, scaler)
    val_pred = predict_raw(model, val_df, numeric_features, scaler) if not val_df.empty else np.empty((0, 2))
    all_pred = predict_raw(model, dataset, numeric_features, scaler)

    train_metrics = metrics_for(train_df, train_pred, config.max_goals)
    val_metrics = metrics_for(val_df, val_pred, config.max_goals)

    # Gera previsão neural pura para todos os jogos.
    rows = []
    for (_, r), (diff_pred, total_pred) in zip(dataset.iterrows(), all_pred):
        g1_neural_float = (float(total_pred) + float(diff_pred)) / 2.0
        g2_neural_float = (float(total_pred) - float(diff_pred)) / 2.0
        pg1, pg2 = safe_round_goals(g1_neural_float, g2_neural_float, max_goals=config.max_goals)
        win = winner_name(r.get("equipe1", ""), r.get("equipe2", ""), pg1, pg2, goal_diff_float=float(diff_pred))
        rows.append({
            "jogo": int(r["jogo"]),
            "fase": r.get("fase", ""),
            "grupo": r.get("grupo", ""),
            "data": r.get("data", ""),
            "equipe1": r.get("equipe1", ""),
            "equipe2": r.get("equipe2", ""),
            "gols1_neural_float": round(g1_neural_float, 4),
            "gols2_neural_float": round(g2_neural_float, 4),
            "goal_diff_neural_float": round(float(diff_pred), 4),
            "total_goals_neural_float": round(float(total_pred), 4),
            "placar_rede_neural": f"{pg1}-{pg2}",
            "gols1_rede_neural": pg1,
            "gols2_rede_neural": pg2,
            "vencedor_rede_neural": win,
            "possui_real": "Sim" if bool(r.get("has_real", False)) else "Não",
            "placar_real": r.get("placar_real", "") if bool(r.get("has_real", False)) else "",
        })
    pred_df = pd.DataFrame(rows)

    dataset_out = dataset[[
        "jogo", "data", "fase", "grupo", "equipe1", "equipe2", "team1_id", "team2_id", "has_real",
        "gols1_real", "gols2_real", "target_goal_diff", "target_total_goals"
    ] + numeric_features].copy()

    feature_schema = pd.DataFrame({
        "feature": numeric_features,
        "tipo": ["numérica padronizada"] * len(numeric_features),
        "uso": ["entrada da MLP / rede neural"] * len(numeric_features),
    })

    metrics = {
        "modelo": "CopaMatchNet PyTorch MLP + embeddings",
        "base_referencia": "NVIDIA DeepLearningExamples: arquitetura modular PyTorch adaptada, sem copiar modelo pesado",
        "amostras_reais": int(len(trainable)),
        "amostras_treino": int(len(train_df)),
        "amostras_validacao_cronologica": int(len(val_df)),
        "jogos_totais_inferidos": int(len(dataset)),
        "variaveis_numericas": int(len(numeric_features)),
        "times_com_embedding": int(len(team_map)),
        "treino": train_metrics,
        "validacao_cronologica": val_metrics,
        "epochs_executados": int(history[-1]["epoch"] if history else 0),
        "best_val_loss": round(float(best_val), 6),
        "observacao": "A rede neural é a fonte única de previsão do repositório. Entradas auxiliares são dados de elenco, ligas, técnicos, calendário e resultados reais, usando somente a rede neural como fonte de previsão.",
    }

    torch.save({
        "model_state_dict": model.state_dict(),
        "team_map": team_map,
        "numeric_features": numeric_features,
        "scaler": scaler,
        "config": config.__dict__,
        "metrics": metrics,
    }, output_dir / "modelo_rede_neural_copa.pt")

    pred_df.to_csv(output_dir / "previsoes_rede_neural.csv", index=False)
    dataset_out.to_csv(output_dir / "dataset_treinamento_rede_neural.csv", index=False)
    feature_schema.to_csv(output_dir / "schema_features_rede_neural.csv", index=False)
    pd.DataFrame(history).to_csv(output_dir / "historico_treinamento.csv", index=False)
    pd.DataFrame([{"team_key": k, "team_id": v} for k, v in team_map.items()]).to_csv(output_dir / "team_embeddings_map.csv", index=False)
    save_json(output_dir / "metricas_rede_neural.json", metrics)

    return metrics


if __name__ == "__main__":
    metrics = run_training()
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
