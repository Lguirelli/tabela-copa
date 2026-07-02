#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valida se o repositório ficou sem estados de 'aguardando recálculo'.

Checagens:
- todos os jogos têm placar previsto e probabilidades do modelo diário;
- nenhum jogo fica com precisa_recalculo diferente de 'Não';
- jogos reais preservam placar real, mas também mantêm probabilidades recalculadas;
- confrontos futuros do chaveamento batem com vencedores reais/projetados dos jogos pais.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "data" / "modelo_diario" / "previsoes_dia_a_dia.csv"
OUT = ROOT / "VALIDACAO_RECALCULO_PROBABILIDADES_2026_06_30.json"

BRACKET_PARENTS = {
    89: (73, 75), 90: (74, 77), 93: (83, 84), 94: (81, 82),
    91: (76, 78), 92: (79, 80), 96: (85, 87), 95: (86, 88),
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (96, 95),
    101: (97, 98), 102: (99, 100), 104: (101, 102), 103: (101, 102),
}
BRACKET_ORDER = [89, 90, 93, 94, 91, 92, 96, 95, 97, 98, 99, 100, 101, 102, 104, 103]


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def same(a: object, b: object) -> bool:
    return clean_text(a).casefold() == clean_text(b).casefold()


def winner_for(row: pd.Series) -> str:
    if clean_text(row.get("possui_real", "")) == "Sim" and clean_text(row.get("vencedor_real", "")):
        return clean_text(row.get("vencedor_real"))
    if clean_text(row.get("vencedor_pos_penaltis", "")):
        return clean_text(row.get("vencedor_pos_penaltis"))
    return clean_text(row.get("vencedor_previsto", ""))


def loser_for(row: pd.Series) -> str:
    winner = winner_for(row)
    t1, t2 = clean_text(row.get("equipe1", "")), clean_text(row.get("equipe2", ""))
    if same(winner, t1):
        return t2
    if same(winner, t2):
        return t1
    return ""


def valid_prob(v: object) -> bool:
    try:
        f = float(v)
        return 0 <= f <= 1 and math.isfinite(f)
    except Exception:
        return False


def main() -> None:
    df = pd.read_csv(PRED, encoding="utf-8-sig")
    by_game = {int(r["jogo"]): r for _, r in df.iterrows()}

    missing_scores = []
    missing_probs = []
    recalc_flags = []
    bracket_mismatches = []
    real_without_model_probability = []

    for _, row in df.iterrows():
        game = int(row["jogo"])
        if not clean_text(row.get("placar_previsto", "")):
            missing_scores.append(game)
        probs = [row.get("prob_vitoria_equipe1"), row.get("prob_empate"), row.get("prob_vitoria_equipe2")]
        if not all(valid_prob(v) for v in probs):
            missing_probs.append(game)
        if clean_text(row.get("precisa_recalculo", "Não")) != "Não":
            recalc_flags.append(game)
        if clean_text(row.get("possui_real", "")) == "Sim" and not all(valid_prob(v) for v in probs):
            real_without_model_probability.append(game)

    for game in BRACKET_ORDER:
        row = by_game[game]
        p1, p2 = BRACKET_PARENTS[game]
        if game == 103:
            expected1 = loser_for(by_game[p1]) or f"Perdedor jogo {p1}"
            expected2 = loser_for(by_game[p2]) or f"Perdedor jogo {p2}"
        else:
            expected1 = winner_for(by_game[p1]) or f"Vencedor jogo {p1}"
            expected2 = winner_for(by_game[p2]) or f"Vencedor jogo {p2}"
        if not (same(row.get("equipe1"), expected1) and same(row.get("equipe2"), expected2)):
            bracket_mismatches.append({
                "jogo": game,
                "esperado": f"{expected1} x {expected2}",
                "encontrado": f"{row.get('equipe1')} x {row.get('equipe2')}",
            })

    result = {
        "status": "ok" if not any([missing_scores, missing_probs, recalc_flags, bracket_mismatches, real_without_model_probability]) else "erro",
        "jogos_total": int(len(df)),
        "jogos_reais": int((df["possui_real"].map(clean_text) == "Sim").sum()),
        "jogos_projetados": int((df["possui_real"].map(clean_text) != "Sim").sum()),
        "missing_scores": missing_scores,
        "missing_probs": missing_probs,
        "recalc_flags": recalc_flags,
        "real_without_model_probability": real_without_model_probability,
        "bracket_mismatches": bracket_mismatches,
        "observacao": "Resultado real preservado; probabilidades recalculadas e chaveamento propagado por vencedor real/projetado.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
