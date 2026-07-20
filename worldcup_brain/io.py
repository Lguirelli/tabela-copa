from __future__ import annotations

import hashlib
import json
import os
import math
import numpy as np
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    frame.columns = [str(col).replace("\ufeff", "").strip() for col in frame.columns]
    return frame


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        frame.to_csv(handle.name, index=False, na_rep="NA")
        temp = Path(handle.name)
    os.replace(temp, path)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float,)):
        return value if math.isfinite(value) else "NA"
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else "NA"
    if isinstance(value, np.integer):
        return int(value)
    if value is pd.NA or value is None:
        return "NA" if value is pd.NA else None
    return value


def atomic_write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = _json_safe(payload)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(safe_payload, handle, ensure_ascii=False, indent=2, allow_nan=False, default=str)
        handle.write("\n")
        temp = Path(handle.name)
    os.replace(temp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lineage(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists() and path.is_file():
            rows.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            })
    return rows
