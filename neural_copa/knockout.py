from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch
try:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except Exception:
    pass

from .config import NeuralCopaConfig
from .data_utils import (
    build_team_feature_table,
    load_base_tables,
    normalize_name,
    read_csv_safe,
    safe_round_goals,
    winner_name,
)
from .modeling import CopaMatchNet

THIRD_SLOTS = {
    74: ["A", "B", "C", "D", "F"],
    77: ["C", "D", "F", "G", "H"],
    79: ["C", "E", "F", "H", "I"],
    80: ["E", "H", "I", "J", "K"],
    81: ["B", "E", "F", "I", "J"],
    82: ["A", "E", "H", "I", "J"],
    85: ["E", "F", "G", "I", "J"],
    87: ["D", "E", "I", "J", "L"],
}

R32_ORDER = list(range(73, 89))
PROGRESSION = {
    89: (73, 75), 90: (74, 77), 91: (76, 78), 92: (79, 80),
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
    101: (97, 98), 102: (99, 100), 104: (101, 102),
}
THIRD_PLACE = 103

TEAM_METRICS = [
    "forca_modelo_0_100", "ataque_score", "meio_score", "defesa_score", "goleiro_score",
    "experiencia_score", "intensidade_valor", "posse_valor", "pressao_valor",
    "player_proxy_mean", "player_proxy_top18", "league_score_mean", "league_score_top11",
    "caps_mean", "caps_total", "caps_total_players", "goals_selection_total_players", "gols_selecao_total",
]

INTERACTIONS = [
    ("ataque_score", "defesa_score", "attack_vs_def_1"),
    ("ataque_score", "defesa_score", "attack_vs_def_2"),
    ("pressao_valor", "posse_valor", "press_vs_posse_1"),
    ("pressao_valor", "posse_valor", "press_vs_posse_2"),
]


def parse_score(value: str | float | int | None) -> Tuple[int, int] | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip().lower().replace(" ", "")
    for sep in ("-", "x", ":"):
        if sep in text:
            a, b = text.split(sep, 1)
            if a.isdigit() and b.isdigit():
                return int(a), int(b)
    return None


def result_winner(team1: str, team2: str, score: str, raw_diff: float | None = None) -> str:
    parsed = parse_score(score)
    if not parsed:
        return ""
    g1, g2 = parsed
    return winner_name(team1, team2, g1, g2, goal_diff_float=raw_diff)


def loser_name(team1: str, team2: str, winner: str) -> str:
    if normalize_name(winner) == normalize_name(team1):
        return team2
    if normalize_name(winner) == normalize_name(team2):
        return team1
    return team2


