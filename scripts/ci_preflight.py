#!/usr/bin/env python3
"""Deterministic preflight for GitHub Actions runs.

It removes known legacy files from canonical data paths while preserving their
content under data/archive/legacy_inputs. The script uses only the standard
library so it can run before dependency installation.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "archive" / "legacy_inputs"
REPORT = ROOT / "reports" / "ci_preflight_report.json"
LEGACY_PATHS = (
    ROOT / "data" / "atualizacoes_entrada_26-06.csv",
    ROOT / "data" / "atualizacoes_entrada_26-06_resultados_desempenho.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_legacy(path: Path) -> dict[str, str]:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(path)
    canonical_archive = ARCHIVE / path.name

    if canonical_archive.exists() and sha256(canonical_archive) == source_hash:
        action = "removed_duplicate"
        archive_path = canonical_archive
    elif not canonical_archive.exists():
        shutil.copy2(path, canonical_archive)
        action = "archived_and_removed"
        archive_path = canonical_archive
    else:
        conflicts = ARCHIVE / "conflicts"
        conflicts.mkdir(parents=True, exist_ok=True)
        archive_path = conflicts / f"{path.stem}__{source_hash[:12]}{path.suffix}"
        if not archive_path.exists():
            shutil.copy2(path, archive_path)
        action = "archived_conflict_and_removed"

    path.unlink()
    return {
        "source": path.relative_to(ROOT).as_posix(),
        "archive": archive_path.relative_to(ROOT).as_posix(),
        "sha256": source_hash,
        "action": action,
    }


def main() -> int:
    actions = [archive_legacy(path) for path in LEGACY_PATHS if path.exists()]
    payload = {
        "status": "CLEANED" if actions else "CLEAN",
        "forbidden_paths": [path.relative_to(ROOT).as_posix() for path in LEGACY_PATHS],
        "actions": actions,
    }
    if actions:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != rendered:
            REPORT.write_text(rendered, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
