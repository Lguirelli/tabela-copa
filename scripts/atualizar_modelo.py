#!/usr/bin/env python3
"""
Atualiza resultados reais e treina novamente a rede neural da Copa.

Fluxo único atual:
1. Ler novas entradas em data/entrada/novos_resultados.csv, se existir.
2. Atualizar data/resultados_reais.csv e data/resultados.txt.
3. Recriar a rede neural em data/rede_neural/ e src/rede-neural-data.js.

Não usa previsões antigas, modelo auxiliar ou bases auxiliares antigas como fonte de previsão.
"""
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REAL_CSV = ROOT / "data" / "resultados_reais.csv"
NEW_CSV = ROOT / "data" / "entrada" / "novos_resultados.csv"
MATCHES_CSV = ROOT / "data" / "matches.csv"
OUT_TXT = ROOT / "data" / "resultados.txt"

ALIASES = {
    "republica da coreia": "coreia do sul", "coreia republica": "coreia do sul",
    "holanda": "paises baixos", "paises baixos": "paises baixos",
    "republica tcheca": "tchequia", "tchequia": "tchequia",
    "rd do congo": "rd congo", "rd congo": "rd congo", "congo kinshasa": "rd congo", "congo dr": "rd congo",
    "dr congo": "rd congo", "turkiye": "turquia", "eua": "estados unidos", "usa": "estados unidos",
    "ira": "ira", "iran": "ira", "ir iran": "ira"
}


def norm(value):
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return ALIASES.get(value, value)


def winner(team1, g1, team2, g2):
    if int(g1) > int(g2):
        return team1
    if int(g2) > int(g1):
        return team2
    return "Empate"


def read_csv(path, **kwargs):
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs) if path.exists() else pd.DataFrame()


def load_new_results(matches):
    if not NEW_CSV.exists() or NEW_CSV.stat().st_size < 10:
        return pd.DataFrame()
    new = pd.read_csv(NEW_CSV, sep=";", encoding="utf-8-sig")
    if new.empty:
        return pd.DataFrame()

    lookup = []
    for _, r in matches.iterrows():
        lookup.append({
            "jogo": int(r["jogo"]), "data": str(r.get("data", "")), "fase": r.get("fase", ""),
            "t1": r.get("equipe1", ""), "t2": r.get("equipe2", ""),
            "n1": norm(r.get("equipe1", "")), "n2": norm(r.get("equipe2", "")),
            "set": frozenset([norm(r.get("equipe1", "")), norm(r.get("equipe2", ""))])
        })

    rows = []
    for _, r in new.iterrows():
        t1_in = r.get("time_1", r.get("equipe1", ""))
        t2_in = r.get("time_2", r.get("equipe2", ""))
        if pd.isna(t1_in) or pd.isna(t2_in):
            continue
        date = str(r.get("data", ""))
        n1, n2 = norm(t1_in), norm(t2_in)
        candidates = [b for b in lookup if b["data"] == date and b["set"] == frozenset([n1, n2])]
        if not candidates:
            candidates = [b for b in lookup if b["set"] == frozenset([n1, n2])]
        if not candidates:
            print(f"Não encontrei jogo para: {t1_in} x {t2_in} em {date}")
            continue
        b = candidates[0]
        g1_in, g2_in = int(r.get("gols_time_1", r.get("gols1", 0))), int(r.get("gols_time_2", r.get("gols2", 0)))
        if n1 == b["n1"]:
            g1, g2 = g1_in, g2_in
        else:
            g1, g2 = g2_in, g1_in
        rows.append({
            "jogo": b["jogo"], "data": b["data"], "fase": b["fase"],
            "equipe1": b["t1"], "equipe2": b["t2"],
            "gols1_real": g1, "gols2_real": g2,
            "placar_real": f"{g1}-{g2}",
            "vencedor_real": winner(b["t1"], g1, b["t2"], g2),
            "status_real": "Finalizado", "fonte": r.get("fonte", ""), "placar_original": r.get("placar", "")
        })
    return pd.DataFrame(rows)


def write_results_txt(real_df):
    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    with OUT_TXT.open("w", encoding="utf-8") as f:
        f.write("jogo;status;placar;equipe1;equipe2;vencedor\n")
        for _, r in real_df.sort_values("jogo").iterrows():
            f.write(f"{int(r['jogo'])};Finalizado;{r['placar_real']};{r['equipe1']};{r['equipe2']};{r['vencedor_real']}\n")


def main():
    matches = read_csv(MATCHES_CSV)
    real_df = read_csv(REAL_CSV)
    new_df = load_new_results(matches)
    if not new_df.empty:
        real_df = pd.concat([real_df, new_df], ignore_index=True)
        real_df = real_df.sort_values("jogo").drop_duplicates("jogo", keep="last")
        real_df.to_csv(REAL_CSV, index=False, encoding="utf-8-sig")
        pd.DataFrame(columns=["data", "dia_semana", "fase", "time_1", "gols_time_1", "gols_time_2", "time_2", "placar", "status", "fonte"]).to_csv(NEW_CSV, index=False, sep=";", encoding="utf-8-sig")
        print(f"{len(new_df)} nova(s) entrada(s) processada(s).")
    else:
        print("Nenhuma nova entrada encontrada. Recalculando rede neural atual.")
    write_results_txt(real_df)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "treinar_rede_neural_copa.py")], check=True)
    print("Rede neural retreinada e visualizador atualizado.")


if __name__ == "__main__":
    main()
