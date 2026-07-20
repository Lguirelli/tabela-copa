from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .config import TemporalConfig
from .io import atomic_write_json, sha256, utc_now


def run(config: TemporalConfig) -> dict[str, Any]:
    files = [path for path in config.root.rglob("*") if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts]
    by_extension: dict[str, int] = defaultdict(int)
    hash_groups: dict[str, list[str]] = defaultdict(list)
    for path in files:
        by_extension[path.suffix.lower() or "<none>"] += 1
        if path.stat().st_size <= 5_000_000:
            hash_groups[sha256(path)].append(path.relative_to(config.root).as_posix())
    duplicates = [paths for paths in hash_groups.values() if len(paths) > 1]
    temporal_inputs = [
        config.path("matches"), config.path("results"), config.path("team_strengths"),
        config.path("team_tactics"), config.path("players"), config.path("events"),
        config.path("team_match_stats"), config.path("lineups"),
        config.path("player_match_stats"), config.path("player_availability"),
        config.path("commentary"), config.path("match_officials"), config.path("validated_results"),
    ]
    issues = [
        {
            "id": "NO_AS_OF_CONTROL_IN_LEGACY_MODEL",
            "severity": "high",
            "status": "MITIGATED_BY_TEMPORAL_LAYER",
            "description": "Legacy prediction artifacts combine final results and model fields without a formal per-record knowledge cutoff.",
        },
        {
            "id": "KNOCKOUT_TEAM_LEAKAGE_RISK",
            "severity": "high",
            "status": "MITIGATED_BY_FIXTURE_KNOWN_AT",
            "description": "The finalized match table contains future knockout teams; historical replay must hide them until parent results are available.",
        },
        {
            "id": "PRE_TOURNAMENT_SOURCE_TIMESTAMPS_MISSING",
            "severity": "high",
            "status": "OPEN_LIMITATION",
            "description": "Ranking, recent form, injuries and recent player minutes do not have archived publication timestamps and remain NA.",
        },
        {
            "id": "PLAYER_MINUTES_AND_AVAILABILITY_INCOMPLETE",
            "severity": "medium",
            "status": "OPEN_LIMITATION",
            "description": "Observed lineups and player statistics cover all matches, but minutes, xG, xA, ratings and historical player availability remain unavailable.",
        },
        {
            "id": "POST_MATCH_FACTS_BACKFILLED",
            "severity": "medium",
            "status": "CONTROLLED",
            "description": "Some events and team statistics were collected after their matches; they are labeled as backfilled post-match facts and cannot enter pre-match snapshots.",
        },
        {
            "id": "MULTIPLE_PREDICTION_SYSTEMS",
            "severity": "medium",
            "status": "DOCUMENTED",
            "description": "Legacy daily/neural predictions are preserved for compatibility; the temporal engine writes to separate predictions, learning and model-version directories.",
        },
    ]
    payload = {
        "generated_at": utc_now(),
        "repository_root": config.root.name,
        "files_analyzed": len(files),
        "files_by_extension": dict(sorted(by_extension.items())),
        "temporal_input_files": [
            {
                "path": path.relative_to(config.root).as_posix(),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sha256": sha256(path) if path.exists() else "NA",
            }
            for path in temporal_inputs
        ],
        "problems_found": issues,
        "duplicate_content_groups": duplicates[:50],
        "duplicate_note": "Exact duplicates are reported for audit only; compatibility mirrors and asset variants are not removed automatically.",
        "implemented_improvements": [
            "pre-tournament state with field-level temporal status",
            "event-driven historical replay",
            "fixture visibility control for knockout rounds",
            "pre-match knowledge ledger",
            "missing-information queue and timestamp-safe collection",
            "online Elo/Poisson learning and conservative recalibration",
            "post-match error, causal-association and significance analyses",
            "complete ESPN event, commentary, team-stat, player-stat, lineup and main-referee coverage",
            "statistical feature discovery with permutation evidence",
            "daily model versions and Monte Carlo simulations",
            "temporal validation tests and GitHub Actions",
        ],
        "risk_summary": {
            "blocking_unmitigated": 0,
            "open_data_limitations": 2,
            "controlled_or_mitigated": 4,
        },
    }
    atomic_write_json(payload, config.output("reports", "worldcup_temporal_repository_audit.json"))
    return payload
