from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .io import find_column, normalize_text, safe_float


def build_team_match_frame(results: pd.DataFrame, stats: pd.DataFrame, events: pd.DataFrame | None = None, performance: pd.DataFrame | None = None) -> pd.DataFrame:
    rid = find_column(results, "jogo", "match_id")
    t1 = find_column(results, "equipe1", "team1"); t2 = find_column(results, "equipe2", "team2")
    g1 = find_column(results, "gols1_real", "gols1"); g2 = find_column(results, "gols2_real", "gols2")
    sid = find_column(stats, "jogo", "match_id")
    steam = find_column(stats, "team_norm", "team", "team_espn", "selecao")
    if not all([rid, t1, t2, g1, g2, sid, steam]):
        return pd.DataFrame()
    result_map: dict[int, dict[str, Any]] = {}
    for _, row in results.iterrows():
        try:
            mid = int(row[rid]); score1 = int(row[g1]); score2 = int(row[g2])
        except (TypeError, ValueError):
            continue
        result_map[mid] = {"team1": normalize_text(row[t1]), "team2": normalize_text(row[t2]), "g1": score1, "g2": score2}
    frame = stats.copy()
    frame["match_id"] = pd.to_numeric(frame[sid], errors="coerce")
    frame["team_key"] = frame[steam].map(normalize_text)
    frame = frame[frame["match_id"].notna()].copy()
    outcome=[]; points=[]; goals_for=[]; goals_against=[]
    for _, row in frame.iterrows():
        match = result_map.get(int(row["match_id"]))
        if not match or row["team_key"] not in {match["team1"], match["team2"]}:
            outcome.append(np.nan); points.append(np.nan); goals_for.append(np.nan); goals_against.append(np.nan); continue
        is_team1 = row["team_key"] == match["team1"]
        gf = match["g1"] if is_team1 else match["g2"]
        ga = match["g2"] if is_team1 else match["g1"]
        outcome.append(1 if gf > ga else -1 if gf < ga else 0)
        points.append(3 if gf > ga else 1 if gf == ga else 0)
        goals_for.append(gf); goals_against.append(ga)
    frame["outcome"] = outcome; frame["points"] = points; frame["goals_for"] = goals_for; frame["goals_against"] = goals_against

    if events is not None and not events.empty:
        eid = find_column(events, "jogo", "match_id"); eteam = find_column(events, "team", "team_norm", "team_espn")
        scoring = find_column(events, "scoring_play"); shootout = find_column(events, "shootout")
        if eid and eteam:
            candidates = events.copy()
            if scoring:
                candidates = candidates[candidates[scoring].astype(str).str.lower().isin({"true", "1", "sim"})]
            if shootout:
                candidates = candidates[~candidates[shootout].astype(str).str.lower().isin({"true", "1", "sim"})]
            candidates = candidates[candidates[eteam].notna()]
            first_goal: dict[int, str] = {}
            for _, event in candidates.iterrows():
                try: mid=int(event[eid])
                except (TypeError, ValueError): continue
                first_goal.setdefault(mid, normalize_text(event[eteam]))
            frame["first_goal"] = [1.0 if first_goal.get(int(mid)) == team else 0.0 if int(mid) in first_goal else np.nan for mid, team in zip(frame["match_id"], frame["team_key"])]

    if performance is not None and not performance.empty:
        pid = find_column(performance, "jogo", "match_id"); pteam = find_column(performance, "selecao", "team")
        if pid and pteam:
            perf = performance.copy(); perf["match_id"] = pd.to_numeric(perf[pid], errors="coerce"); perf["team_key"] = perf[pteam].map(normalize_text)
            wanted = [col for col in [find_column(perf, "xg_pro"), find_column(perf, "xg_contra"), find_column(perf, "indice_desempenho_geral")] if col]
            if wanted:
                agg=perf.groupby(["match_id","team_key"],as_index=False)[wanted].mean(numeric_only=True)
                frame=frame.merge(agg,on=["match_id","team_key"],how="left",suffixes=("","_performance"))
    return frame


def correlation(x: pd.Series, y: pd.Series) -> tuple[float | None, int]:
    pair = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(pair) < 3 or pair["x"].std(ddof=0) == 0 or pair["y"].std(ddof=0) == 0:
        return None, len(pair)
    return float(pair["x"].corr(pair["y"])), len(pair)


def evidence_confidence(corr: float, n: int) -> float:
    return round(float(min(0.99, max(0.0, 1.0 - math.exp(-abs(corr) * math.sqrt(max(n, 1)))))), 6)
