#!/usr/bin/env python3
"""Deterministic repository preflight for local runs and GitHub Actions.

`--check` never mutates the checkout and fails when deprecated canonical paths
reappear. Without `--check`, only the two known legacy input CSVs are archived;
code and directories are never moved silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "archive" / "legacy_inputs"
REPORT = ROOT / "reports" / "ci_preflight_report.json"
LEGACY_INPUTS = (
    ROOT / "data" / "atualizacoes_entrada_26-06.csv",
    ROOT / "data" / "atualizacoes_entrada_26-06_resultados_desempenho.csv",
)
DEPRECATED_LAYOUT = (
    ROOT / "neural_copa",
    ROOT / "scripts" / "atualizar_modelo.py",
    ROOT / "scripts" / "modelo_neural_diario.py",
    ROOT / "scripts" / "recalcular_chaveamento_completo.py",
    ROOT / "scripts" / "treinar_rede_neural_copa.py",
    ROOT / ".github" / "workflows" / "00_run_diagnostics.yml",
    ROOT / ".github" / "workflows" / "01_pre_worldcup_training.yml",
    ROOT / ".github" / "workflows" / "02_daily_tournament_simulation.yml",
    ROOT / ".github" / "workflows" / "03_post_match_learning.yml",
    ROOT / ".github" / "workflows" / "daily_update.yml",
    ROOT / ".github" / "workflows" / "model_training.yml",
    ROOT / ".github" / "workflows" / "post_match_update.yml",
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


def inspect_layout() -> list[str]:
    return [path.relative_to(ROOT).as_posix() for path in (*LEGACY_INPUTS, *DEPRECATED_LAYOUT) if path.exists()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate canonical repository paths")
    parser.add_argument("--check", action="store_true", help="Read-only validation; fail when deprecated paths exist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    actions: list[dict[str, str]] = []
    if not args.check:
        actions = [archive_legacy(path) for path in LEGACY_INPUTS if path.exists()]

    forbidden = inspect_layout()
    payload = {
        "status": "INVALID_LAYOUT" if forbidden else ("CLEANED" if actions else "CLEAN"),
        "mode": "check" if args.check else "cleanup",
        "forbidden_paths": forbidden,
        "actions": actions,
        "canonical_workflows": ["ci.yml", "update_pipeline.yml", "static.yml"],
        "legacy_location": "legacy/",
    }
<<<<<<< HEAD
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if not args.check:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != rendered:
            REPORT.write_text(rendered, encoding="utf-8")
=======
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != rendered:
        REPORT.write_text(rendered, encoding="utf-8")
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
    print(rendered, end="")
    return 1 if forbidden else 0


if __name__ == "__main__":
    raise SystemExit(main())
