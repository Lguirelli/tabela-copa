#!/usr/bin/env python3
"""
Valida integridade mínima dos dados gerados/consumidos pelo frontend.

Este script é propositalmente executável sem pytest para rodar direto no
GitHub Actions e localmente:

    python scripts/testes/test_integridade_dados.py

Ele não substitui scripts/validar_recalculo_probabilidades.py; complementa
checando sincronização entre CSV, JSON e JS, duplicidades, NaN residual e
probabilidades inválidas.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MATCHES = 104
TOL = 0.015

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def read_csv(path: str | Path) -> pd.DataFrame:
    path = ROOT / path if not isinstance(path, Path) or not path.is_absolute() else path
    if not path.exists():
        fail(f"Arquivo ausente: {path.relative_to(ROOT)}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:  # pragma: no cover - mensagem para CI
        fail(f"Falha ao ler CSV {path.relative_to(ROOT)}: {exc}")
        return pd.DataFrame()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def read_json(path: str | Path) -> Any:
    path = ROOT / path if not isinstance(path, Path) or not path.is_absolute() else path
    if not path.exists():
        fail(f"Arquivo ausente: {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        fail(f"Falha ao ler JSON {path.relative_to(ROOT)}: {exc}")
        return None


def extract_js_assignment(path: str | Path, variable: str) -> Any:
    path = ROOT / path if not isinstance(path, Path) or not path.is_absolute() else path
    if not path.exists():
        fail(f"Arquivo JS ausente: {path.relative_to(ROOT)}")
        return None
    text = path.read_text(encoding="utf-8-sig")
    pattern = rf"window\.{re.escape(variable)}\s*=\s*(.*?);\s*(?:\n|$)"
    match = re.search(pattern, text, flags=re.S)
    if not match:
        fail(f"Variável window.{variable} não encontrada em {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(match.group(1))
    except Exception as exc:
        fail(f"JSON inválido em window.{variable} de {path.relative_to(ROOT)}: {exc}")
        return None


def require_unique_ids(df: pd.DataFrame, path: str, column: str = "jogo", expected: int | None = None) -> None:
    if df.empty or column not in df.columns:
        fail(f"{path}: coluna obrigatória ausente: {column}")
        return
    ids = pd.to_numeric(df[column], errors="coerce")
    if ids.isna().any():
        fail(f"{path}: existem IDs de jogo vazios ou não numéricos")
        return
    ids_int = ids.astype(int)
    duplicated = sorted(ids_int[ids_int.duplicated()].unique().tolist())
    if duplicated:
        fail(f"{path}: IDs duplicados em {column}: {duplicated[:20]}")
    if expected is not None and len(df) != expected:
        fail(f"{path}: esperado {expected} jogos, encontrado {len(df)}")
    if expected == EXPECTED_MATCHES:
        missing = sorted(set(range(1, EXPECTED_MATCHES + 1)) - set(ids_int.tolist()))
        extra = sorted(set(ids_int.tolist()) - set(range(1, EXPECTED_MATCHES + 1)))
        if missing:
            fail(f"{path}: jogos ausentes: {missing[:30]}")
        if extra:
            fail(f"{path}: jogos fora do intervalo 1-{EXPECTED_MATCHES}: {extra[:30]}")


def compare_file_bytes(path_a: str, path_b: str, label: str) -> None:
    a, b = ROOT / path_a, ROOT / path_b
    if not a.exists() or not b.exists():
        return
    if a.read_bytes() != b.read_bytes():
        fail(f"{label}: {path_a} e {path_b} divergiram; enquanto ambos existirem, precisam estar sincronizados")


def validate_generated_text_tokens() -> None:
    # Não varre todo o JS de código porque 'undefined' é legítimo em lógica de fallback.
    generated_files = [
        "data/matches.json",
        "src/data.js",
        "src/modelo-diario-data.js",
        "src/rede-neural-data.js",
        "data/modelo_diario/validacao_dia_a_dia.csv",
        "data/modelo_diario/previsoes_dia_a_dia.csv",
        "data/modelo_diario/projecao_chaveamento_completa.csv",
    ]
    patterns = [
        (re.compile(r"\(pên\.\s*(?:nan|NaN|None|null)\)", re.I), "sufixo de pênaltis inválido"),
        (re.compile(r"\bNaN\b"), "literal NaN"),
        (re.compile(r"\bNone\b"), "literal None"),
    ]
    for rel in generated_files:
        path = ROOT / rel
        if not path.exists():
            fail(f"Arquivo gerado ausente: {rel}")
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for rx, desc in patterns:
            if rx.search(text):
                fail(f"{rel}: contém {desc}")


def validate_matches_and_frontend() -> None:
    matches = read_csv("data/matches.csv")
    database_matches = read_csv("data/database/matches.csv")
    matches_json = read_json("data/matches.json")
    wc_data = extract_js_assignment("src/data.js", "WC2026_DATA")

    require_unique_ids(matches, "data/matches.csv", expected=EXPECTED_MATCHES)
    require_unique_ids(database_matches, "data/database/matches.csv", expected=EXPECTED_MATCHES)
    compare_file_bytes("data/matches.csv", "data/database/matches.csv", "Calendário duplicado")

    if isinstance(matches_json, list):
        if len(matches_json) != EXPECTED_MATCHES:
            fail(f"data/matches.json: esperado {EXPECTED_MATCHES} jogos, encontrado {len(matches_json)}")
        ids_json = [int(item.get("jogo")) for item in matches_json if str(item.get("jogo", "")).isdigit()]
        if sorted(ids_json) != list(range(1, EXPECTED_MATCHES + 1)):
            fail("data/matches.json: IDs de jogo não correspondem exatamente a 1..104")
    elif matches_json is not None:
        fail("data/matches.json: esperado array/lista de jogos")

    if isinstance(wc_data, dict):
        frontend_matches = wc_data.get("matches", [])
        if len(frontend_matches) != EXPECTED_MATCHES:
            fail(f"src/data.js: WC2026_DATA.matches deveria ter {EXPECTED_MATCHES} jogos, encontrou {len(frontend_matches)}")
        if wc_data.get("summary", {}).get("totalJogos") != EXPECTED_MATCHES:
            fail("src/data.js: summary.totalJogos diferente de 104")
        frontend_by_id = {int(item["jogo"]): item for item in frontend_matches if str(item.get("jogo", "")).isdigit()}
        for _, row in matches.iterrows():
            jogo = int(row["jogo"])
            front = frontend_by_id.get(jogo)
            if not front:
                fail(f"src/data.js: jogo {jogo} ausente em WC2026_DATA.matches")
                continue
            for col in ["data", "fase", "equipe1", "equipe2", "status"]:
                csv_value = normalize_text(row.get(col, ""))
                js_value = normalize_text(front.get(col, ""))
                if csv_value != js_value:
                    fail(f"src/data.js: jogo {jogo} divergente em {col}: CSV={csv_value!r}, JS={js_value!r}")


def validate_results_sync() -> None:
    resultados = read_csv("data/resultados.csv")
    reais = read_csv("data/resultados_reais.csv")
    require_unique_ids(resultados, "data/resultados.csv")
    require_unique_ids(reais, "data/resultados_reais.csv")
    compare_file_bytes("data/resultados.csv", "data/resultados_reais.csv", "Resultados reais duplicados")

    if not reais.empty:
        required = {"jogo", "gols1_real", "gols2_real", "placar_real", "vencedor_real", "status_real"}
        missing_cols = required - set(reais.columns)
        if missing_cols:
            fail(f"data/resultados_reais.csv: colunas ausentes: {sorted(missing_cols)}")
        finalized = reais[reais.get("status_real", "").astype(str).str.strip().eq("Finalizado")]
        if len(finalized) != len(reais):
            warn("data/resultados_reais.csv: há linhas sem status_real=Finalizado")
        for _, row in reais.iterrows():
            jogo = int(row["jogo"])
            g1 = row.get("gols1_real")
            g2 = row.get("gols2_real")
            expected_score = f"{int(g1)}-{int(g2)}" if not pd.isna(g1) and not pd.isna(g2) else ""
            if expected_score and normalize_text(row.get("placar_real")) != expected_score:
                fail(f"data/resultados_reais.csv: jogo {jogo} tem placar_real divergente de gols1/gols2")


def validate_model_outputs() -> None:
    previsoes = read_csv("data/modelo_diario/previsoes_dia_a_dia.csv")
    chaveamento = read_csv("data/modelo_diario/projecao_chaveamento_completa.csv")
    rede = read_csv("data/rede_neural/previsoes_rede_neural.csv")
    require_unique_ids(previsoes, "data/modelo_diario/previsoes_dia_a_dia.csv", expected=EXPECTED_MATCHES)
    require_unique_ids(chaveamento, "data/modelo_diario/projecao_chaveamento_completa.csv", expected=EXPECTED_MATCHES)
    require_unique_ids(rede, "data/rede_neural/previsoes_rede_neural.csv", expected=EXPECTED_MATCHES)

    for path, df in [
        ("data/modelo_diario/previsoes_dia_a_dia.csv", previsoes),
        ("data/modelo_diario/projecao_chaveamento_completa.csv", chaveamento),
    ]:
        if df.empty:
            continue
        for col in ["prob_vitoria_equipe1", "prob_empate", "prob_vitoria_equipe2"]:
            if col not in df.columns:
                fail(f"{path}: coluna de probabilidade ausente: {col}")
                continue
            values = pd.to_numeric(df[col], errors="coerce")
            invalid = df[values.isna() | (values < 0) | (values > 1)]
            if not invalid.empty:
                fail(f"{path}: {col} possui valores fora de 0..1 ou vazios nos jogos {invalid['jogo'].head(20).tolist()}")
        if {"prob_vitoria_equipe1", "prob_empate", "prob_vitoria_equipe2"}.issubset(df.columns):
            sums = (
                pd.to_numeric(df["prob_vitoria_equipe1"], errors="coerce")
                + pd.to_numeric(df["prob_empate"], errors="coerce")
                + pd.to_numeric(df["prob_vitoria_equipe2"], errors="coerce")
            )
            bad = df[(sums - 1).abs() > TOL]
            if not bad.empty:
                fail(f"{path}: soma de probabilidades inválida nos jogos {bad['jogo'].head(20).tolist()}")
        if "precisa_recalculo" in df.columns:
            recalc = df[df["precisa_recalculo"].astype(str).str.strip().str.lower().isin({"sim", "true", "1"})]
            if not recalc.empty:
                fail(f"{path}: jogos ainda marcados como precisa_recalculo: {recalc['jogo'].tolist()}")
        # Se o confronto já tem data passada/finalizada no arquivo base, não deve carregar placeholders.
        for team_col in ["equipe1", "equipe2"]:
            placeholders = df[df[team_col].astype(str).str.contains(r"Vencedor jogo|Perdedor jogo", case=False, na=False)]
            if not placeholders.empty:
                warn(f"{path}: ainda existem placeholders em {team_col}: jogos {placeholders['jogo'].head(20).tolist()}")

    modelo_js = extract_js_assignment("src/modelo-diario-data.js", "WC2026_MODELO_DIARIO_PREVISOES")
    rede_js = extract_js_assignment("src/rede-neural-data.js", "WC2026_REDE_NEURAL_PREVISOES")
    if isinstance(modelo_js, list) and len(modelo_js) != EXPECTED_MATCHES:
        fail(f"src/modelo-diario-data.js: previsões deveriam ter {EXPECTED_MATCHES} jogos, encontrou {len(modelo_js)}")
    if isinstance(rede_js, list) and len(rede_js) != EXPECTED_MATCHES:
        fail(f"src/rede-neural-data.js: previsões deveriam ter {EXPECTED_MATCHES} jogos, encontrou {len(rede_js)}")


def validate_legacy_orphans_removed() -> None:
    """Garante que arquivos legados removidos no Patch 2 não voltem em recálculos futuros."""
    legacy_paths = [
        "src/analysis.js",
        "src/app.js",
        "src/results.js",
        "src/model-data.js",
        "src/modelo-dados.js",
        "scripts/recalcular_mata_mata.py",
        "scripts/recalcular_modelo_contextual.py",
        "data/previsoes_modelo.csv",
        "data/database/simulated_matches.csv",
        "data/database/simulated_referee_assignments.csv",
        "data/atualizacoes_entrada_26-06.csv",
        "data/atualizacoes_entrada_26-06_resultados_desempenho.csv",
        "data/neural",
        "data/modelo",
    ]
    for rel in legacy_paths:
        if (ROOT / rel).exists():
            fail(f"Arquivo/pasta legado reapareceu após limpeza do Patch 2: {rel}")
    pycache = [p for p in (ROOT).rglob("__pycache__") if p.is_dir()]
    pyc = [p for p in (ROOT).rglob("*.pyc") if p.is_file()]
    if pycache or pyc:
        fail("Artefatos Python locais não devem ser versionados: " + ", ".join(str(x.relative_to(ROOT)) for x in (pycache + pyc)[:20]))


def main() -> int:
    validate_generated_text_tokens()
    validate_matches_and_frontend()
    validate_results_sync()
    validate_model_outputs()
    validate_legacy_orphans_removed()

    print("\n=== Validação de integridade dos dados ===")
    if warnings:
        print("Avisos:")
        for item in warnings:
            print(f"- {item}")
    if errors:
        print("Falhas:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("OK: CSV, JSON, JS, probabilidades e IDs principais estão sincronizados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
