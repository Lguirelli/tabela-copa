#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recalcula a tabela completa e o chaveamento projetado da Copa 2026.

Regra operacional:
- Resultado real nunca é sobrescrito.
- As probabilidades são recalculadas para TODOS os jogos a cada execução, inclusive jogos já finalizados.
- Em jogos finalizados, o placar real é preservado e a previsão recalculada fica como leitura do modelo pré-validação.
- Confrontos de fases futuras são derivados dos vencedores reais ou projetados.
- Em mata-mata, empate não pode avançar: o script decide por pênaltis.
- As variáveis de desempenho dentro da Copa entram via estado acumulado do modelo
  diário: rating dinâmico, momentum, memória de desempenho e entrada manual.

Entradas manuais versionadas:
- data/entrada/novos_resultados.csv
- data/entrada/desempenho_manual.csv
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.modelo_neural_diario import (  # noqa: E402
    DailyWorldCupModel,
    TeamState,
    safe_float,
    winner_name,
    opponent_quality_factor,
    goal_scored_multiplier,
    goal_conceded_damage_multiplier,
    defensive_gap_adjusted_signal,
    penalty_probability_from_features,
)

BRACKET_PARENTS = {
    89: (73, 75), 90: (74, 77), 93: (83, 84), 94: (81, 82),
    91: (76, 78), 92: (79, 80), 96: (85, 87), 95: (86, 88),
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (96, 95),
    101: (97, 98), 102: (99, 100), 104: (101, 102), 103: (101, 102),
}

BRACKET_ORDER = [
    89, 90, 93, 94, 91, 92, 96, 95,
    97, 98, 99, 100,
    101, 102,
    104, 103,
]

KNOCKOUT_PHASES = {
    "16 avos de final", "Oitavas de final", "Quartas de final",
    "Semifinais", "Disputa de 3º lugar", "Final",
}


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def is_knockout(phase: object) -> bool:
    return str(phase or "").strip() in KNOCKOUT_PHASES


def parse_score(score: object) -> Optional[Tuple[int, int]]:
    m = re.match(r"^\s*(\d+)\s*(?:-|x|:)\s*(\d+)\s*$", str(score or ""), flags=re.I)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-max(-8.0, min(8.0, x))))


def decide_penalties(match: pd.Series, pred: dict) -> Tuple[str, str, float]:
    """Decisão determinística por pênaltis para não deixar Empate em mata-mata."""
    team1, team2 = str(match["equipe1"]), str(match["equipe2"])
    f = {
        "rating_diff": safe_float(pred.get("feature_rating_diff", 0), 0),
        "goalkeeper_diff": safe_float(pred.get("feature_goalkeeper_diff", 0), 0),
        "experience_diff": safe_float(pred.get("feature_experience_diff", 0), 0),
        "momentum_diff": safe_float(pred.get("feature_momentum_diff", 0), 0),
        "performance_memory_diff": safe_float(pred.get("feature_performance_memory_diff", 0), 0),
        "schedule_strength_diff": safe_float(pred.get("feature_schedule_strength_diff", 0), 0),
    }
    # Usa a mesma lógica do modelo diário: pênaltis dependem mais de goleiro,
    # experiência, momentum e força do caminho do que de volume ofensivo em 90 minutos.
    p_team1 = safe_float(pred.get("prob_penaltis_equipe1_modelo", ""), None)
    if p_team1 is None:
        p_team1 = penalty_probability_from_features(f)
    winner = team1 if p_team1 >= 0.50 else team2

    # Placar sintético de pênaltis, sem aleatoriedade, mas variando por jogo/probabilidade.
    game = int(match["jogo"])
    close = abs(p_team1 - 0.5) < 0.07
    if winner == team1:
        pen = "5-4" if close or game % 3 == 0 else "4-3"
    else:
        pen = "4-5" if close or game % 3 == 0 else "3-4"
    return winner, pen, p_team1


