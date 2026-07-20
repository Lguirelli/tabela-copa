from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from sports_engine.io import normalize_text


@dataclass
class TeamState:
    team: str
    initial_strength: float = 60.0
    rating: float = 1500.0
    attack_proxy: float = 5.5
    defense_proxy: float = 5.5
    goalkeeper_proxy: float = 5.5
    experience_proxy: float = 7.0
    games: int = 0
    points: int = 0
    goals_for: int = 0
    goals_against: int = 0
    recent_points: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    recent_goal_diffs: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    recent_opponent_ratings: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    last_result_available_at: str | None = None
    last_kickoff_at: str | None = None

    @property
    def form_points(self) -> float:
        return float(np.mean(self.recent_points)) if self.recent_points else 1.0

    @property
    def form_goal_diff(self) -> float:
        return float(np.mean(self.recent_goal_diffs)) if self.recent_goal_diffs else 0.0

    @property
    def schedule_strength(self) -> float:
        return float(np.mean(self.recent_opponent_ratings)) if self.recent_opponent_ratings else 1500.0

    def serializable(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("recent_points", "recent_goal_diffs", "recent_opponent_ratings"):
            payload[key] = list(payload[key])
        payload["form_points"] = self.form_points
        payload["form_goal_diff"] = self.form_goal_diff
        payload["schedule_strength"] = self.schedule_strength
        return payload


class TournamentState:
    def __init__(self, team_profiles: pd.DataFrame):
        self.teams: dict[str, TeamState] = {}
        for _, row in team_profiles.iterrows():
            team = str(row["team"])
            strength = _float(row.get("initial_strength_proxy"), 60.0)
            self.teams[normalize_text(team)] = TeamState(
                team=team,
                initial_strength=strength,
                rating=1500.0 + (strength - 60.0) * 10.0,
                attack_proxy=_float(row.get("attack_proxy"), 5.5),
                defense_proxy=_float(row.get("defense_proxy"), 5.5),
                goalkeeper_proxy=_float(row.get("goalkeeper_proxy"), 5.5),
                experience_proxy=_float(row.get("experience_proxy"), 7.0),
            )

    def get(self, team: str) -> TeamState:
        key = normalize_text(team)
        if key not in self.teams:
            self.teams[key] = TeamState(team=team)
        return self.teams[key]

    def snapshot(self) -> dict[str, Any]:
        return {state.team: state.serializable() for state in sorted(self.teams.values(), key=lambda item: item.team)}


def _float(value: Any, default: float) -> float:
    try:
        number = float(value)
        if np.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return default
