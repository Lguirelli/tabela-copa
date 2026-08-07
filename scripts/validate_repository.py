#!/usr/bin/env python3
"""Validate repository code, configs, structured data and controlled mirrors."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from sports_engine.config import ROOT
from sports_engine.io import read_table, utc_now, write_json

SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", "build", "dist"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    issues: list[dict[str, Any]] = []
    counts = {"python": 0, "yaml": 0, "json": 0, "csv": 0}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8-sig"))
                counts["python"] += 1
            elif path.suffix in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8-sig"))
                counts["yaml"] += 1
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8-sig"))
                counts["json"] += 1
            elif path.suffix == ".csv":
                read_table(path)
                counts["csv"] += 1
        except Exception as exc:
            issues.append({
                "status": "INVALID",
                "path": rel,
                "check": "parse",
                "details": f"{type(exc).__name__}: {exc}",
            })

    catalog_path = ROOT / "data" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    mirror_checks: list[dict[str, Any]] = []
    for domain, definition in catalog.get("datasets", {}).items():
        canonical_rel = definition.get("canonical")
        if not canonical_rel:
            continue
        canonical = ROOT / canonical_rel
        if not canonical.exists():
            issues.append({"status": "INVALID", "path": canonical_rel, "check": "canonical_exists", "details": f"Missing canonical dataset for {domain}"})
            continue
        canonical_sha = sha256(canonical)
        for mirror_rel in definition.get("mirrors", []):
            mirror = ROOT / mirror_rel
            matches = mirror.exists() and sha256(mirror) == canonical_sha
            mirror_checks.append({
                "domain": domain,
                "canonical": canonical_rel,
                "mirror": mirror_rel,
                "status": "VALID" if matches else "INVALID",
            })
            if not matches:
                issues.append({
                    "status": "INVALID",
                    "path": mirror_rel,
                    "check": "controlled_mirror",
                    "details": f"Mirror does not match {canonical_rel}",
                })

    required_artifacts = [
        "reports/repository_audit.json",
        "reports/validation_report.json",
        "reports/final_system_status.json",
        "data/queues/missing_data.json",
        "logs/enrichment_log.json",
        "models/patterns.json",
        "models/error_learning.json",
        "models/features_registry.json",
        "reports/derived_player_facts_report.json",
        "scripts/run_repository_pipeline.py",
        ".github/workflows/ci.yml",
        ".github/workflows/update_pipeline.yml",
        ".github/workflows/static.yml",
    ]
    missing_required = [rel for rel in required_artifacts if not (ROOT / rel).exists()]
    for rel in missing_required:
        issues.append({"status": "INVALID", "path": rel, "check": "required_artifact", "details": "Required platform artifact is missing"})

    report = {
        "generated_at": utc_now(),
        "status": "VALID" if not issues else "INVALID",
        "summary": {
            "parsed_files": counts,
            "controlled_mirrors_checked": len(mirror_checks),
            "issues": len(issues),
            "required_artifacts_checked": len(required_artifacts),
        },
        "mirror_checks": mirror_checks,
        "issues": issues,
        "duplicate_policy": {
            "controlled_dataset_mirrors": "allowed only when declared in data/catalog.json and byte-identical",
            "team_source_templates": "identical sources.md templates are documentation scaffolding, not competing data sources",
            "all_other_duplicate_sources_of_truth": "not allowed",
        },
    }
    write_json(report, ROOT / "reports" / "repository_integrity_report.json")
    print(json.dumps(report["summary"] | {"status": report["status"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