def load_checkpoint(root: Path):
    config = NeuralCopaConfig()
    ckpt_path = root / "data" / "rede_neural" / "modelo_rede_neural_copa.pt"
    if not ckpt_path.exists():
        raise RuntimeError("Checkpoint da rede neural não encontrado. Treine a rede primeiro.")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = ckpt.get("config", {})
    model = CopaMatchNet(
        num_teams=len(ckpt["team_map"]),
        num_numeric_features=len(ckpt["numeric_features"]),
        embedding_dim=cfg.get("embedding_dim", config.embedding_dim),
        hidden_dim_1=cfg.get("hidden_dim_1", config.hidden_dim_1),
        hidden_dim_2=cfg.get("hidden_dim_2", config.hidden_dim_2),
        hidden_dim_3=cfg.get("hidden_dim_3", config.hidden_dim_3),
        dropout=0.0,
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return ckpt, model


def group_standings(matches: pd.DataFrame, preds: pd.DataFrame) -> Dict[str, List[dict]]:
    pred_map = {int(r["jogo"]): r for _, r in preds.iterrows()}
    standings: Dict[str, Dict[str, dict]] = {}
    group_matches = matches[matches["fase"] == "Fase de grupos"].copy()

    for group, gdf in group_matches.groupby("grupo", sort=True):
        teams: List[str] = []
        for _, r in gdf.sort_values("jogo").iterrows():
            for team in (r["equipe1"], r["equipe2"]):
                if team not in teams:
                    teams.append(team)
        standings[group] = {team: {"grupo": group, "team": team, "pts": 0, "j": 0, "v": 0, "e": 0, "d": 0, "gf": 0, "ga": 0, "sg": 0} for team in teams}

    for _, base in group_matches.sort_values("jogo").iterrows():
        jogo = int(base["jogo"])
        pred = pred_map.get(jogo)
        if pred is None:
            continue
        team1, team2 = str(base["equipe1"]), str(base["equipe2"])
        score = pred.get("placar_real") if str(pred.get("possui_real", "")) == "Sim" and str(pred.get("placar_real", "")) else pred.get("placar_rede_neural")
        parsed = parse_score(score)
        if not parsed:
            continue
        g1, g2 = parsed
        table = standings[str(base["grupo"])]
        if team1 not in table or team2 not in table:
            continue
        a, b = table[team1], table[team2]
        a["j"] += 1; b["j"] += 1
        a["gf"] += g1; a["ga"] += g2
        b["gf"] += g2; b["ga"] += g1
        if g1 > g2:
            a["v"] += 1; b["d"] += 1; a["pts"] += 3
        elif g2 > g1:
            b["v"] += 1; a["d"] += 1; b["pts"] += 3
        else:
            a["e"] += 1; b["e"] += 1; a["pts"] += 1; b["pts"] += 1

    out: Dict[str, List[dict]] = {}
    for group, rows in standings.items():
        values = []
        for row in rows.values():
            row["sg"] = row["gf"] - row["ga"]
            values.append(row)
        out[group] = sorted(values, key=lambda r: (-r["pts"], -r["sg"], -r["gf"], r["team"]))
    return out


def assign_third_slots(standings: Dict[str, List[dict]]) -> Tuple[Dict[int, str], List[dict]]:
    thirds = []
    for group, rows in standings.items():
        if len(rows) >= 3:
            item = deepcopy(rows[2])
            item["rank_terceiro"] = 0
            thirds.append(item)
    thirds = sorted(thirds, key=lambda r: (-r["pts"], -r["sg"], -r["gf"], r["team"]))[:8]
    for idx, item in enumerate(thirds, start=1):
        item["rank_terceiro"] = idx
    groups_available = {r["grupo"]: r for r in thirds}
    slot_items = list(THIRD_SLOTS.items())
    best_assign = None
    best_score = float("inf")

    def backtrack(i: int, used: set[str], assign: Dict[int, str], score: float):
        nonlocal best_assign, best_score
        if score >= best_score:
            return
        if i == len(slot_items):
            best_assign = assign.copy()
            best_score = score
            return
        slot, candidates = slot_items[i]
        options = [g for g in candidates if g in groups_available and g not in used]
        options.sort(key=lambda g: groups_available[g]["rank_terceiro"])
        for group in options:
            used.add(group)
            assign[slot] = groups_available[group]["team"]
            backtrack(i + 1, used, assign, score + groups_available[group]["rank_terceiro"])
            used.remove(group)
            assign.pop(slot, None)

    backtrack(0, set(), {}, 0)
    if best_assign is None:
        best_assign = {}
        used = set()
        for slot, candidates in slot_items:
            for group in candidates:
                if group in groups_available and group not in used:
                    best_assign[slot] = groups_available[group]["team"]
                    used.add(group)
                    break
    return best_assign, thirds


def get_team_value(team_features: pd.DataFrame, team: str, metric: str) -> float:
    key = normalize_name(team)
    rows = team_features[team_features["team_key"] == key]
    if rows.empty or metric not in rows.columns:
        return 0.0
    value = pd.to_numeric(rows.iloc[0][metric], errors="coerce")
    return float(value) if pd.notna(value) else 0.0


def predict_match(root: Path, ckpt: dict, model: CopaMatchNet, team_features: pd.DataFrame, matches: pd.DataFrame, match_row: pd.Series, team1: str, team2: str) -> dict:
    numeric_features = ckpt["numeric_features"]
    scaler = ckpt["scaler"]
    cfg = ckpt.get("config", {})
    team_map = ckpt["team_map"]
    min_date = pd.to_datetime(matches["data"], errors="coerce").min()
    date = pd.to_datetime(match_row.get("data", None), errors="coerce")
    days = int((date - min_date).days) if pd.notna(date) and pd.notna(min_date) else 0

    values = {feature: 0.0 for feature in numeric_features}
    values["days_from_start"] = float(days)
    values["is_knockout"] = 1.0 if match_row.get("fase") != "Fase de grupos" else 0.0
    group = str(match_row.get("grupo", "") or "")
    values["grupo_num"] = float(max(0, ord(group[0]) - 64)) if group and group[0].isalpha() else 0.0

    for metric in TEAM_METRICS:
        v1 = get_team_value(team_features, team1, metric)
        v2 = get_team_value(team_features, team2, metric)
        values[f"diff_{metric}"] = v1 - v2
        values[f"sum_{metric}"] = v1 + v2

    values["attack_vs_def_1"] = get_team_value(team_features, team1, "ataque_score") - get_team_value(team_features, team2, "defesa_score")
    values["attack_vs_def_2"] = get_team_value(team_features, team2, "ataque_score") - get_team_value(team_features, team1, "defesa_score")
    values["press_vs_posse_1"] = get_team_value(team_features, team1, "pressao_valor") - get_team_value(team_features, team2, "posse_valor")
    values["press_vs_posse_2"] = get_team_value(team_features, team2, "pressao_valor") - get_team_value(team_features, team1, "posse_valor")

    arr = []
    for feature in numeric_features:
        stats = scaler[feature]
        raw = values.get(feature, stats.get("mean", 0.0))
        arr.append((float(raw) - float(stats.get("mean", 0.0))) / float(stats.get("std", 1.0) or 1.0))

    t1 = torch.tensor([team_map.get(normalize_name(team1), 0)], dtype=torch.long)
    t2 = torch.tensor([team_map.get(normalize_name(team2), 0)], dtype=torch.long)
    x = torch.tensor([arr], dtype=torch.float32)
    with torch.no_grad():
        diff, total = model(t1, t2, x).cpu().numpy()[0]
    g1f = (float(total) + float(diff)) / 2.0
    g2f = (float(total) - float(diff)) / 2.0
    g1, g2 = safe_round_goals(g1f, g2f, max_goals=cfg.get("max_goals", 7))
    win = winner_name(team1, team2, g1, g2, goal_diff_float=float(diff))
    return {
        "gols1_neural_float": round(g1f, 4),
        "gols2_neural_float": round(g2f, 4),
        "goal_diff_neural_float": round(float(diff), 4),
        "total_goals_neural_float": round(float(total), 4),
        "placar_rede_neural": f"{g1}-{g2}",
        "gols1_rede_neural": int(g1),
        "gols2_rede_neural": int(g2),
        "vencedor_rede_neural": win,
    }


def make_js_data(root: Path, matches: pd.DataFrame):
    """Exporta dados base para o frontend.

    O visualizador é estático e não lê CSV diretamente no navegador. Por isso,
    todo resultado manual registrado em data/resultados_reais.csv precisa ser
    incorporado ao src/data.js. Este merge evita que jogos finalizados fiquem
    aparecendo como "Rede neural" quando o CSV já foi atualizado, mas o JS ainda
    não tinha os campos de resultado.
    """
    matches_for_js = matches.copy()

    real = read_csv_safe(root / "data" / "resultados_reais.csv")
    if not real.empty and "jogo" in real.columns:
        real_cols = [
            c for c in [
                "jogo", "placar_real", "vencedor_real", "gols1_real", "gols2_real",
                "status_real", "fonte", "placar_original"
            ] if c in real.columns
        ]
        real_view = real[real_cols].copy()
        real_view["jogo"] = pd.to_numeric(real_view["jogo"], errors="coerce").astype("Int64")
        matches_for_js["jogo"] = pd.to_numeric(matches_for_js["jogo"], errors="coerce").astype("Int64")
        matches_for_js = matches_for_js.merge(real_view, on="jogo", how="left")
        has_real = matches_for_js["placar_real"].notna() & (matches_for_js["placar_real"].astype(str).str.strip() != "")
        matches_for_js.loc[has_real, "status"] = "Finalizado"

    group_rows = matches_for_js[matches_for_js["fase"] == "Fase de grupos"].copy()
    groups = []
    for group in sorted(group_rows["grupo"].dropna().unique()):
        teams = []
        for _, r in group_rows[group_rows["grupo"] == group].sort_values("jogo").iterrows():
            for team in (r["equipe1"], r["equipe2"]):
                if team not in teams:
                    teams.append(team)
        groups.append({"grupo": group, "equipes": teams})
    data = {
        "summary": {
            "totalJogos": int(len(matches_for_js)),
            "faseGrupos": int((matches_for_js["fase"] == "Fase de grupos").sum()),
            "mataMata": int((matches_for_js["fase"] != "Fase de grupos").sum()),
            "grupos": int(group_rows["grupo"].nunique()),
            "selecoes": int(len({t for _, r in group_rows.iterrows() for t in [r["equipe1"], r["equipe2"]]})),
            "periodo": f"{matches_for_js['data'].min()} a {matches_for_js['data'].max()}",
            "resultadosReais": int((matches_for_js.get("placar_real", pd.Series(dtype=object)).notna()).sum()) if "placar_real" in matches_for_js.columns else 0,
        },
        "groups": groups,
        "matches": matches_for_js.replace({np.nan: None}).to_dict(orient="records"),
    }
    (root / "src" / "data.js").write_text("window.WC2026_DATA = " + json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + ";\n", encoding="utf-8")


def rebuild_knockout_from_neural(root: Path | None = None) -> pd.DataFrame:
    root = Path(root or NeuralCopaConfig().root)
    data_dir = root / "data" / "rede_neural"
    matches_path = root / "data" / "matches.csv"
    preds_path = data_dir / "previsoes_rede_neural.csv"
    infer_path = data_dir / "inferencia_rede_neural_pura.csv"

    matches = read_csv_safe(matches_path)
    preds = read_csv_safe(preds_path)
    real = read_csv_safe(root / "data" / "resultados_reais.csv")
    if matches.empty or preds.empty:
        raise RuntimeError("matches.csv ou previsoes_rede_neural.csv não encontrado.")

    ckpt, model = load_checkpoint(root)
    team_features = build_team_feature_table(load_base_tables(root))
    real_map = {int(r["jogo"]): r for _, r in real.iterrows()} if not real.empty else {}

    standings = group_standings(matches, preds)
    third_assignment, best_thirds = assign_third_slots(standings)

    def pos(group: str, idx: int) -> str:
        return standings[group][idx]["team"]

    r32 = {
        73: (pos("A", 1), pos("B", 1)),
        74: (pos("E", 0), third_assignment.get(74, "TBD")),
        75: (pos("F", 0), pos("C", 1)),
        76: (pos("C", 0), pos("F", 1)),
        77: (pos("I", 0), third_assignment.get(77, "TBD")),
        78: (pos("E", 1), pos("I", 1)),
        79: (pos("A", 0), third_assignment.get(79, "TBD")),
        80: (pos("L", 0), third_assignment.get(80, "TBD")),
        81: (pos("D", 0), third_assignment.get(81, "TBD")),
        82: (pos("G", 0), third_assignment.get(82, "TBD")),
        83: (pos("K", 1), pos("L", 1)),
        84: (pos("H", 0), pos("J", 1)),
        85: (pos("B", 0), third_assignment.get(85, "TBD")),
        86: (pos("J", 0), pos("H", 1)),
        87: (pos("K", 0), third_assignment.get(87, "TBD")),
        88: (pos("D", 1), pos("G", 1)),
    }

    pred_rows = {int(r["jogo"]): r.to_dict() for _, r in preds.iterrows()}
    resolved: Dict[int, dict] = {}
    matches_updated = matches.copy()

    def process_game(game: int, team1: str, team2: str):
        row_idx = matches_updated.index[matches_updated["jogo"].astype(int) == int(game)][0]
        base_row = matches_updated.loc[row_idx].copy()
        matches_updated.at[row_idx, "equipe1"] = team1
        matches_updated.at[row_idx, "equipe2"] = team2
        matches_updated.at[row_idx, "confronto"] = f"{team1} x {team2}"
        matches_updated.at[row_idx, "status"] = "Rede neural"

        prediction = predict_match(root, ckpt, model, team_features, matches_updated, base_row, team1, team2)
        real_row = real_map.get(int(game))
        has_real = real_row is not None and str(real_row.get("placar_real", ""))
        real_score = str(real_row.get("placar_real", "")) if has_real else ""
        real_winner = str(real_row.get("vencedor_real", "")) if has_real else ""
        winner = real_winner if has_real else prediction["vencedor_rede_neural"]
        loser = loser_name(team1, team2, winner)
        pred_rows[int(game)] = {
            "jogo": int(game),
            "fase": base_row.get("fase", ""),
            "grupo": base_row.get("grupo", ""),
            "data": base_row.get("data", ""),
            "equipe1": team1,
            "equipe2": team2,
            **prediction,
            "possui_real": "Sim" if has_real else "Não",
            "placar_real": real_score,
        }
        resolved[int(game)] = {"team1": team1, "team2": team2, "winner": winner, "loser": loser, "score": prediction["placar_rede_neural"]}

    for game in R32_ORDER:
        process_game(game, *r32[game])
    for game in range(89, 103):
        if game == THIRD_PLACE:
            process_game(game, resolved[101]["loser"], resolved[102]["loser"])
        else:
            a, b = PROGRESSION[game]
            process_game(game, resolved[a]["winner"], resolved[b]["winner"])
    process_game(104, resolved[101]["winner"], resolved[102]["winner"])
    # Recalcula 3º lugar depois que final já está ok; mantém jogo 103 como perdedores das semis.
    process_game(103, resolved[101]["loser"], resolved[102]["loser"])

    ordered_preds = pd.DataFrame([pred_rows[i] for i in sorted(pred_rows)])
    ordered_preds.to_csv(preds_path, index=False, encoding="utf-8-sig")
    infer_cols = ["jogo", "data", "fase", "equipe1", "equipe2", "placar_rede_neural", "vencedor_rede_neural"]
    infer = ordered_preds[infer_cols].rename(columns={"placar_rede_neural": "placar_rede_neural_puro", "vencedor_rede_neural": "vencedor_rede_neural_puro"})
    infer.to_csv(infer_path, index=False, encoding="utf-8-sig")

    matches_updated.to_csv(matches_path, index=False, encoding="utf-8-sig")
    make_js_data(root, matches_updated)

    debug = {
        "r32": {str(k): list(v) for k, v in r32.items()},
        "third_assignment": {str(k): v for k, v in third_assignment.items()},
        "best_thirds": best_thirds,
        "resolved_knockout": {str(k): v for k, v in resolved.items()},
    }
    (data_dir / "debug_chaveamento_rede_neural.json").write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")
    return ordered_preds


if __name__ == "__main__":
    rebuild_knockout_from_neural()
    print("Mata-mata revisado com encadeamento da rede neural.")
