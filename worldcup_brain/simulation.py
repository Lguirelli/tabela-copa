from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from .config import TemporalConfig
from .model import TemporalPoissonEloModel
from .temporal import parse_timestamp


def _points(g1: np.ndarray, g2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    p1 = np.where(g1 > g2, 3, np.where(g1 == g2, 1, 0))
    p2 = np.where(g2 > g1, 3, np.where(g1 == g2, 1, 0))
    return p1, p2


def simulate_group_stage(
    config: TemporalConfig,
    timeline: pd.DataFrame,
    model: TemporalPoissonEloModel,
    cutoff: Any,
    iterations: int,
) -> dict[str, Any]:
    cutoff_ts = parse_timestamp(cutoff)
    group_matches = timeline[timeline["match_id"] <= 72].copy()
    teams = sorted(set(group_matches["team1"]).union(set(group_matches["team2"])))
    team_index = {team: idx for idx, team in enumerate(teams)}
    n = len(teams)
    points = np.zeros((iterations, n), dtype=np.int16)
    gd = np.zeros((iterations, n), dtype=np.int16)
    gf = np.zeros((iterations, n), dtype=np.int16)
    rng = np.random.default_rng(int(config.get("random_seed", 2026)) + int(cutoff_ts.timestamp()) % 100000)

    for _, match in group_matches.iterrows():
        i1, i2 = team_index[str(match["team1"])], team_index[str(match["team2"])]
        if parse_timestamp(match["result_available_at"]) <= cutoff_ts:
            g1 = np.full(iterations, int(match["result_team1_goals"]), dtype=np.int16)
            g2 = np.full(iterations, int(match["result_team2_goals"]), dtype=np.int16)
        else:
            pred = model.predict(str(match["team1"]), str(match["team2"]), match["kickoff_at"], False)
            g1 = rng.poisson(float(pred["expected_goals_team1"]), iterations).astype(np.int16)
            g2 = rng.poisson(float(pred["expected_goals_team2"]), iterations).astype(np.int16)
        p1, p2 = _points(g1, g2)
        points[:, i1] += p1; points[:, i2] += p2
        gf[:, i1] += g1; gf[:, i2] += g2
        gd[:, i1] += g1 - g2; gd[:, i2] += g2 - g1

    groups: dict[str, list[str]] = {}
    for group, frame in group_matches.groupby("group", dropna=False):
        if str(group) in {"nan", "NA"}:
            continue
        groups[str(group)] = sorted(set(frame["team1"]).union(set(frame["team2"])))

    position_counts = {team: Counter() for team in teams}
    top_two_counts = Counter()
    third_rows: list[list[tuple[str, int, int, int]]] = [[] for _ in range(iterations)]
    for group, group_teams in groups.items():
        indices = [team_index[team] for team in group_teams]
        for it in range(iterations):
            order = sorted(indices, key=lambda idx: (points[it, idx], gd[it, idx], gf[it, idx], teams[idx]), reverse=True)
            for pos, idx in enumerate(order, start=1):
                position_counts[teams[idx]][pos] += 1
                if pos <= 2:
                    top_two_counts[teams[idx]] += 1
            if len(order) >= 3:
                idx = order[2]
                third_rows[it].append((teams[idx], int(points[it, idx]), int(gd[it, idx]), int(gf[it, idx])))

    best_third_counts = Counter()
    for rows in third_rows:
        rows.sort(key=lambda item: (item[1], item[2], item[3], item[0]), reverse=True)
        for team, *_ in rows[:8]:
            best_third_counts[team] += 1

    qualifications = []
    for team in teams:
        group_value = next((group for group, group_teams in groups.items() if team in group_teams), "NA")
        top2 = top_two_counts[team] / iterations
        best3 = best_third_counts[team] / iterations
        qualifications.append({
            "team": team,
            "group": group_value,
            "probability_first": round(position_counts[team][1] / iterations, 6),
            "probability_second": round(position_counts[team][2] / iterations, 6),
            "probability_third": round(position_counts[team][3] / iterations, 6),
            "probability_top_two": round(top2, 6),
            "probability_best_third": round(best3, 6),
            "probability_qualify": round(min(1.0, top2 + best3), 6),
        })
    return {
        "iterations": iterations,
        "cutoff": cutoff_ts.isoformat(),
        "qualification_probabilities": sorted(qualifications, key=lambda item: item["probability_qualify"], reverse=True),
    }


def _actual_advancer(match: pd.Series) -> str:
    penalty = str(match.get("penalty_winner", "NA"))
    if penalty not in {"NA", "nan", "", "None"}:
        return penalty
    winner = str(match.get("result_winner", "NA"))
    if winner not in {"Empate", "NA", "nan", ""}:
        return winner
    g1, g2 = int(match["result_team1_goals"]), int(match["result_team2_goals"])
    return str(match["team1"] if g1 > g2 else match["team2"])


def simulate_knockout(
    config: TemporalConfig,
    timeline: pd.DataFrame,
    model: TemporalPoissonEloModel,
    cutoff: Any,
    iterations: int,
) -> dict[str, Any]:
    cutoff_ts = parse_timestamp(cutoff)
    group_end = parse_timestamp(timeline.loc[timeline["match_id"] == 72, "result_available_at"].iloc[0])
    if cutoff_ts < group_end:
        return {
            "status": "UNRESOLVED_GROUP_STAGE",
            "reason": "Round-of-32 teams are intentionally hidden until all group-stage results are available.",
            "champion_probabilities": "NA",
        }
    parent_map = {int(key): [int(value) for value in values] for key, values in config.get("bracket_parents", {}).items()}
    matches = {int(row["match_id"]): row for _, row in timeline[timeline["match_id"] >= 73].iterrows()}
    order = list(range(73, 89)) + [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104]
    rng = np.random.default_rng(int(config.get("random_seed", 2026)) + int(cutoff_ts.timestamp()) % 99991)
    champions = Counter(); finalists = Counter(); semifinalists = Counter()
    cache: dict[tuple[str, str], float] = {}

    def advance_probability(team1: str, team2: str, match: pd.Series) -> float:
        key = (team1, team2)
        if key not in cache:
            pred = model.predict(team1, team2, match["kickoff_at"], True)
            cache[key] = float(pred["probability_team1_advance"])
        return cache[key]

    for _ in range(iterations):
        winners: dict[int, str] = {}
        losers: dict[int, str] = {}
        for match_id in order:
            match = matches[match_id]
            if match_id <= 88:
                team1, team2 = str(match["team1"]), str(match["team2"])
            elif match_id == 103:
                team1, team2 = losers[101], losers[102]
            else:
                parents = parent_map[match_id]
                team1, team2 = winners[parents[0]], winners[parents[1]]
            if parse_timestamp(match["result_available_at"]) <= cutoff_ts:
                winner = _actual_advancer(match)
                # For derived rounds, official team identity is safe because the result is already visible.
                if winner not in {team1, team2}:
                    winner = str(match["team1"] if normalize_name(match["team1"]) == normalize_name(winner) else match["team2"])
            else:
                p_team1 = advance_probability(team1, team2, match)
                winner = team1 if rng.random() < p_team1 else team2
            loser = team2 if winner == team1 else team1
            winners[match_id] = winner; losers[match_id] = loser
            if match_id in {97, 98, 99, 100}:
                semifinalists[winner] += 1
            if match_id in {101, 102}:
                finalists[winner] += 1
        champions[winners[104]] += 1

    teams = sorted(set(champions) | set(finalists) | set(semifinalists))
    return {
        "status": "AVAILABLE",
        "iterations": iterations,
        "champion_probabilities": sorted([
            {
                "team": team,
                "probability_champion": round(champions[team] / iterations, 6),
                "probability_final": round(finalists[team] / iterations, 6),
                "probability_semifinal": round(semifinalists[team] / iterations, 6),
            }
            for team in teams
        ], key=lambda item: item["probability_champion"], reverse=True),
    }


def normalize_name(value: Any) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()


def run_daily_simulation(config: TemporalConfig, timeline: pd.DataFrame, model: TemporalPoissonEloModel, cutoff: Any) -> dict[str, Any]:
    iterations = int(config.get("simulation_iterations", 4000))
    return {
        "competition_id": config.get("competition_id"),
        "cutoff": parse_timestamp(cutoff).isoformat(),
        "temporal_integrity": "Only results with result_available_at <= cutoff are fixed; future matches are sampled.",
        "group_stage": simulate_group_stage(config, timeline, model, cutoff, iterations),
        "knockout": simulate_knockout(config, timeline, model, cutoff, iterations),
    }
