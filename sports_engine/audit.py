from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from .config import ROOT
from .io import read_table, utc_now, write_json


def run(output: Path | None = None) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    by_hash: dict[str, list[str]] = {}
    problems: list[dict[str, Any]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        blob = path.read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
        rel = path.relative_to(ROOT).as_posix()
        files.append({"path": rel, "size_bytes": len(blob), "sha256": sha})
        by_hash.setdefault(sha, []).append(rel)
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                problems.append({"path": rel, "type": "python_syntax_error", "severity": "critical", "details": str(exc)})
        if path.suffix == ".csv":
            try:
                read_table(path)
            except Exception as exc:
                problems.append({"path": rel, "type": "csv_parse_error", "severity": "high", "details": str(exc)})
    duplicates = [
        {"sha256": sha, "files": paths}
        for sha, paths in by_hash.items() if len(paths) > 1
    ]
    report = {
        "generated_at": utc_now(),
        "audit_scope": "current repository",
        "summary": {"files_analyzed": len(files), "problems_found": len(problems), "duplicate_groups": len(duplicates)},
        "files_analyzed": files,
        "problems_found": problems,
        "duplications": duplicates,
        "risks": [
            "Generated compatibility copies must remain synchronized.",
            "External enrichment depends on availability and terms of configured sources.",
            "Player-level match data remains incomplete until a reliable source is configured.",
        ],
        "suggestions": [
            "Use competition-specific data directories for new seasons.",
            "Keep observed, derived and synthetic fields explicitly labeled.",
            "Review source adapters whenever an upstream API schema changes.",
        ],
    }
    write_json(report, output or ROOT / "reports" / "repository_audit.json")
    return report
