from __future__ import annotations

import json
import math
import random
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def normalize_name(value: str) -> str:
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("republica da coreia", "coreia do sul")
    value = value.replace("korea republic", "coreia do sul")
    value = value.replace("turkiye", "turquia")
    value = value.replace("cote d ivoire", "costa do marfim")
    value = value.replace("ivory coast", "costa do marfim")
    value = value.replace("congo dr", "rd congo")
    value = value.replace("congo - kinshasa", "rd congo")
    value = value.replace("netherlands", "paises baixos")
    value = value.replace("países baixos", "paises baixos")
    return " ".join(value.split())


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def pick_col(df: pd.DataFrame, options: List[str], default: str | None = None) -> str | None:
    for col in options:
        if col in df.columns:
            return col
    return default


def winner_label(g1: int, g2: int) -> int:
    if g1 > g2:
        return 0
    if g2 > g1:
        return 2
    return 1


def winner_name(team1: str, team2: str, g1: int, g2: int, goal_diff_float: float | None = None) -> str:
    if g1 > g2:
        return team1
    if g2 > g1:
        return team2
    # Em mata-mata a rede pode arredondar para empate; usa o sinal bruto como desempate técnico.
    if goal_diff_float is not None and abs(float(goal_diff_float)) > 1e-6:
        return team1 if goal_diff_float > 0 else team2
    return "Empate"


def safe_round_goals(g1_float: float, g2_float: float, max_goals: int = 7) -> Tuple[int, int]:
    g1 = int(np.clip(np.rint(g1_float), 0, max_goals))
    g2 = int(np.clip(np.rint(g2_float), 0, max_goals))
    return g1, g2


def load_base_tables(root: Path) -> Dict[str, pd.DataFrame]:
    data = root / "data"
    return {
        "matches": read_csv_safe(data / "matches.csv"),
        "real": read_csv_safe(data / "resultados_reais.csv"),
        "team_strengths": read_csv_safe(data / "database" / "team_strengths.csv"),
        "players": read_csv_safe(data / "database" / "players_database.csv"),
        "tactical": read_csv_safe(data / "database" / "teams_tactical.csv"),
    }


