from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "competitions.yaml"
DEFAULT_REQUIRED_DATA = {
    "matches": [
        {"field": "result", "priority": "high", "provider_dataset": "results"},
        {"field": "date", "priority": "high", "provider_dataset": "matches"},
        {"field": "competition", "priority": "high", "provider_dataset": "configuration"},
        {"field": "lineup", "priority": "medium", "provider_dataset": "lineups"},
        {"field": "events", "priority": "medium", "provider_dataset": "events"},
        {"field": "statistics", "priority": "high", "provider_dataset": "team_match_stats"},
    ],
    "teams": [
        {"field": "recent_form", "priority": "high", "provider_dataset": "results", "derivable": True},
        {"field": "offensive_strength", "priority": "high", "provider_dataset": "results", "derivable": True},
        {"field": "defensive_strength", "priority": "high", "provider_dataset": "results", "derivable": True},
        {"field": "history", "priority": "medium", "provider_dataset": "results", "derivable": True},
    ],
    "players": [
        {"field": "minutes", "priority": "high", "provider_dataset": "player_match_stats"},
        {"field": "performance", "priority": "high", "provider_dataset": "player_match_stats"},
        {"field": "participation", "priority": "high", "provider_dataset": "lineups"},
        {"field": "availability", "priority": "medium", "provider_dataset": "player_availability"},
    ],
}


@dataclass(frozen=True)
class CompetitionConfig:
    competition_id: str
    data: dict[str, Any]
    engine: dict[str, Any]
    root: Path = ROOT

    @property
    def name(self) -> str:
        return str(self.data.get("name", self.competition_id))

    @property
    def season(self) -> str:
        return str(self.data.get("season", "NA"))

    def dataset(self, name: str) -> Path:
        value = self.data.get("datasets", {}).get(name)
        if not value:
            raise KeyError(f"Dataset '{name}' is not configured for {self.competition_id}")
        return self.root / str(value)

    def scoped_path(self, top_level: str, *parts: str) -> Path:
        """Return a competition-isolated artifact path under a repository domain."""
        return self.root / top_level / "competitions" / self.competition_id / Path(*parts)


def load_registry(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if "competitions" not in payload:
        raise ValueError("config/competitions.yaml must contain a competitions mapping")
    return payload


def load_competition(competition_id: str | None = None, path: Path | str = DEFAULT_CONFIG) -> CompetitionConfig:
    registry = load_registry(path)
    selected = competition_id or registry.get("active_competition")
    if not selected:
        raise ValueError("No competition selected and active_competition is not configured")
    competitions = registry["competitions"]
    if selected not in competitions:
        raise KeyError(f"Competition '{selected}' is not configured")
    import copy
    data = copy.deepcopy(competitions[selected])
    data.setdefault("required_data", copy.deepcopy(DEFAULT_REQUIRED_DATA))
    data.setdefault("sources", [])
    data.setdefault("final_statuses", ["Finalizado", "Finished", "FT"])
    if data.get("template"):
        raise ValueError(f"Competition '{selected}' is a template and cannot be executed")
    return CompetitionConfig(selected, data, registry.get("engine", {}))
