from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import input_manifest, utc_now


def metadata(loop_name: str, competition_id: str, inputs: list[Path], root: Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "loop": loop_name,
        "competition_id": competition_id,
        "generated_at": utc_now(),
        "inputs": input_manifest(inputs, root),
    }
    if extra:
        payload.update(extra)
    return payload