def build_team_feature_table(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    strengths = tables["team_strengths"].copy()
    players = tables["players"].copy()
    tactical = tables.get("tactical", pd.DataFrame()).copy()

    if strengths.empty:
        raise RuntimeError("data/database/team_strengths.csv não encontrado ou vazio.")

    team_col = pick_col(strengths, ["selecao", "Seleção"])
    strengths["team_key"] = strengths[team_col].map(normalize_name)

    player_agg = pd.DataFrame({"team_key": strengths["team_key"]})
    if not players.empty:
        pteam_col = pick_col(players, ["Seleção", "selecao"])
        players["team_key"] = players[pteam_col].map(normalize_name)
        idx_col = pick_col(players, ["Índice proxy 0-10", "Indice proxy 0-10", "indice_proxy_0_10"])
        liga_col = pick_col(players, ["Score liga/clube", "Score liga clube", "score_liga_clube"])
        caps_col = pick_col(players, ["Caps seleção", "Caps selecao"])
        gols_col = pick_col(players, ["Gols seleção", "Gols selecao"])
        pos_col = pick_col(players, ["Posição", "Posicao"])
        agg_spec = {}
        if idx_col:
            agg_spec["player_proxy_mean"] = (idx_col, "mean")
            agg_spec["player_proxy_top18"] = (idx_col, lambda s: s.nlargest(min(len(s), 18)).mean())
        if liga_col:
            agg_spec["league_score_mean"] = (liga_col, "mean")
            agg_spec["league_score_top11"] = (liga_col, lambda s: s.nlargest(min(len(s), 11)).mean())
        if caps_col:
            agg_spec["caps_mean"] = (caps_col, "mean")
            agg_spec["caps_total_players"] = (caps_col, "sum")
        if gols_col:
            agg_spec["goals_selection_total_players"] = (gols_col, "sum")
        if agg_spec:
            player_agg = players.groupby("team_key").agg(**agg_spec).reset_index()
        if pos_col and idx_col:
            pivot = players.pivot_table(index="team_key", columns=pos_col, values=idx_col, aggfunc="mean").reset_index()
            pivot.columns = ["team_key"] + [f"pos_{c}_score" for c in pivot.columns[1:]]
            player_agg = player_agg.merge(pivot, on="team_key", how="left")

    keep_strength_cols = [
        "team_key", "selecao", "codigo", "grupo", "forca_modelo_0_100",
        "ataque_score", "meio_score", "defesa_score", "goleiro_score",
        "experiencia_score", "intensidade_valor", "posse_valor", "pressao_valor",
        "caps_media", "caps_total", "gols_selecao_total"
    ]
    strengths_keep = strengths[[c for c in keep_strength_cols if c in strengths.columns]].copy()

    if not tactical.empty:
        tteam_col = pick_col(tactical, ["Seleção", "selecao"])
        if tteam_col:
            tactical["team_key"] = tactical[tteam_col].map(normalize_name)
            tactical_keep = tactical[[c for c in ["team_key", "Estilo técnico", "Sistema base", "Técnico"] if c in tactical.columns]].copy()
        else:
            tactical_keep = pd.DataFrame({"team_key": strengths["team_key"]})
    else:
        tactical_keep = pd.DataFrame({"team_key": strengths["team_key"]})

    team_features = strengths_keep.merge(player_agg, on="team_key", how="left").merge(tactical_keep, on="team_key", how="left")

    num_cols = team_features.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        team_features[col] = pd.to_numeric(team_features[col], errors="coerce")
        team_features[col] = team_features[col].fillna(team_features[col].median() if team_features[col].notna().any() else 0.0)
    return team_features


def build_match_dataset(root: Path) -> Tuple[pd.DataFrame, Dict[str, int], List[str]]:
    tables = load_base_tables(root)
    matches = tables["matches"].copy()
    real = tables["real"].copy()
    team_features = build_team_feature_table(tables)

    if matches.empty:
        raise RuntimeError("Arquivo data/matches.csv é obrigatório.")

    matches["jogo"] = matches["jogo"].astype(int)
    base = matches.copy()

    if not real.empty:
        real["jogo"] = real["jogo"].astype(int)
        keep_real = [c for c in ["jogo", "gols1_real", "gols2_real", "placar_real", "vencedor_real", "status_real"] if c in real.columns]
        base = base.merge(real[keep_real], on="jogo", how="left")
    else:
        base["gols1_real"] = np.nan
        base["gols2_real"] = np.nan

    base["team1_key"] = base["equipe1"].map(normalize_name)
    base["team2_key"] = base["equipe2"].map(normalize_name)
    base["date_ordinal"] = pd.to_datetime(base["data"], errors="coerce").map(lambda x: x.toordinal() if pd.notnull(x) else 0)
    min_ord = base["date_ordinal"].replace(0, np.nan).min()
    base["days_from_start"] = base["date_ordinal"].apply(lambda x: 0 if x == 0 or pd.isna(min_ord) else x - min_ord)
    base["is_knockout"] = (base["fase"] != "Fase de grupos").astype(float)
    base["grupo_num"] = base.get("grupo", "").fillna("").map(lambda g: max(0, ord(str(g)[0]) - 64) if str(g) and str(g)[0].isalpha() else 0)

    team_map = {k: i for i, k in enumerate(sorted(set(team_features["team_key"]) | set(base["team1_key"]) | set(base["team2_key"]))) }
    base["team1_id"] = base["team1_key"].map(team_map).fillna(0).astype(int)
    base["team2_id"] = base["team2_key"].map(team_map).fillna(0).astype(int)

    tf1 = team_features.add_prefix("t1_").rename(columns={"t1_team_key": "team1_key"})
    tf2 = team_features.add_prefix("t2_").rename(columns={"t2_team_key": "team2_key"})
    base = base.merge(tf1, on="team1_key", how="left").merge(tf2, on="team2_key", how="left")

    candidate_team_metrics = [
        "forca_modelo_0_100", "ataque_score", "meio_score", "defesa_score", "goleiro_score",
        "experiencia_score", "intensidade_valor", "posse_valor", "pressao_valor",
        "player_proxy_mean", "player_proxy_top18", "league_score_mean", "league_score_top11",
        "caps_mean", "caps_total", "caps_total_players", "goals_selection_total_players", "gols_selecao_total"
    ]
    numeric_features = ["days_from_start", "is_knockout", "grupo_num"]

    for metric in candidate_team_metrics:
        c1, c2 = f"t1_{metric}", f"t2_{metric}"
        if c1 in base.columns and c2 in base.columns:
            base[f"diff_{metric}"] = pd.to_numeric(base[c1], errors="coerce") - pd.to_numeric(base[c2], errors="coerce")
            base[f"sum_{metric}"] = pd.to_numeric(base[c1], errors="coerce") + pd.to_numeric(base[c2], errors="coerce")
            numeric_features.extend([f"diff_{metric}", f"sum_{metric}"])

    interaction_pairs = [
        ("t1_ataque_score", "t2_defesa_score", "attack_vs_def_1"),
        ("t2_ataque_score", "t1_defesa_score", "attack_vs_def_2"),
        ("t1_pressao_valor", "t2_posse_valor", "press_vs_posse_1"),
        ("t2_pressao_valor", "t1_posse_valor", "press_vs_posse_2"),
    ]
    for a, b, out in interaction_pairs:
        if a in base.columns and b in base.columns:
            base[out] = pd.to_numeric(base[a], errors="coerce") - pd.to_numeric(base[b], errors="coerce")
            numeric_features.append(out)

    base["has_real"] = base["gols1_real"].notna() & base["gols2_real"].notna()
    base["target_goal_diff"] = pd.to_numeric(base["gols1_real"], errors="coerce") - pd.to_numeric(base["gols2_real"], errors="coerce")
    base["target_total_goals"] = pd.to_numeric(base["gols1_real"], errors="coerce") + pd.to_numeric(base["gols2_real"], errors="coerce")
    base["target_winner"] = base.apply(lambda r: winner_label(int(r["gols1_real"]), int(r["gols2_real"])) if bool(r["has_real"]) else np.nan, axis=1)

    for col in numeric_features:
        if col not in base.columns:
            base[col] = 0.0
        base[col] = pd.to_numeric(base[col], errors="coerce")
        base[col] = base[col].fillna(base[col].median() if base[col].notna().any() else 0.0)

    return base, team_map, numeric_features


def build_scaler(train_df: pd.DataFrame, numeric_features: List[str]) -> Dict[str, Dict[str, float]]:
    scaler = {}
    for col in numeric_features:
        mean = float(train_df[col].mean())
        std = float(train_df[col].std(ddof=0))
        if not np.isfinite(std) or std < 1e-6:
            std = 1.0
        scaler[col] = {"mean": mean, "std": std}
    return scaler


def transform_numeric(df: pd.DataFrame, numeric_features: List[str], scaler: Dict[str, Dict[str, float]]) -> np.ndarray:
    arr = []
    for col in numeric_features:
        stats = scaler[col]
        arr.append(((pd.to_numeric(df[col], errors="coerce").fillna(stats["mean"]) - stats["mean"]) / stats["std"]).to_numpy(dtype=np.float32))
    return np.stack(arr, axis=1).astype(np.float32)


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_seeds(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except Exception:
        pass