def projected_update(model: DailyWorldCupModel, match: pd.Series, pred: dict) -> None:
    """Atualiza estado para a projeção da fase seguinte sem treinar o modelo com simulação."""
    t1, t2 = str(match["equipe1"]), str(match["equipe2"])
    g1 = int(pred.get("gols1_previsto", 0) or 0)
    g2 = int(pred.get("gols2_previsto", 0) or 0)
    penalty_winner = str(pred.get("vencedor_pos_penaltis", "") or "")

    s1 = model.states.setdefault(t1, TeamState(t1, 60.0, 60.0))
    s2 = model.states.setdefault(t2, TeamState(t2, 60.0, 60.0))

    xg1, xg2 = safe_float(pred.get("xg1_modelo", 1.1), 1.1), safe_float(pred.get("xg2_modelo", 1.1), 1.1)
    expected_margin = xg1 - xg2
    projected_margin = g1 - g2
    knockout = is_knockout(match.get("fase", ""))

    if g1 > g2:
        result_points1, result_points2 = 3, 0
        winner_boost = 0.0
    elif g2 > g1:
        result_points1, result_points2 = 0, 3
        winner_boost = 0.0
    else:
        if knockout and penalty_winner:
            result_points1 = 2 if penalty_winner == t1 else 1
            result_points2 = 2 if penalty_winner == t2 else 1
            winner_boost = 0.18 if penalty_winner == t1 else -0.18
        else:
            result_points1 = result_points2 = 1
            winner_boost = 0.0

    # Projeção tem peso menor que resultado real para não exagerar caminho futuro.
    # Gols marcados e sofridos são separados também na simulação, mas com atualização fraca.
    rating1_pre, rating2_pre = float(s1.rating_dynamic), float(s2.rating_dynamic)
    opp_attack_t1 = safe_float(model.team_row(t1).get("ataque_score", 5.5), 5.5)
    opp_attack_t2 = safe_float(model.team_row(t2).get("ataque_score", 5.5), 5.5)
    opp_quality_for_t1 = opponent_quality_factor(rating2_pre, opp_attack_t2)
    opp_quality_for_t2 = opponent_quality_factor(rating1_pre, opp_attack_t1)
    opp_factor_for_t1 = goal_scored_multiplier(opp_quality_for_t1)
    opp_factor_for_t2 = goal_scored_multiplier(opp_quality_for_t2)
    ga_penalty_t1 = goal_conceded_damage_multiplier(opp_quality_for_t1)
    ga_penalty_t2 = goal_conceded_damage_multiplier(opp_quality_for_t2)

    offense_signal1 = float(np.clip((g1 - xg1) * opp_factor_for_t1, -1.6, 1.6))
    offense_signal2 = float(np.clip((g2 - xg2) * opp_factor_for_t2, -1.6, 1.6))
    defense_signal1 = float(np.clip(defensive_gap_adjusted_signal(xg2 - g2, opp_quality_for_t1), -1.6, 1.6))
    defense_signal2 = float(np.clip(defensive_gap_adjusted_signal(xg1 - g1, opp_quality_for_t2), -1.6, 1.6))

    # Pênaltis não devem gerar salto grande de rating: classificação nos pênaltis é baixa confiança.
    penalty_boost = winner_boost * 0.42
    update1 = float(np.clip(0.16 * (projected_margin - expected_margin) + 0.08 * offense_signal1 + 0.08 * defense_signal1 + penalty_boost, -0.75, 0.75))
    update2 = float(np.clip(-0.16 * (projected_margin - expected_margin) + 0.08 * offense_signal2 + 0.08 * defense_signal2 - penalty_boost, -0.75, 0.75))
    s1.rating_dynamic = float(np.clip(s1.rating_dynamic + update1, 25, 95))
    s2.rating_dynamic = float(np.clip(s2.rating_dynamic + update2, 25, 95))

    s1.momentum = float(np.clip(s1.momentum * 0.70 + (result_points1 - 1) * 0.18 + update1 * 0.18, -2.5, 2.5))
    s2.momentum = float(np.clip(s2.momentum * 0.70 + (result_points2 - 1) * 0.18 + update2 * 0.18, -2.5, 2.5))
    s1.performance_memory = float(np.clip(s1.performance_memory * 0.78 + (update1 + offense_signal1 + defense_signal1) * 0.025, -2.0, 2.0))
    s2.performance_memory = float(np.clip(s2.performance_memory * 0.78 + (update2 + offense_signal2 + defense_signal2) * 0.025, -2.0, 2.0))
    s1.offensive_form = float(np.clip(s1.offensive_form * 0.78 + offense_signal1 * 0.12, -2.4, 2.4))
    s2.offensive_form = float(np.clip(s2.offensive_form * 0.78 + offense_signal2 * 0.12, -2.4, 2.4))
    s1.defensive_form = float(np.clip(s1.defensive_form * 0.78 + defense_signal1 * 0.12, -2.4, 2.4))
    s2.defensive_form = float(np.clip(s2.defensive_form * 0.78 + defense_signal2 * 0.12, -2.4, 2.4))

    for st, opp_rating in [(s1, rating2_pre), (s2, rating1_pre)]:
        st.last_match_date = match.get("data_dt")
        # Gols/pontos projetados não entram como jogo validado real.
        # A força média de adversários projetados entra só como contexto fraco para a sequência.
        st.schedule_strength = float(np.clip(st.schedule_strength * 0.92 + opp_rating * 0.08, 42, 90))


