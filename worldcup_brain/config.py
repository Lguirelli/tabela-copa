from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "worldcup_temporal.yaml"


@dataclass(frozen=True)
class TemporalConfig:
    data: dict[str, Any]
    root: Path = ROOT

    def path(self, name: str) -> Path:
        value = self.data.get("paths", {}).get(name)
        if not value:
            raise KeyError(f"Path '{name}' is not configured")
        return self.root / str(value)

    def output(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def load_config(path: Path | str = DEFAULT_CONFIG) -> TemporalConfig:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    required = ["competition_id", "pre_tournament_cutoff", "paths"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"Missing temporal configuration keys: {missing}")
    return TemporalConfig(payload)
