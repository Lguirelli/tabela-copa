from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


NA_TOKENS = {"", "na", "n/a", "nan", "none", "null", "<na>"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_column(name: Any) -> str:
    return str(name).replace("\ufeff", "").strip()


def read_table(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    frame.columns = [normalize_column(col) for col in frame.columns]
    return frame


def write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        frame.to_csv(handle.name, index=False, na_rep="NA")
        temp = Path(handle.name)
    os.replace(temp, path)


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        temp = Path(handle.name)
    os.replace(temp, path)



def write_json_copies(payload: Any, primary: Path, *aliases: Path) -> None:
    """Atomically write a canonical JSON artifact and optional compatibility aliases."""
    write_json(payload, primary)
    for alias in aliases:
        if alias != primary:
            write_json(payload, alias)


def write_table_copies(frame: pd.DataFrame, primary: Path, *aliases: Path) -> None:
    """Atomically write a canonical table and optional compatibility aliases."""
    write_table(frame, primary)
    for alias in aliases:
        if alias != primary:
            write_table(frame, alias)

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_manifest(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    manifest = []
    for path in paths:
        if path.exists() and path.is_file():
            manifest.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
            })
    return manifest


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in NA_TOKENS


def normalize_text(value: Any) -> str:
    if is_missing(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().strip().split())


def find_column(frame: pd.DataFrame, *candidates: str) -> str | None:
    normalized = {normalize_text(col).replace(" ", "_"): col for col in frame.columns}
    for candidate in candidates:
        key = normalize_text(candidate).replace(" ", "_")
        if key in normalized:
            return normalized[key]
    return None


def safe_float(value: Any) -> float | None:
    if is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