def row_to_real_series(real_row: pd.Series) -> pd.Series:
    return real_row


def update_match_row(match: pd.Series, team1: str, team2: str, real: Optional[pd.Series], pred: dict) -> pd.Series:
    m = match.copy()
    m["equipe1"] = team1
    m["equipe2"] = team2
    m["confronto"] = f"{team1} x {team2}"
    if real is not None:
        m["status"] = "Finalizado"
        m["placar_real"] = str(real.get("placar_real", ""))
        m["vencedor_real"] = str(real.get("vencedor_real", ""))
        m["gols1_real"] = int(real.get("gols1_real", 0))
        m["gols2_real"] = int(real.get("gols2_real", 0))
        m["status_real"] = "Finalizado"
        m["fonte"] = str(real.get("fonte", ""))
        m["placar_original"] = str(real.get("placar_original", ""))
    else:
        m["status"] = "Modelo diário"
        for col in ["placar_real", "vencedor_real", "gols1_real", "gols2_real", "status_real", "fonte", "placar_original"]:
            if col in m.index:
                m[col] = ""
    return m


def build_data_js(root: Path, matches_front: pd.DataFrame) -> None:
    data_js = root / "src" / "data.js"
    text = data_js.read_text(encoding="utf-8")
    match = re.search(r"window\.WC2026_DATA = (.*);\s*$", text, flags=re.S)
    if not match:
        raise RuntimeError("Não consegui ler WC2026_DATA em src/data.js")
    obj = json.loads(match.group(1))
    records = matches_front.replace({np.nan: None}).to_dict(orient="records")
    # json não aceita np.int64/float nan
    def clean(v):
        if isinstance(v, (pd.Timestamp,)):
            if pd.isna(v):
                return None
            return str(v.date())
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            if np.isnan(v):
                return None
            return float(v)
        if pd.isna(v) if not isinstance(v, (list, dict, tuple, str, bytes)) else False:
            return None
        return v
    records = [{k: clean(v) for k, v in row.items()} for row in records]
    obj["matches"] = records
    obj["summary"]["resultadosReais"] = int((matches_front.get("status_real", pd.Series(dtype=str)) == "Finalizado").sum())
    obj["summary"]["simulados"] = int(len(matches_front) - obj["summary"]["resultadosReais"])
    data_js.write_text("window.WC2026_DATA = " + json.dumps(obj, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


def export_modelo_diario_js(root: Path, pred_df: pd.DataFrame, val_df: pd.DataFrame, state_df: pd.DataFrame, metrics: dict) -> None:
    day_df = read_csv(root / "data/modelo_diario/resumo_diario_validacao.csv")
    if day_df.empty:
        day_df = pd.DataFrame(columns=["data", "jogos_previstos", "jogos_validados"])
    js = "window.WC2026_MODELO_DIARIO_PREVISOES = " + json.dumps(pred_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
    js += "window.WC2026_MODELO_DIARIO_VALIDACAO = " + json.dumps(val_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
    js += "window.WC2026_MODELO_DIARIO_ESTADO_TIMES = " + json.dumps(state_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
    js += "window.WC2026_MODELO_DIARIO_RESUMO = " + json.dumps(day_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
    js += "window.WC2026_MODELO_DIARIO_METRICAS = " + json.dumps(metrics, ensure_ascii=False) + ";\n"
    (root / "src/modelo-diario-data.js").write_text(js, encoding="utf-8")


def main() -> None:
    model = DailyWorldCupModel(ROOT, simulations=12000, neural_min_samples=16)
    model.load()

    original_matches = model.matches.copy().sort_values("jogo").reset_index(drop=True)
    real_by_game: Dict[int, pd.Series] = {int(r["jogo"]): r for _, r in model.real_results.iterrows()}
    match_by_game: Dict[int, pd.Series] = {int(r["jogo"]): r.copy() for _, r in original_matches.iterrows()}

    winners: Dict[int, str] = {}
    losers: Dict[int, str] = {}
    predictions = []
    validations = []
    projected_matches = []

    for game in sorted(match_by_game):
        match = match_by_game[game].copy()

        if game in BRACKET_PARENTS:
            p1, p2 = BRACKET_PARENTS[game]
            if game == 103:  # disputa de 3º lugar pega perdedores das semis
                team1 = losers.get(p1, f"Perdedor jogo {p1}")
                team2 = losers.get(p2, f"Perdedor jogo {p2}")
            else:
                team1 = winners.get(p1, f"Vencedor jogo {p1}")
                team2 = winners.get(p2, f"Vencedor jogo {p2}")
            match["equipe1"] = team1
            match["equipe2"] = team2
            match["confronto"] = f"{team1} x {team2}"

        pred = model.predict_match(match)
        pred["placar_regular_previsto"] = pred["placar_previsto"]
        pred["decisao_penaltis"] = "Não"
        pred["placar_penaltis"] = ""
        pred["prob_penaltis_equipe1"] = ""
        pred["vencedor_pos_penaltis"] = ""
        pred["criterio_vencedor"] = "Tempo regulamentar/modelado"
        pred["status_previsao"] = "Projetado"
        pred["fonte_previsao"] = "Modelo diário recalibrado"
        pred["usa_desempenho_copa"] = "Sim"
        pred["origem_confronto"] = "Derivado do chaveamento" if game in BRACKET_PARENTS else "Tabela base"
        pred["precisa_recalculo"] = "Não"

        real_row = real_by_game.get(game)
        score = parse_score(pred.get("placar_previsto"))
        if real_row is not None:
            pred["possui_real"] = "Sim"
            pred["placar_real"] = str(real_row.get("placar_real", ""))
            pred["vencedor_real"] = str(real_row.get("vencedor_real", ""))
            pred["status_previsao"] = "Real validado"
            # Em jogo real de mata-mata, usa vencedor real. Se no futuro houver empate real, exigir campo manual de pênaltis.
            winner = str(real_row.get("vencedor_real", ""))
            if winner == "Empate" and is_knockout(match.get("fase")):
                winner = str(pred.get("vencedor_previsto", ""))
            val = model.validate_and_update(match, pred, real_row)
            validations.append(val)
        else:
            pred["possui_real"] = "Não"
            pred["placar_real"] = ""
            pred["vencedor_real"] = ""
            if is_knockout(match.get("fase")):
                class_winner = str(pred.get("vencedor_classificacao_previsto", "") or pred.get("vencedor_previsto", ""))
                pred["criterio_vencedor"] = "Classificação modelada"
                if score and score[0] == score[1]:
                    pen_winner, pen_score, p_team1 = decide_penalties(match, pred)
                    pred["decisao_penaltis"] = "Sim"
                    pred["placar_penaltis"] = pen_score
                    pred["prob_penaltis_equipe1"] = round(p_team1, 4)
                    pred["vencedor_pos_penaltis"] = pen_winner
                    pred["criterio_vencedor"] = "Pênaltis"
                    pred["vencedor_previsto"] = pen_winner
                    winner = pen_winner
                else:
                    pred["vencedor_previsto"] = class_winner
                    winner = class_winner
            else:
                winner = str(pred.get("vencedor_previsto", ""))
            projected_update(model, match, pred)

        # Resolve vencedor/perdedor para próximas fases. Em fase de grupos, empate continua empate.
        if is_knockout(match.get("fase")) and (not winner or winner == "Empate"):
            # Segurança: em mata-mata nunca deixa sem classificado.
            pen_winner, pen_score, p_team1 = decide_penalties(match, pred)
            pred["decisao_penaltis"] = "Sim"
            pred["placar_penaltis"] = pen_score
            pred["prob_penaltis_equipe1"] = round(p_team1, 4)
            pred["vencedor_pos_penaltis"] = pen_winner
            pred["criterio_vencedor"] = "Pênaltis"
            pred["vencedor_previsto"] = pen_winner
            winner = pen_winner

        team1, team2 = str(match["equipe1"]), str(match["equipe2"])
        if winner == team1:
            loser = team2
        elif winner == team2:
            loser = team1
        else:
            loser = ""
        winners[game] = winner
        losers[game] = loser
        predictions.append(pred)
        projected_matches.append(update_match_row(match, team1, team2, real_row, pred))

    pred_df = pd.DataFrame(predictions).sort_values("jogo")
    val_df = pd.DataFrame(validations).sort_values("jogo") if validations else pd.DataFrame()

    state_rows = []
    for team, st in sorted(model.states.items(), key=lambda kv: kv[1].rating_dynamic, reverse=True):
        state_rows.append({
            "selecao": team,
            "rating_inicial_0_100": round(st.rating_base, 3),
            "rating_atual_0_100": round(st.rating_dynamic, 3),
            "ajuste_total_rating": round(st.rating_dynamic - st.rating_base, 3),
            "momentum_resultado_anterior": round(st.momentum, 3),
            "memoria_desempenho": round(st.performance_memory, 3),
            "forma_ofensiva": round(st.offensive_form, 3),
            "forma_defensiva": round(st.defensive_form, 3),
            "forca_media_adversarios": round(st.schedule_strength, 3),
            "pontos_ajustados_por_adversario": round(st.opponent_adjusted_points, 3),
            "gols_marcados_ajustados_por_adversario": round(st.opponent_weighted_goals_for, 3),
            "gols_sofridos_ajustados_por_adversario": round(st.opponent_weighted_goals_against, 3),
            "gols_marcados_ajustados_por_jogo": round(st.opponent_weighted_goals_for / max(1, st.games_validated), 3),
            "gols_sofridos_ajustados_por_jogo": round(st.opponent_weighted_goals_against / max(1, st.games_validated), 3),
            "jogos_validados": st.games_validated,
            "gols_pro": st.goals_for,
            "gols_contra": st.goals_against,
            "saldo": st.goals_for - st.goals_against,
            "pontos": st.points,
            "ultima_data_validada": str(st.last_match_date.date()) if st.last_match_date is not None and pd.notna(st.last_match_date) else "",
        })
    state_df = pd.DataFrame(state_rows)

    real_count = int((pred_df["possui_real"] == "Sim").sum())
    pen_count = int((pred_df["decisao_penaltis"] == "Sim").sum())
    metrics = {
        "modelo": "modelo diário incremental + projeção completa de chaveamento",
        "modelo_ativo": "Modelo diário incremental com desempenho da Copa",
        "usa_desempenho_copa": True,
        "usa_placar_real_quando_disponivel": True,
        "sobrescreve_resultado_real": False,
        "recalcula_apenas_jogos_sem_resultado_real": False,
        "recalcula_probabilidades_todos_jogos": True,
        "preserva_placar_real_e_recalcula_probabilidades": True,
        "propaga_vencedor_real_no_chaveamento": True,
        "simula_chaveamento_completo": True,
        "inclui_decisao_por_penaltis": True,
        "jogos_previstos": int(len(pred_df)),
        "jogos_com_placar_real_validado": real_count,
        "jogos_projetados": int(len(pred_df) - real_count),
        "jogos_decididos_por_penaltis_na_projecao": pen_count,
        "interacoes_monte_carlo": int(pred_df.get("interacoes_monte_carlo", pd.Series([0])).max()),
        "ultima_entrada_real": str(model.real_results["data"].max()) if not model.real_results.empty else "",
        "fonte_desempenho_manual": "data/entrada/desempenho_manual.csv",
        "fonte_resultados_manuais": "data/entrada/novos_resultados.csv",
        "observacao": "Resultados reais são preservados, mas as probabilidades e o placar previsto são recalculados em toda execução. Jogos reais atualizam o estado de desempenho e propagam vencedores reais no chaveamento; jogos sem real são projetados a partir desse estado atualizado. Gols marcados, gols sofridos e peso dos adversários são avaliados separadamente; força do caminho pesa mais no mata-mata; probabilidades de classificação são calculadas separadamente das probabilidades em 90 minutos.",
        "probabilidade_classificacao_mata_mata": True,
        "recalibracao_forca_caminho": True,
        "gols_separados": True,
        "usa_peso_adversario": True,
        "gols_sofridos_ajustados_por_forca_adversario": True,
        "rede_neural_peso_maximo": 0.035,
    }
    if not val_df.empty:
        metrics.update({
            "acuracia_vencedor_percentual": round(float((val_df["acertou_vencedor"] == "Sim").mean() * 100), 2),
            "placar_exato_percentual": round(float((val_df["acertou_placar_exato"] == "Sim").mean() * 100), 2),
            "erro_medio_total_gols": round(float(val_df["erro_total_gols"].mean()), 3),
            "proximidade_media_0_100": round(float(val_df["proximidade_0_100"].mean()), 2),
        })

    out_dir = ROOT / "data" / "modelo_diario"
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_df.to_csv(out_dir / "previsoes_dia_a_dia.csv", index=False, encoding="utf-8-sig")
    pred_df.to_csv(out_dir / "projecao_chaveamento_completa.csv", index=False, encoding="utf-8-sig")
    val_df.to_csv(out_dir / "validacao_dia_a_dia.csv", index=False, encoding="utf-8-sig")
    state_df.to_csv(out_dir / "estado_times_dia_a_dia.csv", index=False, encoding="utf-8-sig")
    with (out_dir / "metricas_modelo.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # Atualiza matches com confrontos projetados da fase futura, preservando reais.
    matches_front = pd.DataFrame(projected_matches).sort_values("jogo")
    # Mantém as colunas originais primeiro, e campos de real no fim quando existirem.
    base_cols = list(read_csv(ROOT / "data/matches.csv").columns)
    extra_cols = [c for c in ["placar_real", "vencedor_real", "gols1_real", "gols2_real", "status_real", "fonte", "placar_original"] if c in matches_front.columns]
    matches_csv = matches_front[[c for c in base_cols if c in matches_front.columns]].copy()
    matches_csv.to_csv(ROOT / "data/matches.csv", index=False, encoding="utf-8-sig")
    matches_csv.to_csv(ROOT / "data/database/matches.csv", index=False, encoding="utf-8-sig")
    matches_front.to_json(ROOT / "data/matches.json", orient="records", force_ascii=False, indent=2)
    build_data_js(ROOT, matches_front)
    export_modelo_diario_js(ROOT, pred_df, val_df, state_df, metrics)

    readme = out_dir / "README_PROJECAO_CHAVEAMENTO.md"
    readme.write_text(
        "# Projeção completa do chaveamento\n\n"
        "- Resultado real é prioridade e nunca é sobrescrito.\n"
        "- As probabilidades são recalculadas para todos os jogos a cada execução, inclusive os já finalizados.\n"
        "- Jogos finalizados preservam o placar real, mas atualizam a leitura do modelo e alimentam o estado de desempenho.\n"
        "- O classificado real ou projetado alimenta a próxima fase para manter a tabela completa.\n"
        "- Em mata-mata, placar empatado gera decisão por pênaltis e vencedor projetado.\n"
        "- Variáveis de desempenho da Copa entram via rating dinâmico, forma ofensiva, forma defensiva, força dos adversários, momentum, memória de desempenho e `data/entrada/desempenho_manual.csv`.\n\n"
        f"Jogos reais preservados: {real_count}\n\n"
        f"Jogos projetados: {len(pred_df) - real_count}\n\n"
        f"Decisões por pênaltis na projeção: {pen_count}\n",
        encoding="utf-8",
    )
    print(f"Chaveamento completo recalculado: {len(pred_df)} jogos, {real_count} reais, {pen_count} pênaltis projetados.")


if __name__ == "__main__":
    main()
