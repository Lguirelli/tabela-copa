#!/usr/bin/env python3
"""Single repository orchestrator used locally and by GitHub Actions.

The script serializes collection, enrichment, model updates, temporal replay,
validation, dashboard export and tests. It replaces the overlapping write
workflows that previously recalculated the same artifacts several times.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "pipeline" / "latest.json"
LOG_ROOT = ROOT / "logs" / "pipeline"
PRE_WORLD_CUP_CUTOFF = "2026-06-10T23:59:59-04:00"


@dataclass
class StepResult:
    name: str
    command: list[str]
    status: str
    exit_code: int
    duration_seconds: float
    log_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_cutoff() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _console_excerpt(output: str, limit: int = 6000) -> str:
    output = output.rstrip()
    if len(output) <= limit:
        return output
    head = output[: limit // 2]
    tail = output[-limit // 2 :]
    omitted = len(output) - len(head) - len(tail)
    return f"{head}\n\n... {omitted:,} characters omitted; full output is in the step log ...\n\n{tail}"


def execute(name: str, command: list[str], env: dict[str, str], log_dir: Path) -> StepResult:
    started = time.monotonic()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{len(list(log_dir.glob('*.log'))) + 1:02d}_{name}.log"
    timeout_seconds = max(60, int(env.get("PIPELINE_STEP_TIMEOUT_SECONDS", "900")))
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
        )
        output = completed.stdout or ""
        exit_code = completed.returncode
        status = "SUCCESS" if exit_code == 0 else "FAILED"
    except subprocess.TimeoutExpired as exc:
        captured = exc.stdout or ""
        if isinstance(captured, bytes):
            captured = captured.decode("utf-8", errors="replace")
        output = f"{captured}\nSTEP TIMEOUT after {timeout_seconds} seconds\n"
        exit_code = 124
        status = "TIMEOUT"

    log_path.write_text(output, encoding="utf-8", errors="replace")
    print(f"\n===== {name} [{status}] =====")
    excerpt = _console_excerpt(output)
    if excerpt:
        print(excerpt)
    print(f"log: {log_path.relative_to(ROOT).as_posix()}")
    result = StepResult(
        name=name,
        command=command,
        status=status,
        exit_code=exit_code,
        duration_seconds=round(time.monotonic() - started, 3),
        log_path=log_path.relative_to(ROOT).as_posix(),
    )
    if exit_code != 0:
        raise PipelineFailure(result)
    return result


class PipelineFailure(RuntimeError):
    def __init__(self, result: StepResult):
        super().__init__(f"Pipeline step failed: {result.name}")
        self.result = result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical repository pipeline exactly once")
    parser.add_argument("--mode", choices=["auto", "daily", "post-match", "prepare", "validate"], default="auto")
    parser.add_argument("--competition", default="all", help="Competition ID or 'all'")
    parser.add_argument("--as-of", default="", help="UTC or timezone-aware temporal cutoff")
    parser.add_argument("--allow-network", action="store_true", help="Enable configured public network providers")
    parser.add_argument("--run-tests", action="store_true", help="Run the complete repository test suite")
    parser.add_argument("--skip-temporal", action="store_true", help="Skip worldcup_brain even for world_cup_2026")
    return parser.parse_args()


def write_report(payload: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    mode = "daily" if args.mode == "auto" else args.mode
    cutoff = args.as_of.strip() or default_cutoff()
    identifier = run_id()
    log_dir = LOG_ROOT / identifier
    env = os.environ.copy()
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "SPORTS_ENGINE_NETWORK": "1" if args.allow_network else "0",
    })

    steps: list[StepResult] = []
    payload: dict[str, Any] = {
        "run_id": identifier,
        "started_at": utc_now(),
        "mode": mode,
        "competition": args.competition,
        "as_of": cutoff,
        "network_enabled": args.allow_network,
        "status": "RUNNING",
        "steps": [],
    }

    try:
        steps.append(execute("preflight", [sys.executable, "scripts/ci_preflight.py", "--check"], env, log_dir))

        if mode in {"daily", "post-match"}:
            if args.competition == "all":
                sports_command = [sys.executable, "-m", "sports_engine.cli", "run-registry"]
            else:
                sports_command = [sys.executable, "-m", "sports_engine.cli", "run-all", "--competition", args.competition]
            steps.append(execute("sports_pipeline", sports_command, env, log_dir))
        elif mode == "validate":
            if args.competition == "all":
                # Audit is global; validation of the active competition is covered by make test.
                steps.append(execute("sports_audit", [sys.executable, "-m", "sports_engine.cli", "audit"], env, log_dir))
            else:
                steps.append(execute("sports_validation", [sys.executable, "-m", "sports_engine.cli", "validate", "--competition", args.competition], env, log_dir))

        temporal_enabled = not args.skip_temporal and args.competition in {"all", "world_cup_2026"}
        if temporal_enabled:
            if mode == "prepare":
                steps.append(execute("temporal_prepare", [sys.executable, "-m", "worldcup_brain.cli", "prepare"], env, log_dir))
                steps.append(execute(
                    "temporal_validate_pre_worldcup",
                    [sys.executable, "-m", "worldcup_brain.cli", "validate", "--as-of", PRE_WORLD_CUP_CUTOFF],
                    env,
                    log_dir,
                ))
            elif mode in {"daily", "post-match"}:
                # sports_engine already performs the only enrichment/network pass. The temporal
                # replay rebuilds its missing-data queue, so a second collection scan is redundant.
                steps.append(execute(
                    f"temporal_{mode}",
                    [sys.executable, "-m", "worldcup_brain.cli", mode, "--as-of", cutoff],
                    env,
                    log_dir,
                ))
                steps.append(execute(
                    "temporal_validate",
                    [sys.executable, "-m", "worldcup_brain.cli", "validate", "--as-of", cutoff],
                    env,
                    log_dir,
                ))
            elif mode == "validate":
                steps.append(execute(
                    "temporal_validate",
                    [sys.executable, "-m", "worldcup_brain.cli", "validate", "--as-of", cutoff],
                    env,
                    log_dir,
                ))

            if mode != "prepare":
                steps.append(execute(
                    "temporal_audit",
                    [sys.executable, "-m", "worldcup_brain.cli", "audit"],
                    env,
                    log_dir,
                ))
                steps.append(execute(
                    "temporal_status",
                    [sys.executable, "-m", "worldcup_brain.cli", "status"],
                    env,
                    log_dir,
                ))

        steps.append(execute("export_dashboard", [sys.executable, "scripts/export_model_dashboard.py"], env, log_dir))
        if args.run_tests:
            steps.append(execute("repository_tests", ["make", "test"], env, log_dir))

        payload.update({
            "finished_at": utc_now(),
            "status": "SUCCESS",
            "steps": [asdict(step) for step in steps],
            "summary": {
                "steps_completed": len(steps),
                "network_requests_are_single_pass": True,
                "write_pipeline": "single_orchestrator",
            },
        })
        write_report(payload)
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        return 0
    except PipelineFailure as exc:
        steps.append(exc.result)
        payload.update({
            "finished_at": utc_now(),
            "status": "FAILED",
            "failed_step": exc.result.name,
            "steps": [asdict(step) for step in steps],
        })
        write_report(payload)
        return exc.result.exit_code or 1
    except Exception as exc:  # defensive: always leave an actionable pipeline report
        payload.update({
            "finished_at": utc_now(),
            "status": "FAILED_UNEXPECTED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "steps": [asdict(step) for step in steps],
        })
        write_report(payload)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
