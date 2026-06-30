#!/usr/bin/env python3
"""
Atualiza resultados reais, rede neural de referência e modelo diário ativo da Copa.

Fluxo atual:
1. Ler novas entradas em data/entrada/novos_resultados.csv, se existir.
2. Atualizar data/resultados_reais.csv, data/resultados.txt e campos reais do frontend.
3. Recriar a rede neural de referência em data/rede_neural/ e src/rede-neural-data.js.
4. Recalcular o modelo diário em data/modelo_diario/ e src/modelo-diario-data.js.
5. Recalcular o modelo diário lendo data/entrada/desempenho_manual.csv como única entrada manual de desempenho.
6. Recalcular a projeção completa do chaveamento, usando vencedor real quando houver e vencedor provável quando o resultado estiver vazio.
7. O front prioriza: placar real > modelo diário/projeção completa > rede neural pura.

O modelo diário não sobrescreve resultados reais. Jogos vazios são simulados para completar a tabela, e empates no mata-mata são decididos por pênaltis.
"""
from pathlib import Path
import json
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


def read_manual_input_csv(path):
    """Lê a entrada manual aceitando CSV separado por vírgula ou ponto e vírgula."""
    if not path.exists() or path.stat().st_size < 10:
        return pd.DataFrame()
    for kwargs in (
        {"sep": None, "engine": "python"},
        {"sep": ";"},
        {"sep": ","},
    ):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", **kwargs)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    return pd.DataFrame()


def load_new_results(matches):
    new = read_manual_input_csv(NEW_CSV)
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
        if pd.isna(t1_in) or pd.isna(t2_in) or not str(t1_in).strip() or not str(t2_in).strip():
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
            "vencedor_real": str(r.get("vencedor_penaltis_real", r.get("vencedor_real", ""))).strip() or winner(b["t1"], g1, b["t2"], g2),
            "status_real": "Finalizado", "fonte": r.get("fonte", ""), "placar_original": r.get("placar", ""),
            "placar_penaltis_real": r.get("placar_penaltis_real", ""), "vencedor_penaltis_real": r.get("vencedor_penaltis_real", "")
        })
    return pd.DataFrame(rows)




def validate_frontend_sync(real_df):
    """Garante que o CSV manual e os dados JS consumidos pelo site estão sincronizados."""
    frontend_js = ROOT / "src" / "rede-neural-data.js"
    if not frontend_js.exists():
        raise RuntimeError("src/rede-neural-data.js não foi gerado.")
    text = frontend_js.read_text(encoding="utf-8")
    match = re.search(r"window\.WC2026_REDE_NEURAL_PREVISOES = (.*?);\n", text, flags=re.S)
    if not match:
        raise RuntimeError("Não consegui localizar WC2026_REDE_NEURAL_PREVISOES em src/rede-neural-data.js.")
    previsoes = json.loads(match.group(1))
    real_games_csv = {int(j) for j in pd.to_numeric(real_df.get("jogo", pd.Series(dtype=int)), errors="coerce").dropna().astype(int)}
    real_games_js = {int(row["jogo"]) for row in previsoes if row.get("possui_real") == "Sim" and row.get("placar_real")}
    missing = sorted(real_games_csv - real_games_js)
    if missing:
        raise RuntimeError(
            "O frontend ainda não recebeu todos os resultados reais. "
            f"Jogos ausentes em src/rede-neural-data.js: {missing}"
        )
    print(f"Frontend sincronizado: {len(real_games_js)} resultado(s) real(is) disponíveis no visualizador.")

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
    subprocess.run([sys.executable, str(ROOT / "scripts" / "modelo_neural_diario.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "recalcular_chaveamento_completo.py")], check=True)
    real_df = read_csv(REAL_CSV)
    validate_frontend_sync(real_df)
    print("Rede neural de referência, modelo diário ativo, chaveamento completo e visualizador atualizados com entrada manual única.")


if __name__ == "__main__":
    main()
