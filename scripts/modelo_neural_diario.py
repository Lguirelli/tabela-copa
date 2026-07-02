#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelo neural/incremental diário para a Copa 2026.

Objetivo:
- Usar somente bases iniciais limpas para prever jogos: elenco, força, estilo, calendário e árbitros agregados.
- Ignorar previsões/simulações/resultados já prontos como entrada do modelo.
- Processar os jogos em ordem cronológica.
- Antes de cada jogo, gerar previsão usando o estado disponível até o dia/jogo anterior.
- Depois, se houver placar real, validar a previsão e atualizar rating, momentum e desempenho para jogos futuros.

Entradas usadas:
- data/database/players_database.csv
- data/database/team_strengths.csv
- data/database/teams_tactical.csv
- data/database/matches.csv
- data/database/referees_fifa.csv apenas como perfil agregado, sem assignments simulados
- data/resultados_reais.csv para validação pós-previsão
- data/entrada/desempenho_manual.csv para ajuste pós-jogo, somente depois do jogo validado

Entradas propositalmente ignoradas:
- data/previsoes_modelo.csv
- data/resultados.csv
- data/database/simulated_matches.csv
- data/database/simulated_referee_assignments.csv
- data/neural/* como fonte de previsão
- data/modelo/modelo_times.csv anterior
- data/desempenho/* gerado/duplicado como fonte de entrada
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

try:
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "modelo_diario"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 26062026
rng = np.random.default_rng(RANDOM_SEED)

ALIASES = {
    "republica da coreia": "coreia do sul",
    "coreia republica": "coreia do sul",
    "south korea": "coreia do sul",
    "korea republic": "coreia do sul",
    "republica tcheca": "tchequia",
    "czech republic": "tchequia",
    "czechia": "tchequia",
    "holanda": "paises baixos",
    "netherlands": "paises baixos",
    "turkiye": "turquia",
    "usa": "estados unidos",
    "eua": "estados unidos",
    "united states": "estados unidos",
    "dr congo": "rd congo",
    "congo dr": "rd congo",
    "congo kinshasa": "rd congo",
    "south africa": "africa do sul",
    "cote d ivoire": "costa do marfim",
    "ivory coast": "costa do marfim",
    "saudi arabia": "arabia saudita",
    "cape verde": "cabo verde",
    "new zealand": "nova zelandia",
    "bosnia herzegovina": "bosnia e herzegovina",
    "bosnia and herzegovina": "bosnia e herzegovina",
    "curacao": "curacao",
}

LEAGUE_STRENGTH = {
    "ENG": 10.0, "ESP": 9.8, "GER": 9.5, "DEU": 9.5, "ITA": 9.4, "FRA": 9.0,
    "POR": 8.5, "NED": 8.4, "BEL": 8.0, "BRA": 8.2, "ARG": 8.1, "TUR": 8.0,
    "USA": 7.4, "MEX": 7.3, "KSA": 7.2, "QAT": 6.9, "SCO": 7.3, "CHE": 7.6,
    "AUT": 7.5, "NOR": 7.2, "SWE": 7.1, "CZE": 6.9, "JPN": 6.9, "KOR": 6.8,
    "COL": 6.8, "ECU": 6.7, "URU": 6.8, "PAR": 6.5, "IRN": 6.2, "IRQ": 5.8,
    "AUS": 6.4, "CAN": 6.4, "MAR": 6.4, "EGY": 6.2, "RSA": 6.1, "ZAF": 6.1,
    "DZA": 6.1, "ALG": 6.1, "SEN": 6.1, "CIV": 6.1, "GHA": 6.1, "BIH": 6.2,
    "TUN": 6.0, "CPV": 5.8, "COD": 5.8, "UZB": 5.7, "PAN": 5.7, "NZL": 5.7,
    "JOR": 5.5, "HTI": 5.4, "CUW": 5.4,
}

HOST_NAMES = {"mexico", "canada", "estados unidos"}


def norm(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ALIASES.get(text, text)


def read_csv_auto(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    # Tenta separador automático simples. Muitas bases do projeto usam ;.
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    except Exception:
        return pd.read_csv(path, sep=";", encoding="utf-8-sig", **kwargs)


def to_num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def outcome_from_goals(g1: int, g2: int) -> str:
    if g1 > g2:
        return "1"
    if g2 > g1:
        return "2"
    return "X"


def winner_name(team1: str, g1: int, team2: str, g2: int) -> str:
    if g1 > g2:
        return team1
    if g2 > g1:
        return team2
    return "Empate"


def poisson_probs(xg1: float, xg2: float, max_goals: int = 8) -> Tuple[float, float, float]:
    probs1 = [math.exp(-xg1) * (xg1 ** k) / math.factorial(k) for k in range(max_goals + 1)]
    probs2 = [math.exp(-xg2) * (xg2 ** k) / math.factorial(k) for k in range(max_goals + 1)]
    p1 = px = p2 = 0.0
    for i, a in enumerate(probs1):
        for j, b in enumerate(probs2):
            p = a * b
            if i > j:
                p1 += p
            elif i == j:
                px += p
            else:
                p2 += p
    total = p1 + px + p2
    return p1 / total, px / total, p2 / total


def score_grid(xg1: float, xg2: float, max_goals: int = 7) -> List[Tuple[int, int, float]]:
    rows: List[Tuple[int, int, float]] = []
    for i in range(max_goals + 1):
        pi = math.exp(-xg1) * (xg1 ** i) / math.factorial(i)
        for j in range(max_goals + 1):
            pj = math.exp(-xg2) * (xg2 ** j) / math.factorial(j)
            rows.append((i, j, pi * pj))
    total = sum(p for _, _, p in rows) or 1.0
    return [(i, j, p / total) for i, j, p in rows]


def modal_score(xg1: float, xg2: float, max_goals: int = 7) -> Tuple[int, int]:
    best = max(score_grid(xg1, xg2, max_goals), key=lambda row: row[2])
    return int(best[0]), int(best[1])


def representative_score(
    xg1: float,
    xg2: float,
    outcome: str,
    game: int,
    team1: str = "",
    team2: str = "",
    max_goals: int = 7,
) -> Tuple[int, int, str]:
    """Escolhe um placar plausível sem repetir sempre o placar modal 1-0/0-1.

    O placar modal de uma distribuição Poisson independente costuma ser muito
    conservador. Para a tela principal, usamos um placar representativo dentro
    do resultado mais provável, combinando probabilidade com aderência ao xG e
    uma pequena variação determinística por jogo.
    """
    rows = score_grid(xg1, xg2, max_goals)
    if outcome == "1":
        candidates = [(i, j, p) for i, j, p in rows if i > j]
    elif outcome == "2":
        candidates = [(i, j, p) for i, j, p in rows if j > i]
    else:
        candidates = [(i, j, p) for i, j, p in rows if i == j]
    if not candidates:
        g1, g2 = modal_score(xg1, xg2, max_goals)
        return g1, g2, "modal_fallback"

    total_goals_target = xg1 + xg2
    margin_target = xg1 - xg2

    def score_candidate(row: Tuple[int, int, float]) -> float:
        i, j, p = row
        prob_component = math.log(max(p, 1e-12))
        total_penalty = abs((i + j) - total_goals_target) * 0.34
        margin_penalty = abs((i - j) - margin_target) * 0.26
        # Penaliza levemente o 1-0/0-1 quando o jogo tem volume para 2+ gols.
        low_score_penalty = 0.0
        if (i + j) <= 1 and total_goals_target >= 2.15:
            low_score_penalty = 0.55 + min(0.35, (total_goals_target - 2.15) * 0.30)
        # Evita placares muito abertos sem xG suficiente.
        blowout_penalty = 0.22 * max(0, abs(i - j) - max(1.0, abs(margin_target) + 0.8))
        return prob_component - total_penalty - margin_penalty - low_score_penalty - blowout_penalty

    ranked = sorted(candidates, key=score_candidate, reverse=True)
    # Entre candidatos quase equivalentes, alterna de forma determinística para
    # não transformar todo favoritismo moderado em 1-0.
    best_value = score_candidate(ranked[0])
    pool = [r for r in ranked[:8] if score_candidate(r) >= best_value - 0.32]
    if len(pool) > 1:
        key = f"{game}|{team1}|{team2}|{round(xg1, 2)}|{round(xg2, 2)}"
        idx = sum(ord(c) for c in key) % len(pool)
        chosen = pool[idx]
        method = "representativo_condicional"
    else:
        chosen = ranked[0]
        method = "representativo_probabilistico"
    return int(chosen[0]), int(chosen[1]), method


def penalty_shootout_probability(xg1: float, xg2: float, prob_draw_90: float) -> float:
    """Aproxima P(pênaltis) = P(empate em 90') * P(empate na prorrogação).

    A prorrogação é modelada com cerca de 1/3 do volume de xG de 90 minutos,
    mantendo a assimetria entre as equipes.
    """
    _, draw_extra, _ = poisson_probs(max(0.05, xg1 / 3.0), max(0.05, xg2 / 3.0), max_goals=5)
    return float(np.clip(prob_draw_90 * draw_extra, 0.0, 0.65))


def monte_carlo_probs_and_score(xg1: float, xg2: float, simulations: int, seed_extra: int = 0) -> Tuple[float, float, float, int, int]:
    if simulations <= 0:
        p1, px, p2 = poisson_probs(xg1, xg2)
        g1, g2 = modal_score(xg1, xg2)
        return p1, px, p2, g1, g2
    local_rng = np.random.default_rng(RANDOM_SEED + int(seed_extra) * 97 + simulations)
    g1_arr = local_rng.poisson(xg1, simulations)
    g2_arr = local_rng.poisson(xg2, simulations)
    p1 = float(np.mean(g1_arr > g2_arr))
    px = float(np.mean(g1_arr == g2_arr))
    p2 = float(np.mean(g2_arr > g1_arr))
    # Placar modal da interação Monte Carlo.
    pairs, counts = np.unique(np.column_stack([g1_arr, g2_arr]), axis=0, return_counts=True)
    best = pairs[int(np.argmax(counts))]
    return p1, px, p2, int(best[0]), int(best[1])

def confidence_label(p1: float, px: float, p2: float) -> str:
    top = max(p1, px, p2)
    margin = sorted([p1, px, p2], reverse=True)[0] - sorted([p1, px, p2], reverse=True)[1]
    if top >= 0.58 and margin >= 0.18:
        return "alta"
    if top >= 0.47 and margin >= 0.10:
        return "média"
    return "baixa"


def safe_float(v: object, default: float = 0.0) -> float:
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def opponent_quality_factor(opp_rating: float, opp_attack_score: float = 5.5) -> float:
    """Fator de qualidade do adversário para ajustar gols e resultados.

    > 1.0 = adversário forte/ofensivamente perigoso
    < 1.0 = adversário mais fraco
    """
    rating_component = float(opp_rating) / 60.0
    attack_component = float(opp_attack_score) / 5.5
    return float(np.clip(rating_component * 0.68 + attack_component * 0.32, 0.70, 1.35))


def goal_scored_multiplier(opp_quality: float) -> float:
    """Gol marcado contra adversário forte vale mais para a forma ofensiva."""
    return float(np.clip(opp_quality, 0.72, 1.32))


def goal_conceded_damage_multiplier(opp_quality: float) -> float:
    """Gol sofrido contra adversário forte gera dano menor; contra fraco gera dano maior."""
    return float(np.clip(1.0 / max(0.70, opp_quality), 0.72, 1.35))


def defensive_gap_adjusted_signal(xga_minus_goals_against: float, opp_quality: float) -> float:
    """Ajusta defesa pelo adversário.

    Se o time sofre menos gols que o xG contra adversário forte, recebe recompensa maior.
    Se sofre mais gols que o xG contra adversário fraco, recebe punição maior.
    """
    gap = float(xga_minus_goals_against)
    if gap >= 0:
        multiplier = float(np.clip(opp_quality, 0.82, 1.28))
    else:
        multiplier = goal_conceded_damage_multiplier(opp_quality)
    return gap * multiplier


@dataclass
class TeamState:
    team: str
    rating_base: float
    rating_dynamic: float
    momentum: float = 0.0
    performance_memory: float = 0.0
    offensive_form: float = 0.0
    defensive_form: float = 0.0
    schedule_strength: float = 60.0
    opponent_adjusted_points: float = 0.0
    opponent_weighted_goals_for: float = 0.0
    opponent_weighted_goals_against: float = 0.0
    games_validated: int = 0
    last_match_date: Optional[pd.Timestamp] = None
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0


class DailyWorldCupModel:
    def __init__(self, root: Path, simulations: int = 8000, neural_min_samples: int = 16):
        self.root = root
        self.simulations = simulations
        self.neural_min_samples = neural_min_samples
        self.alias_to_team: Dict[str, str] = {}
        self.features_team = pd.DataFrame()
        self.matches = pd.DataFrame()
        self.real_results = pd.DataFrame()
        self.performance_by_match_team: Dict[Tuple[int, str], float] = {}
        self.performance_components_by_match_team: Dict[Tuple[int, str], Dict[str, float]] = {}
        self.states: Dict[str, TeamState] = {}
        self.history_features: List[List[float]] = []
        self.history_labels: List[int] = []
        self.predictions: List[dict] = []
        self.validations: List[dict] = []
        self.daily_rows: List[dict] = []

    def canonical_team(self, value: object) -> str:
        key = norm(value)
        return self.alias_to_team.get(key, str(value).strip())

    def load(self) -> None:
        strength = read_csv_auto(self.root / "data/database/team_strengths.csv")
        tactical = read_csv_auto(self.root / "data/database/teams_tactical.csv")
        players = read_csv_auto(self.root / "data/database/players_database.csv")
        matches = read_csv_auto(self.root / "data/database/matches.csv")
        refs = read_csv_auto(self.root / "data/database/referees_fifa.csv")
        real = read_csv_auto(self.root / "data/resultados_reais.csv")

        if strength.empty or matches.empty:
            raise RuntimeError("Bases mínimas não encontradas: team_strengths.csv e matches.csv são obrigatórios.")

        # Canonicaliza nomes pelos times da base de força.
        for _, r in strength.iterrows():
            team = str(r.get("selecao", "")).strip()
            if not team:
                continue
            self.alias_to_team[norm(team)] = team
            if "selecao_xlsx" in r and str(r.get("selecao_xlsx", "")).strip():
                self.alias_to_team[norm(r["selecao_xlsx"])] = team
        # aliases comuns adicionais
        for k, v in {
            "Republica da Coreia": "Coreia do Sul",
            "Korea Republic": "Coreia do Sul",
            "South Korea": "Coreia do Sul",
            "Czech Republic": "Tchéquia",
            "Czechia": "Tchéquia",
            "Netherlands": "Países Baixos",
            "Ivory Coast": "Costa do Marfim",
            "United States": "Estados Unidos",
            "DR Congo": "RD Congo",
            "Congo DR": "RD Congo",
            "Saudi Arabia": "Arábia Saudita",
            "Cape Verde": "Cabo Verde",
            "New Zealand": "Nova Zelândia",
            "South Africa": "África do Sul",
            "Algeria": "Argélia",
            "Bosnia and Herzegovina": "Bósnia e Herzegovina",
        }.items():
            if norm(v) in self.alias_to_team:
                self.alias_to_team[norm(k)] = self.alias_to_team[norm(v)]

        self.features_team = self.build_team_features(strength, tactical, players, refs)
        self.matches = self.clean_matches(matches)
        self.real_results = self.clean_real_results(real)
        self.performance_by_match_team = self.load_performance_impacts()

        self.states = {
            row["selecao"]: TeamState(
                team=row["selecao"],
                rating_base=float(row["rating_inicial_0_100"]),
                rating_dynamic=float(row["rating_inicial_0_100"]),
            )
            for _, row in self.features_team.iterrows()
        }

    def build_team_features(self, strength: pd.DataFrame, tactical: pd.DataFrame, players: pd.DataFrame, refs: pd.DataFrame) -> pd.DataFrame:
        df = strength.copy()
        df["selecao"] = df["selecao"].astype(str).str.strip()
        numeric_cols = [
            "forca_modelo_0_100", "media_proxy", "top11_proxy", "top18_proxy",
            "ataque_score", "meio_score", "defesa_score", "goleiro_score",
            "caps_media", "caps_total", "gols_selecao_total", "experiencia_score",
            "intensidade_valor", "posse_valor", "pressao_valor",
        ]
        for col in numeric_cols:
            if col in df:
                df[col] = to_num(df[col], 0)
            else:
                df[col] = 0.0

        if not players.empty:
            p = players.copy()
            p["selecao"] = p["Seleção"].map(self.canonical_team)
            p["proxy"] = to_num(p.get("Índice proxy 0-10", pd.Series(index=p.index)), 5.0)
            p["league"] = p.get("País do clube", pd.Series(index=p.index)).fillna("").astype(str).str.upper().str.strip()
            p["league_strength"] = p["league"].map(lambda x: LEAGUE_STRENGTH.get(x, 6.2))
            p["caps"] = to_num(p.get("Caps seleção", pd.Series(index=p.index)), 0)
            p["goals"] = to_num(p.get("Gols seleção", pd.Series(index=p.index)), 0)
            p["age"] = to_num(p.get("Idade em 26/06/2026", pd.Series(index=p.index)), 27)
            p["player_quality"] = (
                p["proxy"] * 0.52
                + p["league_strength"] * 0.30
                + (p["caps"].clip(0, 100) / 100 * 10) * 0.12
                + (p["goals"].clip(0, 40) / 40 * 10) * 0.06
            )
            player_agg = p.groupby("selecao").agg(
                qtd_jogadores=("Jogador", "count"),
                liga_media=("league_strength", "mean"),
                liga_top11=("league_strength", lambda s: s.sort_values(ascending=False).head(11).mean()),
                qualidade_top11=("player_quality", lambda s: s.sort_values(ascending=False).head(11).mean()),
                qualidade_top18=("player_quality", lambda s: s.sort_values(ascending=False).head(18).mean()),
                idade_media=("age", "mean"),
                caps_mediana=("caps", "median"),
            ).reset_index()
        else:
            player_agg = pd.DataFrame(columns=["selecao"])

        df = df.merge(player_agg, on="selecao", how="left")
        for col in ["qtd_jogadores", "liga_media", "liga_top11", "qualidade_top11", "qualidade_top18", "idade_media", "caps_mediana"]:
            df[col] = to_num(df.get(col, pd.Series(index=df.index)), 0)

        # Perfil agregado de arbitragem: não usa sorteio/assignment simulado por jogo.
        if not refs.empty:
            only_refs = refs[refs.get("Função", "").astype(str).str.lower().eq("referee")] if "Função" in refs else refs
            ref_card = safe_float(only_refs.get("rigor_cartoes_simulado_0_10", pd.Series(dtype=float)).mean(), 5.0)
            ref_flow = safe_float(only_refs.get("fluidez_jogo_simulada_0_10", pd.Series(dtype=float)).mean(), 5.0)
            ref_var = safe_float(only_refs.get("var_intervencao_simulada_0_10", pd.Series(dtype=float)).mean(), 5.0)
            ref_pen = safe_float(only_refs.get("penalti_tendencia_simulada_0_10", pd.Series(dtype=float)).mean(), 5.0)
        else:
            ref_card = ref_flow = ref_var = ref_pen = 5.0

        df["arbitragem_rigor_medio_0_10"] = ref_card
        df["arbitragem_fluidez_media_0_10"] = ref_flow
        df["arbitragem_var_media_0_10"] = ref_var
        df["arbitragem_penalti_media_0_10"] = ref_pen

        # Rating inicial sem usar resultado pronto. Combina força, jogadores e competitividade.
        league_base = df["liga_top11"].where(df["liga_top11"] > 0, df["liga_media"])
        quality_base = df["qualidade_top18"].where(df["qualidade_top18"] > 0, df["top18_proxy"])
        df["competitividade_liga_0_100"] = (league_base * 10).clip(0, 100)
        df["qualidade_jogadores_0_100"] = (quality_base * 10).clip(0, 100)
        df["equilibrio_setores_0_100"] = ((df["ataque_score"] + df["meio_score"] + df["defesa_score"] + df["goleiro_score"]) / 4 * 10).clip(0, 100)
        df["rating_inicial_0_100"] = (
            df["forca_modelo_0_100"] * 0.45
            + df["qualidade_jogadores_0_100"] * 0.22
            + df["competitividade_liga_0_100"] * 0.16
            + df["equilibrio_setores_0_100"] * 0.12
            + (df["experiencia_score"] * 10) * 0.05
        ).round(2)
        df["fonte_rating"] = "team_strengths + players_database + árbitros agregados; sem previsões/simulações prévias"
        return df.sort_values("rating_inicial_0_100", ascending=False)

    def clean_matches(self, matches: pd.DataFrame) -> pd.DataFrame:
        df = matches.copy()
        df["jogo"] = to_num(df["jogo"], 0).astype(int)
        df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")
        df["equipe1"] = df["equipe1"].map(self.canonical_team)
        df["equipe2"] = df["equipe2"].map(self.canonical_team)
        df["rodadaGrupo"] = to_num(df.get("rodadaGrupo", pd.Series(index=df.index)), 0)
        df = df.sort_values(["data_dt", "jogo"]).reset_index(drop=True)
        return df

    def clean_real_results(self, real: pd.DataFrame) -> pd.DataFrame:
        if real.empty:
            return pd.DataFrame(columns=["jogo"])
        df = real.copy()
        df["jogo"] = to_num(df["jogo"], 0).astype(int)
        df["data_dt"] = pd.to_datetime(df.get("data", pd.Series(index=df.index)), errors="coerce")
        df["equipe1"] = df["equipe1"].map(self.canonical_team)
        df["equipe2"] = df["equipe2"].map(self.canonical_team)
        df["gols1_real"] = to_num(df["gols1_real"], 0).astype(int)
        df["gols2_real"] = to_num(df["gols2_real"], 0).astype(int)
        return df.sort_values(["data_dt", "jogo"]).drop_duplicates("jogo", keep="last")

    def performance_text_score(self, tipo: object, detalhe: object) -> float:
        txt = norm(f"{tipo} {detalhe}")
        score = 0.0
        if "gol assistencia" in txt or "gol e assistencia" in txt:
            score += 1.0
        if "hat trick" in txt or "3 gols" in txt or "tres gols" in txt:
            score += 1.6
        if "2 gols" in txt or "doblete" in txt:
            score += 1.2
        if "gol" in txt:
            score += 0.55
        if "assist" in txt:
            score += 0.35
        if "destaque" in txt or "mvp" in txt or "lider" in txt or "decisivo" in txt:
            score += 0.45
        if "goleiro" in txt or "defesa" in txt or "clean sheet" in txt:
            score += 0.25
        if "expuls" in txt or "disciplina negativa" in txt or "falha" in txt or "erro" in txt or "abaixo" in txt:
            score -= 1.25
        return score

    def load_performance_impacts(self) -> Dict[Tuple[int, str], float]:
        """Lê somente a entrada manual auditável de desempenho.

        Fonte única versionada:
        - data/entrada/desempenho_manual.csv

        Bases consolidadas antigas em data/desempenho/* não são mais usadas como entrada,
        porque geravam duplicação e conflitos no repositório. O impacto só é aplicado
        depois que o jogo possui resultado real validado pelo fluxo diário.
        """
        impacts: Dict[Tuple[int, str], float] = {}
        manual_path = self.root / "data" / "entrada" / "desempenho_manual.csv"
        if not manual_path.exists() or manual_path.stat().st_size < 10:
            return impacts

        manual = pd.DataFrame()
        for kwargs in ({"sep": None, "engine": "python"}, {"sep": ";"}, {"sep": ","}):
            try:
                manual = pd.read_csv(manual_path, encoding="utf-8-sig", **kwargs)
                if len(manual.columns) > 1:
                    break
            except Exception:
                manual = pd.DataFrame()
        if manual.empty:
            return impacts
        manual.columns = [str(c).replace("\ufeff", "").strip() for c in manual.columns]

        def col(row, *names, default=""):
            for name in names:
                if name in row and not pd.isna(row.get(name)):
                    return row.get(name)
            return default

        for _, r in manual.iterrows():
            game_val = col(r, "jogo", "ID jogo", default="")
            if pd.isna(game_val) or str(game_val).strip().upper() in {"", "NA"}:
                continue
            game = int(safe_float(game_val, 0))
            if game <= 0:
                continue

            team = self.canonical_team(col(r, "selecao", "Seleção", "time", "equipe", default=""))
            if not team:
                continue

            impact = safe_float(col(r, "impacto_modelo_jogador", "impacto_modelo", default=0), 0)
            if impact == 0:
                impact += self.performance_text_score(
                    col(r, "tipo_desempenho", "Tipo de desempenho", default=""),
                    col(r, "detalhe_pesquisado", "Detalhe pesquisado", default=""),
                )

            # Impacto leve por métricas de equipe, sempre vindo da linha manual auditável.
            def num_or_none(value):
                try:
                    text = str(value).strip().upper()
                    if text in {"", "NA", "NAN", "NONE"}:
                        return None
                    if pd.isna(value):
                        return None
                    return float(value)
                except Exception:
                    return None

            metric_impact = 0.0
            attack_component = 0.0
            defense_component = 0.0
            chance_quality_component = 0.0

            xg_pro, xg_against = num_or_none(col(r, "xg_pro", default="NA")), num_or_none(col(r, "xg_contra", default="NA"))
            if xg_pro is not None and xg_against is not None:
                xg_diff = max(-2.0, min(2.0, xg_pro - xg_against))
                metric_impact += xg_diff * 0.22
                attack_component += max(-1.5, min(1.5, xg_pro - 1.20)) * 0.42
                defense_component += max(-1.5, min(1.5, 1.20 - xg_against)) * 0.42
                chance_quality_component += xg_diff * 0.18

            # Agregado da fase de grupos: separa volume ofensivo de solidez defensiva.
            gp = num_or_none(col(r, "gp", "jogos", default="NA"))
            gf = num_or_none(col(r, "gf", "gols_pro", default="NA"))
            ga = num_or_none(col(r, "ga", "gols_contra", default="NA"))
            xg_total = num_or_none(col(r, "xg_total", "xg_pro_fase_grupos", default="NA"))
            if gp is not None and gp > 0:
                if gf is not None:
                    gf_pg = gf / gp
                    attack_component += max(-1.6, min(1.6, gf_pg - 1.35)) * 0.30
                if ga is not None:
                    ga_pg = ga / gp
                    defense_component += max(-1.6, min(1.6, 1.15 - ga_pg)) * 0.34
                if xg_total is not None:
                    xg_pg = xg_total / gp
                    attack_component += max(-1.4, min(1.4, xg_pg - 1.25)) * 0.26

            shots_on, shots_on_against = num_or_none(col(r, "finalizacoes_alvo", default="NA")), num_or_none(col(r, "finalizacoes_alvo_contra", default="NA"))
            if shots_on is not None and shots_on_against is not None:
                shots_diff = max(-6.0, min(6.0, shots_on - shots_on_against))
                metric_impact += shots_diff * 0.022
                attack_component += max(-5.0, min(5.0, shots_on - 4.0)) * 0.035
                defense_component += max(-5.0, min(5.0, 4.0 - shots_on_against)) * 0.035
            big_chance, big_chance_against = num_or_none(col(r, "grandes_chances", default="NA")), num_or_none(col(r, "grandes_chances_contra", default="NA"))
            if big_chance is not None and big_chance_against is not None:
                chance_diff = max(-4.0, min(4.0, big_chance - big_chance_against))
                metric_impact += chance_diff * 0.055
                chance_quality_component += chance_diff * 0.08
            box_touches, box_touches_against = num_or_none(col(r, "toques_area", default="NA")), num_or_none(col(r, "toques_area_contra", default="NA"))
            if box_touches is not None and box_touches_against is not None:
                touch_diff = max(-30.0, min(30.0, box_touches - box_touches_against))
                metric_impact += touch_diff * 0.0035
                attack_component += max(-25.0, min(25.0, box_touches - 18.0)) * 0.004
                defense_component += max(-25.0, min(25.0, 18.0 - box_touches_against)) * 0.004
            errors = num_or_none(col(r, "erros_gol", default="NA"))
            if errors is not None:
                metric_impact -= min(3.0, max(0.0, errors)) * 0.25
                defense_component -= min(3.0, max(0.0, errors)) * 0.28

            # impacto_modelo manual continua aceito, mas com teto conservador para não inflar seleções
            # apenas por saldo/defesa da fase de grupos.
            total = max(-1.25, min(1.25, impact * 0.55 + metric_impact))
            attack_component = max(-1.6, min(1.6, attack_component))
            defense_component = max(-1.6, min(1.6, defense_component))
            chance_quality_component = max(-1.2, min(1.2, chance_quality_component))
            key = (game, team)
            if total != 0:
                impacts[key] = impacts.get(key, 0.0) + total
            prev = self.performance_components_by_match_team.get(key, {"attack": 0.0, "defense": 0.0, "chance_quality": 0.0})
            self.performance_components_by_match_team[key] = {
                "attack": prev.get("attack", 0.0) + attack_component,
                "defense": prev.get("defense", 0.0) + defense_component,
                "chance_quality": prev.get("chance_quality", 0.0) + chance_quality_component,
            }

        return impacts

    def rest_days(self, team: str, current_date: pd.Timestamp) -> float:
        st = self.states.get(team)
        if not st or st.last_match_date is None or pd.isna(current_date):
            return 6.0
        return max(1.0, min(12.0, float((current_date - st.last_match_date).days)))

    def team_row(self, team: str) -> pd.Series:
        rows = self.features_team[self.features_team["selecao"] == team]
        if rows.empty:
            # fallback neutro para placeholders de mata-mata ainda indefinidos.
            return pd.Series({
                "selecao": team,
                "rating_inicial_0_100": 60.0,
                "ataque_score": 5.5,
                "meio_score": 5.5,
                "defesa_score": 5.5,
                "goleiro_score": 5.5,
                "experiencia_score": 6.0,
                "intensidade_valor": 5.0,
                "posse_valor": 5.0,
                "pressao_valor": 5.0,
                "competitividade_liga_0_100": 62.0,
                "qualidade_jogadores_0_100": 60.0,
            })
        return rows.iloc[0]

    def build_match_features(self, match: pd.Series) -> Tuple[List[float], dict]:
        t1, t2 = str(match["equipe1"]), str(match["equipe2"])
        r1, r2 = self.team_row(t1), self.team_row(t2)
        s1 = self.states.get(t1, TeamState(t1, 60.0, 60.0))
        s2 = self.states.get(t2, TeamState(t2, 60.0, 60.0))
        date = match.get("data_dt")
        rest1, rest2 = self.rest_days(t1, date), self.rest_days(t2, date)
        # Modelo sem bônus de mandante/sede: a Copa 2026 é multi-país e o bônus
        # estava inflando seleções anfitriãs fora do próprio contexto real.
        # Mantemos host_diff para compatibilidade de schema, sempre zerado.
        host1 = 0.0
        host2 = 0.0
        knockout = 0.0 if str(match.get("fase", "")).lower().startswith("fase de grupos") else 1.0

        games1 = max(1.0, float(s1.games_validated or 0) or 1.0)
        games2 = max(1.0, float(s2.games_validated or 0) or 1.0)
        gf_rate1, gf_rate2 = s1.goals_for / games1, s2.goals_for / games2
        ga_rate1, ga_rate2 = s1.goals_against / games1, s2.goals_against / games2
        weighted_gf_rate1 = s1.opponent_weighted_goals_for / games1
        weighted_gf_rate2 = s2.opponent_weighted_goals_for / games2
        adjusted_ga_rate1 = s1.opponent_weighted_goals_against / games1
        adjusted_ga_rate2 = s2.opponent_weighted_goals_against / games2

        # Diferenças sempre na perspectiva da equipe1.
        # Gols marcados e sofridos ficam separados para evitar que um saldo simples infle o modelo.
        f = {
            "rating_diff": s1.rating_dynamic - s2.rating_dynamic,
            "base_rating_diff": float(r1["rating_inicial_0_100"]) - float(r2["rating_inicial_0_100"]),
            "attack_vs_defense": float(r1["ataque_score"]) - float(r2["defesa_score"]),
            "defense_vs_attack": float(r1["defesa_score"]) - float(r2["ataque_score"]),
            "midfield_diff": float(r1["meio_score"]) - float(r2["meio_score"]),
            "goalkeeper_diff": float(r1["goleiro_score"]) - float(r2["goleiro_score"]),
            "experience_diff": float(r1["experiencia_score"]) - float(r2["experiencia_score"]),
            "league_diff": float(r1["competitividade_liga_0_100"]) - float(r2["competitividade_liga_0_100"]),
            "player_quality_diff": float(r1["qualidade_jogadores_0_100"]) - float(r2["qualidade_jogadores_0_100"]),
            "intensity_diff": float(r1["intensidade_valor"]) - float(r2["intensidade_valor"]),
            "possession_diff": float(r1["posse_valor"]) - float(r2["posse_valor"]),
            "pressing_diff": float(r1["pressao_valor"]) - float(r2["pressao_valor"]),
            "momentum_diff": s1.momentum - s2.momentum,
            "performance_memory_diff": s1.performance_memory - s2.performance_memory,
            "offensive_form_diff": s1.offensive_form - s2.offensive_form,
            "defensive_form_diff": s1.defensive_form - s2.defensive_form,
            "offensive_form_equipe1": s1.offensive_form,
            "offensive_form_equipe2": s2.offensive_form,
            "defensive_form_equipe1": s1.defensive_form,
            "defensive_form_equipe2": s2.defensive_form,
            "schedule_strength_diff": s1.schedule_strength - s2.schedule_strength,
            "opponent_adjusted_points_diff": s1.opponent_adjusted_points - s2.opponent_adjusted_points,
            "goals_for_rate_diff": gf_rate1 - gf_rate2,
            "goals_against_rate_diff": ga_rate1 - ga_rate2,
            "opponent_weighted_goals_for_diff": s1.opponent_weighted_goals_for - s2.opponent_weighted_goals_for,
            "opponent_weighted_goals_against_diff": s1.opponent_weighted_goals_against - s2.opponent_weighted_goals_against,
            "weighted_goals_for_rate_diff": weighted_gf_rate1 - weighted_gf_rate2,
            "adjusted_goals_against_rate_diff": adjusted_ga_rate1 - adjusted_ga_rate2,
            "weighted_goals_for_rate_equipe1": weighted_gf_rate1,
            "weighted_goals_for_rate_equipe2": weighted_gf_rate2,
            "adjusted_goals_against_rate_equipe1": adjusted_ga_rate1,
            "adjusted_goals_against_rate_equipe2": adjusted_ga_rate2,
            "rest_diff": rest1 - rest2,
            "host_diff": host1 - host2,
            "knockout": knockout,
            "round_group": float(match.get("rodadaGrupo", 0) or 0),
        }
        vector = [
            f["rating_diff"], f["base_rating_diff"], f["attack_vs_defense"], f["defense_vs_attack"],
            f["midfield_diff"], f["goalkeeper_diff"], f["experience_diff"], f["league_diff"],
            f["player_quality_diff"], f["intensity_diff"], f["possession_diff"], f["pressing_diff"],
            f["momentum_diff"], f["performance_memory_diff"], f["offensive_form_diff"], f["defensive_form_diff"],
            f["schedule_strength_diff"], f["opponent_adjusted_points_diff"], f["goals_for_rate_diff"], f["goals_against_rate_diff"],
            f["opponent_weighted_goals_for_diff"], f["opponent_weighted_goals_against_diff"],
            f["weighted_goals_for_rate_diff"], f["adjusted_goals_against_rate_diff"],
            f["rest_diff"], f["host_diff"], f["knockout"], f["round_group"],
        ]
        return vector, f

    def expected_goals(self, match: pd.Series, f: dict) -> Tuple[float, float]:
        t1, t2 = str(match["equipe1"]), str(match["equipe2"])
        r1, r2 = self.team_row(t1), self.team_row(t2)
        # Base calibrada para Copa: média levemente acima de 1.2 por equipe, ajustada por força/setor.
        base = 1.18
        atk1 = (float(r1["ataque_score"]) - 5.5) * 0.145
        atk2 = (float(r2["ataque_score"]) - 5.5) * 0.145
        def1 = (float(r1["defesa_score"]) - 5.5) * 0.120
        def2 = (float(r2["defesa_score"]) - 5.5) * 0.120

        # Separação real: gol marcado aumenta a forma ofensiva; gol sofrido afeta a forma defensiva.
        # O peso do resultado anterior existe, mas não pode virar atalho para inflar mata-mata.
        form1 = f.get("offensive_form_equipe1", 0.0) * 0.085 - f.get("defensive_form_equipe2", 0.0) * 0.095
        form2 = f.get("offensive_form_equipe2", 0.0) * 0.085 - f.get("defensive_form_equipe1", 0.0) * 0.095
        schedule_adj = max(-0.10, min(0.10, f.get("schedule_strength_diff", 0.0) * 0.006))
        points_adj = max(-0.08, min(0.08, f.get("opponent_adjusted_points_diff", 0.0) * 0.010))
        # Produção ofensiva e vulnerabilidade defensiva ajustadas pela força dos adversários já enfrentados.
        # adjusted_goals_against_rate alto indica dano defensivo real, principalmente por gols sofridos
        # contra adversários fracos. Contra adversários fortes, o dano entra amortecido.
        attack_rate1 = max(-0.10, min(0.10, (f.get("weighted_goals_for_rate_equipe1", 0.0) - 1.20) * 0.045))
        attack_rate2 = max(-0.10, min(0.10, (f.get("weighted_goals_for_rate_equipe2", 0.0) - 1.20) * 0.045))
        defensive_vulnerability1 = max(-0.12, min(0.14, (f.get("adjusted_goals_against_rate_equipe1", 0.0) - 1.05) * 0.060))
        defensive_vulnerability2 = max(-0.12, min(0.14, (f.get("adjusted_goals_against_rate_equipe2", 0.0) - 1.05) * 0.060))

        xg1 = (
            base + atk1 - def2
            + f["rating_diff"] * 0.014
            + f["momentum_diff"] * 0.055
            + f["performance_memory_diff"] * 0.030
            + form1 + schedule_adj + points_adj
            + attack_rate1 + defensive_vulnerability2
        )
        xg2 = (
            base + atk2 - def1
            - f["rating_diff"] * 0.014
            - f["momentum_diff"] * 0.055
            - f["performance_memory_diff"] * 0.030
            + form2 - schedule_adj - points_adj
            + attack_rate2 + defensive_vulnerability1
        )
        # Jogo de mata-mata tende a maior cautela.
        if f["knockout"]:
            xg1 *= 0.92
            xg2 *= 0.92
        # Descanso maior reduz risco de queda física.
        xg1 += max(-0.12, min(0.12, f["rest_diff"] * 0.025))
        xg2 -= max(-0.12, min(0.12, f["rest_diff"] * 0.025))
        return float(np.clip(xg1, 0.25, 3.9)), float(np.clip(xg2, 0.25, 3.9))

    def neural_probabilities(self, features: List[float]) -> Optional[Tuple[float, float, float, float]]:
        if not SKLEARN_AVAILABLE or len(self.history_labels) < self.neural_min_samples:
            return None
        classes = sorted(set(self.history_labels))
        if len(classes) < 2:
            return None
        X = np.array(self.history_features, dtype=float)
        y = np.array(self.history_labels, dtype=int)
        # Em poucos jogos, rede pequena e regularizada para calibrar sem dominar o prior.
        clf = Pipeline([
            ("scale", StandardScaler()),
            ("mlp", MLPClassifier(
                hidden_layer_sizes=(12, 6),
                activation="relu",
                alpha=0.08,
                learning_rate_init=0.01,
                max_iter=800,
                random_state=RANDOM_SEED,
                early_stopping=False,
            )),
        ])
        try:
            clf.fit(X, y)
            proba_raw = clf.predict_proba(np.array(features, dtype=float).reshape(1, -1))[0]
            class_order = clf.named_steps["mlp"].classes_
            # label: 0=equipe1, 1=empate, 2=equipe2
            probs = {int(c): float(p) for c, p in zip(class_order, proba_raw)}
            p1, px, p2 = probs.get(0, 0.0), probs.get(1, 0.0), probs.get(2, 0.0)
            total = p1 + px + p2
            if total <= 0:
                return None
            # Peso da rede é apenas calibrador. Com poucos jogos validados, ela não deve inverter
            # favoritos quando xG/rating/desempenho apontam o contrário.
            blend = min(0.08, 0.025 + len(self.history_labels) / 1600.0)
            return p1 / total, px / total, p2 / total, blend
        except Exception:
            return None

    def predict_match(self, match: pd.Series) -> dict:
        features, details = self.build_match_features(match)
        xg1, xg2 = self.expected_goals(match, details)
        p1, px, p2, g1, g2 = monte_carlo_probs_and_score(xg1, xg2, self.simulations, int(match["jogo"]))
        neural = self.neural_probabilities(features)
        neural_weight = 0.0
        if neural is not None:
            np1, npx, np2, neural_weight = neural
            p1 = (1 - neural_weight) * p1 + neural_weight * np1
            px = (1 - neural_weight) * px + neural_weight * npx
            p2 = (1 - neural_weight) * p2 + neural_weight * np2
            total = p1 + px + p2
            p1, px, p2 = p1 / total, px / total, p2 / total

        # Guarda de veracidade: a rede neural não pode virar o favorito quando o xG
        # e o rating dão vantagem clara ao outro lado, salvo margem probabilística muito forte.
        xg_margin = xg1 - xg2
        if xg_margin > 0.28 and p2 > p1 and (p2 - p1) < 0.16:
            excess = (p2 - p1) + 0.025
            p2 -= excess / 2
            p1 += excess / 2
        elif xg_margin < -0.28 and p1 > p2 and (p1 - p2) < 0.16:
            excess = (p1 - p2) + 0.025
            p1 -= excess / 2
            p2 += excess / 2
        # Em margem estatística muito apertada, desempata pelo xG, não por ruído da rede.
        if xg_margin > 0.08 and p2 > p1 and (p2 - p1) < 0.06:
            excess = (p2 - p1) + 0.012
            p2 -= excess / 2
            p1 += excess / 2
        elif xg_margin < -0.08 and p1 > p2 and (p1 - p2) < 0.06:
            excess = (p1 - p2) + 0.012
            p1 -= excess / 2
            p2 += excess / 2
        total = p1 + px + p2
        p1, px, p2 = p1 / total, px / total, p2 / total

        # Placar principal: não usa apenas o placar modal bruto, porque isso
        # repete 1-0/0-1 em excesso quando o xG fica próximo de 1 por equipe.
        predicted_outcome = ["1", "X", "2"][[p1, px, p2].index(max(p1, px, p2))]
        criterion_outcome = "maior_probabilidade"
        prob_penaltis = penalty_shootout_probability(xg1, xg2, px) if bool(details.get("knockout", 0.0)) else 0.0
        # Em mata-mata, uma vitória estreita não deve apagar o risco real de
        # empate e pênaltis. Se o empate estiver perto da maior probabilidade,
        # modela o tempo de jogo como empate e deixa o classificado vir da
        # rotina de pênaltis.
        if bool(details.get("knockout", 0.0)):
            top_non_draw = max(p1, p2)
            close_to_draw = (top_non_draw - px) <= 0.085
            enough_penalty_risk = prob_penaltis >= 0.145 or px >= 0.285
            if close_to_draw and enough_penalty_risk:
                predicted_outcome = "X"
                criterion_outcome = "risco_penaltis_considerado"

        modal_g1, modal_g2 = int(g1), int(g2)
        g1, g2, score_method = representative_score(
            xg1, xg2, predicted_outcome, int(match["jogo"]), str(match["equipe1"]), str(match["equipe2"])
        )

        row = {
            "jogo": int(match["jogo"]),
            "data": str(match.get("data", "")),
            "fase": match.get("fase", ""),
            "grupo": match.get("grupo", ""),
            "rodadaGrupo": match.get("rodadaGrupo", ""),
            "equipe1": match["equipe1"],
            "equipe2": match["equipe2"],
            "xg1_modelo": round(xg1, 3),
            "xg2_modelo": round(xg2, 3),
            "placar_previsto": f"{g1}-{g2}",
            "placar_modal_bruto": f"{modal_g1}-{modal_g2}",
            "metodo_placar": score_method,
            "criterio_resultado_modelado": criterion_outcome,
            "gols1_previsto": int(g1),
            "gols2_previsto": int(g2),
            "vencedor_previsto": winner_name(str(match["equipe1"]), g1, str(match["equipe2"]), g2),
            "prob_vitoria_equipe1": round(p1, 4),
            "prob_empate": round(px, 4),
            "prob_vitoria_equipe2": round(p2, 4),
            "prob_decisao_penaltis": round(prob_penaltis, 4),
            "confianca_modelo": confidence_label(p1, px, p2),
            "peso_rede_neural": round(neural_weight, 3),
            "validacoes_anteriores_usadas": len(self.history_labels),
            "interacoes_monte_carlo": int(self.simulations),
        }
        row.update({f"feature_{k}": round(float(v), 4) for k, v in details.items()})
        return row

    def validate_and_update(self, match: pd.Series, prediction: dict, real_row: pd.Series) -> dict:
        t1, t2 = str(match["equipe1"]), str(match["equipe2"])
        a1, a2 = int(real_row["gols1_real"]), int(real_row["gols2_real"])
        p1, p2 = int(prediction["gols1_previsto"]), int(prediction["gols2_previsto"])
        xg1, xg2 = float(prediction["xg1_modelo"]), float(prediction["xg2_modelo"])
        pred_out = outcome_from_goals(p1, p2)
        real_out = outcome_from_goals(a1, a2)
        real_winner_manual = str(real_row.get("vencedor_real", "") or "").strip()
        penalty_score_real = str(real_row.get("placar_penaltis_real", "") or "").strip()
        knockout_real_penalty = (
            str(match.get("fase", "")).strip() != "Fase de grupos"
            and a1 == a2
            and real_winner_manual in {t1, t2}
        )
        if knockout_real_penalty:
            real_out = "1" if real_winner_manual == t1 else "2"
        exact = (p1 == a1 and p2 == a2)
        winner_ok = pred_out == real_out
        err_goals = abs(a1 - p1) + abs(a2 - p2)
        err_xg = abs(a1 - xg1) + abs(a2 - xg2)
        err_margin = abs((a1 - a2) - (p1 - p2))
        proximity = max(0.0, 100 - err_goals * 14 - err_margin * 12 - (0 if winner_ok else 22))

        perf1 = self.performance_by_match_team.get((int(match["jogo"]), t1), 0.0)
        perf2 = self.performance_by_match_team.get((int(match["jogo"]), t2), 0.0)
        if knockout_real_penalty:
            result_points1 = 2 if real_winner_manual == t1 else 1
            result_points2 = 2 if real_winner_manual == t2 else 1
        else:
            result_points1 = 3 if a1 > a2 else 1 if a1 == a2 else 0
            result_points2 = 3 if a2 > a1 else 1 if a1 == a2 else 0
        expected_margin = xg1 - xg2
        real_margin = a1 - a2
        surprise = real_margin - expected_margin

        s1 = self.states.setdefault(t1, TeamState(t1, 60.0, 60.0))
        s2 = self.states.setdefault(t2, TeamState(t2, 60.0, 60.0))

        # Peso do adversário: resultado contra time forte vale mais; tropeço contra time fraco pesa mais.
        # Gols sofridos também são ajustados: sofrer de ataque forte pesa menos negativamente;
        # sofrer de ataque fraco pesa mais negativamente.
        rating1_pre, rating2_pre = float(s1.rating_dynamic), float(s2.rating_dynamic)
        opp_attack_t1 = safe_float(self.team_row(t1).get("ataque_score", 5.5), 5.5)
        opp_attack_t2 = safe_float(self.team_row(t2).get("ataque_score", 5.5), 5.5)
        opp_quality_for_t1 = opponent_quality_factor(rating2_pre, opp_attack_t2)
        opp_quality_for_t2 = opponent_quality_factor(rating1_pre, opp_attack_t1)
        opp_factor_for_t1 = goal_scored_multiplier(opp_quality_for_t1)
        opp_factor_for_t2 = goal_scored_multiplier(opp_quality_for_t2)
        ga_penalty_t1 = goal_conceded_damage_multiplier(opp_quality_for_t1)
        ga_penalty_t2 = goal_conceded_damage_multiplier(opp_quality_for_t2)

        expected_points1 = safe_float(prediction.get("prob_vitoria_equipe1", 0), 0) * 3 + safe_float(prediction.get("prob_empate", 0), 0)
        expected_points2 = safe_float(prediction.get("prob_vitoria_equipe2", 0), 0) * 3 + safe_float(prediction.get("prob_empate", 0), 0)
        result_surprise1 = float(np.clip((result_points1 - expected_points1) / 3.0, -1.0, 1.0))
        result_surprise2 = float(np.clip((result_points2 - expected_points2) / 3.0, -1.0, 1.0))

        comp1 = self.performance_components_by_match_team.get((int(match["jogo"]), t1), {})
        comp2 = self.performance_components_by_match_team.get((int(match["jogo"]), t2), {})
        attack_perf1, defense_perf1 = safe_float(comp1.get("attack", 0), 0), safe_float(comp1.get("defense", 0), 0)
        attack_perf2, defense_perf2 = safe_float(comp2.get("attack", 0), 0), safe_float(comp2.get("defense", 0), 0)

        # Gols marcados: avalia produção ofensiva contra a força do adversário.
        offense_signal1 = float(np.clip((a1 - xg1) * opp_factor_for_t1 + attack_perf1 * 0.35, -2.0, 2.0))
        offense_signal2 = float(np.clip((a2 - xg2) * opp_factor_for_t2 + attack_perf2 * 0.35, -2.0, 2.0))
        # Gols sofridos: avalia defesa separadamente com qualidade do adversário.
        # Sofrer contra adversário forte reduz a punição; segurar adversário forte aumenta o mérito.
        defense_signal1 = float(np.clip(defensive_gap_adjusted_signal(xg2 - a2, opp_quality_for_t1) + defense_perf1 * 0.35, -2.0, 2.0))
        defense_signal2 = float(np.clip(defensive_gap_adjusted_signal(xg1 - a1, opp_quality_for_t2) + defense_perf2 * 0.35, -2.0, 2.0))

        perf_total1 = float(np.clip(perf1 * 0.035, -0.12, 0.12))
        perf_total2 = float(np.clip(perf2 * 0.035, -0.12, 0.12))
        update1 = float(np.clip(
            0.85 * (0.52 * result_surprise1 + 0.24 * offense_signal1 + 0.24 * defense_signal1) + perf_total1,
            -1.55, 1.55
        ))
        update2 = float(np.clip(
            0.85 * (0.52 * result_surprise2 + 0.24 * offense_signal2 + 0.24 * defense_signal2) + perf_total2,
            -1.55, 1.55
        ))

        s1.rating_dynamic = float(np.clip(s1.rating_dynamic + update1, 25, 95))
        s2.rating_dynamic = float(np.clip(s2.rating_dynamic + update2, 25, 95))
        # Momentum com decaimento jogo a jogo, sem misturar saldo bruto com desempenho.
        s1.momentum = float(np.clip(s1.momentum * 0.58 + (result_points1 - 1) * 0.30 + result_surprise1 * 0.22 + perf_total1, -2.5, 2.5))
        s2.momentum = float(np.clip(s2.momentum * 0.58 + (result_points2 - 1) * 0.30 + result_surprise2 * 0.22 + perf_total2, -2.5, 2.5))
        s1.performance_memory = float(np.clip(s1.performance_memory * 0.64 + perf1 * 0.045 + (attack_perf1 + defense_perf1) * 0.035, -2.0, 2.0))
        s2.performance_memory = float(np.clip(s2.performance_memory * 0.64 + perf2 * 0.045 + (attack_perf2 + defense_perf2) * 0.035, -2.0, 2.0))
        s1.offensive_form = float(np.clip(s1.offensive_form * 0.66 + offense_signal1 * 0.28, -2.4, 2.4))
        s2.offensive_form = float(np.clip(s2.offensive_form * 0.66 + offense_signal2 * 0.28, -2.4, 2.4))
        s1.defensive_form = float(np.clip(s1.defensive_form * 0.66 + defense_signal1 * 0.28, -2.4, 2.4))
        s2.defensive_form = float(np.clip(s2.defensive_form * 0.66 + defense_signal2 * 0.28, -2.4, 2.4))

        for st, gf, ga, points, opp_rating, opp_for, opp_ga_penalty in [
            (s1, a1, a2, result_points1, rating2_pre, opp_factor_for_t1, ga_penalty_t1),
            (s2, a2, a1, result_points2, rating1_pre, opp_factor_for_t2, ga_penalty_t2),
        ]:
            prev_games = st.games_validated
            st.games_validated += 1
            st.last_match_date = match.get("data_dt")
            st.goals_for += int(gf)
            st.goals_against += int(ga)
            st.points += int(points)
            st.schedule_strength = float(((st.schedule_strength * prev_games) + opp_rating) / max(1, st.games_validated))
            st.opponent_adjusted_points += float(points) * float(np.clip(opp_rating / 60.0, 0.72, 1.32))
            st.opponent_weighted_goals_for += float(gf) * opp_for
            st.opponent_weighted_goals_against += float(ga) * opp_ga_penalty

        rating_shift = update1 - update2

        # Registra este jogo como treino para a rede somente depois da validação.
        # Importante: usa as features capturadas na previsão pré-jogo, não o estado pós-jogo.
        feature_order = [
            "rating_diff", "base_rating_diff", "attack_vs_defense", "defense_vs_attack",
            "midfield_diff", "goalkeeper_diff", "experience_diff", "league_diff",
            "player_quality_diff", "intensity_diff", "possession_diff", "pressing_diff",
            "momentum_diff", "performance_memory_diff", "offensive_form_diff", "defensive_form_diff",
            "schedule_strength_diff", "opponent_adjusted_points_diff", "goals_for_rate_diff", "goals_against_rate_diff",
            "opponent_weighted_goals_for_diff", "opponent_weighted_goals_against_diff",
            "weighted_goals_for_rate_diff", "adjusted_goals_against_rate_diff",
            "rest_diff", "host_diff", "knockout", "round_group",
        ]
        features = [float(prediction.get(f"feature_{name}", 0.0)) for name in feature_order]
        label = 0 if real_out == "1" else 1 if real_out == "X" else 2
        self.history_features.append(features)
        self.history_labels.append(label)

        row = {
            "jogo": int(match["jogo"]),
            "data": str(match.get("data", "")),
            "fase": match.get("fase", ""),
            "grupo": match.get("grupo", ""),
            "equipe1": t1,
            "equipe2": t2,
            "placar_previsto": prediction["placar_previsto"],
            "placar_real": f"{a1}-{a2}" + (f" (pên. {penalty_score_real})" if penalty_score_real else ""),
            "vencedor_previsto": prediction["vencedor_previsto"],
            "vencedor_real": real_winner_manual if knockout_real_penalty else winner_name(t1, a1, t2, a2),
            "acertou_vencedor": "Sim" if winner_ok else "Não",
            "acertou_placar_exato": "Sim" if exact else "Não",
            "erro_total_gols": round(float(err_goals), 3),
            "erro_xg_total": round(float(err_xg), 3),
            "erro_saldo": round(float(err_margin), 3),
            "proximidade_0_100": round(float(proximity), 2),
            "impacto_desempenho_equipe1": round(float(perf1), 3),
            "impacto_desempenho_equipe2": round(float(perf2), 3),
            "peso_resultado_anterior_aplicado_equipe1": round(float(s1.momentum), 3),
            "peso_resultado_anterior_aplicado_equipe2": round(float(s2.momentum), 3),
            "ajuste_rating_equipe1": round(float(update1), 3),
            "ajuste_rating_equipe2": round(float(update2), 3),
            "ajuste_relativo_rating": round(float(rating_shift), 3),
            "ajuste_ofensivo_equipe1": round(float(offense_signal1), 3),
            "ajuste_ofensivo_equipe2": round(float(offense_signal2), 3),
            "ajuste_defensivo_equipe1": round(float(defense_signal1), 3),
            "ajuste_defensivo_equipe2": round(float(defense_signal2), 3),
            "peso_adversario_ofensivo_equipe1": round(float(opp_factor_for_t1), 3),
            "peso_adversario_ofensivo_equipe2": round(float(opp_factor_for_t2), 3),
            "peso_gol_sofrido_equipe1": round(float(ga_penalty_t1), 3),
            "peso_gol_sofrido_equipe2": round(float(ga_penalty_t2), 3),
            "qualidade_adversario_equipe1": round(float(opp_quality_for_t1), 3),
            "qualidade_adversario_equipe2": round(float(opp_quality_for_t2), 3),
            "rating_pos_jogo_equipe1": round(float(s1.rating_dynamic), 3),
            "rating_pos_jogo_equipe2": round(float(s2.rating_dynamic), 3),
            "fonte_resultado": real_row.get("fonte", ""),
        }
        return row

    def run(self) -> None:
        real_by_game = {int(r["jogo"]): r for _, r in self.real_results.iterrows()}
        current_date = None
        day_pred = day_val = 0
        day_winner_ok = []
        day_exact = []
        day_err = []

        def flush_day(date_value):
            nonlocal day_pred, day_val, day_winner_ok, day_exact, day_err
            if date_value is None:
                return
            self.daily_rows.append({
                "data": str(date_value.date() if hasattr(date_value, "date") else date_value),
                "jogos_previstos": day_pred,
                "jogos_validados": day_val,
                "acuracia_vencedor_%": round(float(np.mean(day_winner_ok) * 100), 2) if day_winner_ok else "",
                "placar_exato_%": round(float(np.mean(day_exact) * 100), 2) if day_exact else "",
                "erro_medio_total_gols": round(float(np.mean(day_err)), 3) if day_err else "",
            })
            day_pred = day_val = 0
            day_winner_ok = []
            day_exact = []
            day_err = []

        for _, match in self.matches.iterrows():
            dt = match.get("data_dt")
            if current_date is None:
                current_date = dt
            elif pd.notna(dt) and pd.notna(current_date) and dt.date() != current_date.date():
                flush_day(current_date)
                current_date = dt

            pred = self.predict_match(match)
            self.predictions.append(pred)
            day_pred += 1

            real_row = real_by_game.get(int(match["jogo"]))
            if real_row is not None:
                val = self.validate_and_update(match, pred, real_row)
                self.validations.append(val)
                day_val += 1
                day_winner_ok.append(1 if val["acertou_vencedor"] == "Sim" else 0)
                day_exact.append(1 if val["acertou_placar_exato"] == "Sim" else 0)
                day_err.append(val["erro_total_gols"])
            else:
                # Mesmo sem resultado, atualiza data do último jogo apenas em jogos com real? Não.
                pass
        flush_day(current_date)

    def export(self) -> None:
        pred_df = pd.DataFrame(self.predictions)
        val_df = pd.DataFrame(self.validations)
        day_df = pd.DataFrame(self.daily_rows)
        state_rows = []
        for team, st in sorted(self.states.items(), key=lambda kv: kv[1].rating_dynamic, reverse=True):
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

        pred_df.to_csv(OUT_DIR / "previsoes_dia_a_dia.csv", index=False, encoding="utf-8-sig")
        val_df.to_csv(OUT_DIR / "validacao_dia_a_dia.csv", index=False, encoding="utf-8-sig")
        day_df.to_csv(OUT_DIR / "resumo_diario_validacao.csv", index=False, encoding="utf-8-sig")
        state_df.to_csv(OUT_DIR / "estado_times_dia_a_dia.csv", index=False, encoding="utf-8-sig")
        self.features_team.to_csv(OUT_DIR / "features_times_iniciais.csv", index=False, encoding="utf-8-sig")

        if not val_df.empty:
            metrics = {
                "modelo": "neural incremental + prior Poisson contextual",
                "usa_previsoes_anteriores_como_entrada": False,
                "usa_simulacoes_anteriores_como_entrada": False,
                "validacao_sem_vazamento": True,
                "jogos_previstos": int(len(pred_df)),
                "jogos_com_placar_real_validado": int(len(val_df)),
                "acuracia_vencedor_percentual": round(float((val_df["acertou_vencedor"] == "Sim").mean() * 100), 2),
                "placar_exato_percentual": round(float((val_df["acertou_placar_exato"] == "Sim").mean() * 100), 2),
                "erro_medio_total_gols": round(float(val_df["erro_total_gols"].mean()), 3),
                "erro_medio_xg_total": round(float(val_df["erro_xg_total"].mean()), 3),
                "proximidade_media_0_100": round(float(val_df["proximidade_0_100"].mean()), 2),
                "dias_validados": int((pd.to_numeric(day_df.get("jogos_validados", pd.Series(dtype=int)), errors="coerce").fillna(0) > 0).sum()),
                "peso_resultado_anterior": "momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time",
                "peso_desempenho": "menções de jogadores/desempenho entram somente após o jogo validado",
                "gols_separados": "gols marcados atualizam forma ofensiva; gols sofridos atualizam forma defensiva com dano ajustado pela força ofensiva/rating do adversário; saldo não é usado como atalho principal",
                "peso_adversario": "resultado e gols marcados são valorizados contra adversários fortes; gols sofridos contra adversários fortes têm punição reduzida e contra fracos têm punição maior",
                "rede_neural_como_calibrador": "rede neural tem peso máximo de 8% e não pode inverter favorito quando xG/rating dão vantagem clara ao outro lado",
                "placar_representativo": "placar exibido é escolhido dentro do resultado mais provável, considerando probabilidade, xG, margem e variação determinística; o placar modal bruto é preservado em placar_modal_bruto",
                "probabilidade_penaltis": "em mata-mata calcula P(pênaltis) como P(empate em 90 minutos) vezes P(empate na prorrogação aproximada por xG/3)",
                "rede_neural": "MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual",
                "sklearn_disponivel": SKLEARN_AVAILABLE,
                "neural_min_samples": self.neural_min_samples,
                "simulations_parameter": self.simulations,
            }
        else:
            metrics = {"jogos_previstos": int(len(pred_df)), "jogos_com_placar_real_validado": 0}

        with (OUT_DIR / "metricas_modelo.json").open("w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

        js = "window.WC2026_MODELO_DIARIO_PREVISOES = " + json.dumps(pred_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
        js += "window.WC2026_MODELO_DIARIO_VALIDACAO = " + json.dumps(val_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
        js += "window.WC2026_MODELO_DIARIO_ESTADO_TIMES = " + json.dumps(state_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
        js += "window.WC2026_MODELO_DIARIO_RESUMO = " + json.dumps(day_df.fillna("").to_dict(orient="records"), ensure_ascii=False) + ";\n"
        js += "window.WC2026_MODELO_DIARIO_METRICAS = " + json.dumps(metrics, ensure_ascii=False) + ";\n"
        (self.root / "src" / "modelo-diario-data.js").write_text(js, encoding="utf-8")

        self.write_report(metrics, pred_df, val_df, day_df, state_df)

    def write_report(self, metrics: dict, pred_df: pd.DataFrame, val_df: pd.DataFrame, day_df: pd.DataFrame, state_df: pd.DataFrame) -> None:
        top_teams = state_df.head(12)[["selecao", "rating_atual_0_100", "momentum_resultado_anterior", "jogos_validados", "saldo"]].to_dict(orient="records") if not state_df.empty else []
        last_predictions = pred_df.tail(12)[["jogo", "data", "equipe1", "equipe2", "placar_previsto", "vencedor_previsto", "confianca_modelo"]].to_dict(orient="records") if not pred_df.empty else []
        lines = []
        lines.append("# Modelo neural diário — Copa 2026\n")
        lines.append("Este modelo foi gerado para prever jogo a jogo sem usar previsões ou simulações anteriores como entrada.\n")
        lines.append("\n## O que o script faz\n")
        lines.append("1. Lê elenco, força, estilo tático, calendário e árbitros agregados.\n")
        lines.append("2. Ordena os jogos por data e número do jogo.\n")
        lines.append("3. Antes de cada partida, gera xG, placar provável e probabilidades.\n")
        lines.append("4. Depois da previsão, se existir placar real, valida e atualiza rating/momentum/desempenho.\n")
        lines.append("5. O resultado anterior da seleção pesa nos próximos jogos do mesmo time.\n")
        lines.append("\n## Arquivos gerados\n")
        for filename in [
            "features_times_iniciais.csv",
            "previsoes_dia_a_dia.csv",
            "validacao_dia_a_dia.csv",
            "resumo_diario_validacao.csv",
            "estado_times_dia_a_dia.csv",
            "metricas_modelo.json",
            "../../src/modelo-diario-data.js",
        ]:
            lines.append(f"- `{filename}`\n")
        lines.append("\n## Métricas da rodada atual\n")
        for k, v in metrics.items():
            lines.append(f"- **{k}**: {v}\n")
        lines.append("\n## Times com maior rating atualizado\n")
        for row in top_teams:
            lines.append(f"- {row['selecao']}: {row['rating_atual_0_100']} | momentum {row['momentum_resultado_anterior']} | jogos {row['jogos_validados']} | saldo {row['saldo']}\n")
        lines.append("\n## Últimas previsões processadas\n")
        for row in last_predictions:
            lines.append(f"- Jogo {row['jogo']} ({row['data']}): {row['equipe1']} x {row['equipe2']} → {row['placar_previsto']} / {row['vencedor_previsto']} ({row['confianca_modelo']})\n")
        lines.append("\n## Observação importante\n")
        lines.append("Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.\n")
        (OUT_DIR / "README_MODELO_DIARIO.md").write_text("".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda o modelo neural/incremental diário da Copa 2026.")
    parser.add_argument("--simulations", type=int, default=8000, help="Parâmetro reservado para interações/compatibilidade; probabilidades usam Poisson analítico.")
    parser.add_argument("--neural-min-samples", type=int, default=16, help="Mínimo de jogos reais anteriores para ativar a calibração MLP.")
    args = parser.parse_args()

    model = DailyWorldCupModel(ROOT, simulations=args.simulations, neural_min_samples=args.neural_min_samples)
    model.load()
    model.run()
    model.export()
    print(f"Modelo diário gerado em: {OUT_DIR}")


if __name__ == "__main__":
    main()
