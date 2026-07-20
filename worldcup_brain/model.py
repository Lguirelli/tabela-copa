from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .state import TeamState, TournamentState


@dataclass
class ModelParameters:
    base_goals: float = 1.22
    rating_weight: float = 0.24
    attack_weight: float = 0.12
    defense_weight: float = 0.11
    form_weight: float = 0.10
    schedule_weight: float = 0.04
    rest_weight: float = 0.015
    experience_weight: float = 0.02
    goalkeeper_weight: float = 0.025
    probability_temperature: float = 1.0
    elo_k: float = 24.0
    learning_rate: float = 0.03

    def payload(self) -> dict[str, float]:
        return asdict(self)


class TemporalPoissonEloModel:
    def __init__(self, state: TournamentState, parameters: ModelParameters | None = None, random_seed: int = 2026):
        self.state = state
        self.parameters = parameters or ModelParameters()
        self.rng = np.random.default_rng(random_seed)

    def _rest_days(self, team: TeamState, kickoff_at: Any) -> float:
        if not team.last_kickoff_at:
            return 7.0
        delta = pd.Timestamp(kickoff_at) - pd.Timestamp(team.last_kickoff_at)
        return float(np.clip(delta.total_seconds() / 86400.0, 1.0, 14.0))

    def features(self, team1: str, team2: str, kickoff_at: Any, is_knockout: bool) -> dict[str, float]:
        s1, s2 = self.state.get(team1), self.state.get(team2)
        rest1, rest2 = self._rest_days(s1, kickoff_at), self._rest_days(s2, kickoff_at)
        return {
            "rating_diff": (s1.rating - s2.rating) / 100.0,
            "initial_strength_diff": (s1.initial_strength - s2.initial_strength) / 10.0,
            "attack_vs_defense": s1.attack_proxy - s2.defense_proxy,
            "defense_vs_attack": s1.defense_proxy - s2.attack_proxy,
            "goalkeeper_diff": s1.goalkeeper_proxy - s2.goalkeeper_proxy,
            "experience_diff": s1.experience_proxy - s2.experience_proxy,
            "form_points_diff": s1.form_points - s2.form_points,
            "form_goal_diff": s1.form_goal_diff - s2.form_goal_diff,
            "schedule_strength_diff": (s1.schedule_strength - s2.schedule_strength) / 100.0,
            "rest_diff": rest1 - rest2,
            "games_diff": float(s1.games - s2.games),
            "knockout": 1.0 if is_knockout else 0.0,
            "rest_days_team1": rest1,
            "rest_days_team2": rest2,
        }

    def expected_goals(self, features: dict[str, float]) -> tuple[float, float, dict[str, float]]:
        p = self.parameters
        shared_rating = p.rating_weight * features["rating_diff"]
        attack_term_1 = p.attack_weight * features["attack_vs_defense"]
        attack_term_2 = p.attack_weight * (-features["defense_vs_attack"])
        form_term = p.form_weight * (0.65 * features["form_goal_diff"] + 0.35 * features["form_points_diff"])
        schedule_term = p.schedule_weight * features["schedule_strength_diff"]
        rest_term = p.rest_weight * features["rest_diff"]
        experience_term = p.experience_weight * features["experience_diff"]
        goalkeeper_term = p.goalkeeper_weight * features["goalkeeper_diff"]
        knockout_suppression = -0.08 * features["knockout"]
        log_lambda1 = math.log(p.base_goals) + shared_rating + attack_term_1 + form_term + schedule_term + rest_term + experience_term + goalkeeper_term + knockout_suppression
        log_lambda2 = math.log(p.base_goals) - shared_rating + attack_term_2 - form_term - schedule_term - rest_term - experience_term - goalkeeper_term + knockout_suppression
        lambda1 = float(np.clip(math.exp(log_lambda1), 0.18, 4.2))
        lambda2 = float(np.clip(math.exp(log_lambda2), 0.18, 4.2))
        contributions = {
            "rating": shared_rating,
            "attack_team1": attack_term_1,
            "attack_team2": attack_term_2,
            "recent_form": form_term,
            "schedule_strength": schedule_term,
            "rest": rest_term,
            "experience": experience_term,
            "goalkeeper": goalkeeper_term,
            "knockout_suppression": knockout_suppression,
        }
        return lambda1, lambda2, contributions

    @staticmethod
    def _poisson_pmf(lam: float, goals: int) -> float:
        return math.exp(-lam) * lam**goals / math.factorial(goals)

    def score_distribution(self, lambda1: float, lambda2: float, max_goals: int = 8) -> list[dict[str, float]]:
        rows = []
        for g1 in range(max_goals + 1):
            p1 = self._poisson_pmf(lambda1, g1)
            for g2 in range(max_goals + 1):
                probability = p1 * self._poisson_pmf(lambda2, g2)
                rows.append({"score": f"{g1}-{g2}", "team1_goals": g1, "team2_goals": g2, "probability": probability})
        total = sum(row["probability"] for row in rows)
        for row in rows:
            row["probability"] /= total
        return sorted(rows, key=lambda row: row["probability"], reverse=True)

    def _temperature_scale(self, probabilities: np.ndarray) -> np.ndarray:
        temperature = max(0.4, float(self.parameters.probability_temperature))
        logits = np.log(np.clip(probabilities, 1e-12, 1.0)) / temperature
        logits -= logits.max()
        exp = np.exp(logits)
        return exp / exp.sum()

    def predict(self, team1: str, team2: str, kickoff_at: Any, is_knockout: bool) -> dict[str, Any]:
        features = self.features(team1, team2, kickoff_at, is_knockout)
        lambda1, lambda2, contributions = self.expected_goals(features)
        distribution = self.score_distribution(lambda1, lambda2)
        p1 = sum(item["probability"] for item in distribution if item["team1_goals"] > item["team2_goals"])
        pdra = sum(item["probability"] for item in distribution if item["team1_goals"] == item["team2_goals"])
        p2 = sum(item["probability"] for item in distribution if item["team1_goals"] < item["team2_goals"])
        scaled = self._temperature_scale(np.array([p1, pdra, p2], dtype=float))
        p1, pdra, p2 = map(float, scaled)
        outcomes = [(team1, p1), ("Empate", pdra), (team2, p2)]
        predicted_outcome, top_probability = max(outcomes, key=lambda item: item[1])
        penalty_team1 = float(1.0 / (1.0 + math.exp(-np.clip(
            0.010 * (self.state.get(team1).rating - self.state.get(team2).rating)
            + 0.18 * features["goalkeeper_diff"]
            + 0.08 * features["experience_diff"], -6.0, 6.0
        ))))
        advance_team1 = p1 + pdra * penalty_team1 if is_knockout else None
        advance_team2 = p2 + pdra * (1.0 - penalty_team1) if is_knockout else None
        predicted_advancer = (team1 if advance_team1 >= advance_team2 else team2) if is_knockout else "NA"
        top_scores = distribution[:8]
        modal = top_scores[0]
        data_margin = sorted([p1, pdra, p2], reverse=True)
        confidence = float(np.clip((data_margin[0] - data_margin[1]) * 2.2 + 0.35, 0.05, 0.95))
        return {
            "team1": team1,
            "team2": team2,
            "expected_goals_team1": round(lambda1, 6),
            "expected_goals_team2": round(lambda2, 6),
            "probability_team1_win": round(p1, 6),
            "probability_draw": round(pdra, 6),
            "probability_team2_win": round(p2, 6),
            "predicted_outcome": predicted_outcome,
            "predicted_score": modal["score"],
            "probability_team1_advance": round(float(advance_team1), 6) if advance_team1 is not None else "NA",
            "probability_team2_advance": round(float(advance_team2), 6) if advance_team2 is not None else "NA",
            "probability_team1_win_penalties": round(penalty_team1, 6) if is_knockout else "NA",
            "predicted_advancer": predicted_advancer,
            "confidence": round(confidence, 6),
            "features": {key: round(float(value), 6) for key, value in features.items()},
            "feature_contributions": {key: round(float(value), 6) for key, value in contributions.items()},
            "top_scorelines": [{**item, "probability": round(float(item["probability"]), 6)} for item in top_scores],
            "model_parameters": self.parameters.payload(),
        }

    def update_after_result(self, team1: str, team2: str, goals1: int, goals2: int, kickoff_at: Any, result_available_at: Any) -> dict[str, Any]:
        s1, s2 = self.state.get(team1), self.state.get(team2)
        pre_rating1, pre_rating2 = s1.rating, s2.rating
        expected1 = 1.0 / (1.0 + 10.0 ** ((pre_rating2 - pre_rating1) / 400.0))
        if goals1 > goals2:
            score1, points1, points2 = 1.0, 3, 0
        elif goals1 < goals2:
            score1, points1, points2 = 0.0, 0, 3
        else:
            score1, points1, points2 = 0.5, 1, 1
        margin_multiplier = math.log(abs(goals1 - goals2) + 1.0) + 1.0
        delta = self.parameters.elo_k * margin_multiplier * (score1 - expected1)
        s1.rating = float(np.clip(s1.rating + delta, 1100.0, 2000.0))
        s2.rating = float(np.clip(s2.rating - delta, 1100.0, 2000.0))
        for state, gf, ga, points, opponent_rating in (
            (s1, goals1, goals2, points1, pre_rating2),
            (s2, goals2, goals1, points2, pre_rating1),
        ):
            state.games += 1
            state.points += points
            state.goals_for += int(gf)
            state.goals_against += int(ga)
            state.recent_points.append(float(points))
            state.recent_goal_diffs.append(float(gf - ga))
            state.recent_opponent_ratings.append(float(opponent_rating))
            state.last_kickoff_at = pd.Timestamp(kickoff_at).isoformat()
            state.last_result_available_at = pd.Timestamp(result_available_at).isoformat()
        return {
            "team1_rating_before": round(pre_rating1, 6),
            "team2_rating_before": round(pre_rating2, 6),
            "team1_rating_after": round(s1.rating, 6),
            "team2_rating_after": round(s2.rating, 6),
            "rating_delta_team1": round(delta, 6),
            "rating_delta_team2": round(-delta, 6),
        }

    def recalibrate(self, evaluated_predictions: list[dict[str, Any]]) -> dict[str, Any]:
        if len(evaluated_predictions) < 8:
            return {"accepted": False, "reason": "insufficient_history", "samples": len(evaluated_predictions)}
        temperatures = [0.75, 0.85, 0.95, 1.0, 1.1, 1.2, 1.35]
        current = float(self.parameters.probability_temperature)

        def loss_for(temp: float) -> float:
            losses = []
            for item in evaluated_predictions:
                raw = np.array(item["raw_probabilities"], dtype=float)
                logits = np.log(np.clip(raw, 1e-12, 1.0)) / temp
                logits -= logits.max()
                probs = np.exp(logits); probs /= probs.sum()
                losses.append(-math.log(max(1e-12, probs[int(item["actual_index"])])))
            return float(np.mean(losses))

        current_loss = loss_for(current)
        candidates = [{"temperature": temp, "log_loss": loss_for(temp)} for temp in temperatures]
        best = min(candidates, key=lambda item: item["log_loss"])
        accepted = best["log_loss"] + 1e-9 < current_loss
        if accepted:
            self.parameters.probability_temperature = float(best["temperature"])
        # Goal baseline is updated conservatively from observed total goals, never future results.
        observed_mean = float(np.mean([item["total_goals"] for item in evaluated_predictions[-24:]])) / 2.0
        old_base = self.parameters.base_goals
        proposed_base = float(np.clip(0.92 * old_base + 0.08 * observed_mean, 0.75, 1.8))
        self.parameters.base_goals = proposed_base
        return {
            "accepted": accepted,
            "samples": len(evaluated_predictions),
            "previous_temperature": current,
            "selected_temperature": self.parameters.probability_temperature,
            "previous_log_loss": round(current_loss, 8),
            "selected_log_loss": round(best["log_loss"], 8),
            "candidate_temperatures": candidates,
            "base_goals_before": round(old_base, 8),
            "base_goals_after": round(proposed_base, 8),
            "observed_goals_per_team_recent": round(observed_mean, 8),
        }
