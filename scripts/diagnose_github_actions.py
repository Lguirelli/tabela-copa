#!/usr/bin/env python3
"""Repeatable, isolated diagnosis of GitHub Actions-equivalent repository runs.

The script copies the repository into a fresh workspace for every scenario and
iteration, executes each workflow step independently, preserves complete logs,
and classifies recurring failure signatures. It does not mutate the source
checkout and does not require GitHub API access.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports" / "run_diagnostics"
PRE_WORLD_CUP_CUTOFF = "2026-06-10T23:59:59-04:00"


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    env: dict[str, str] | None = None
    timeout_seconds: int = 300


@dataclass
class StepResult:
    scenario: str
    iteration: int
    step: str
    command: list[str]
    status: str
    exit_code: int | None
    duration_seconds: float
    classification: str
    probable_cause: str
    log_path: str
    tail: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_cutoff() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def python_step(name: str, *args: str, env: dict[str, str] | None = None, timeout: int = 300) -> Step:
    return Step(name=name, command=[sys.executable, *args], env=env, timeout_seconds=timeout)


def scenarios(allow_network: bool) -> dict[str, list[Step]]:
    base_env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    network_env = {**base_env, "SPORTS_ENGINE_NETWORK": "1" if allow_network else "0"}
    cutoff = current_cutoff()
    collect_args = ["-m", "worldcup_brain.cli", "collect"]
    if allow_network:
        collect_args.append("--allow-network")
    return {
        "repository_quality": [
            python_step("pytest", "-m", "pytest", "-p", "no:cacheprovider", "-q", env=base_env),
            python_step("validate_repository", "scripts/validate_repository.py", env=base_env),
            python_step("integrity", "scripts/testes/test_integridade_dados.py", env=base_env),
        ],
        "sports_pipeline": [
            python_step("run_registry", "-m", "sports_engine.cli", "run-registry", env=network_env, timeout=600),
            python_step("export_dashboard", "scripts/export_model_dashboard.py", env=base_env),
            python_step("pytest_after_pipeline", "-m", "pytest", "-p", "no:cacheprovider", "-q", env=base_env),
            python_step("validate_after_pipeline", "scripts/validate_repository.py", env=base_env),
            python_step("integrity_after_pipeline", "scripts/testes/test_integridade_dados.py", env=base_env),
        ],
        "temporal_pre_worldcup": [
            python_step("prepare", "-m", "worldcup_brain.cli", "prepare", env=base_env),
            python_step("validate_pre_worldcup", "-m", "worldcup_brain.cli", "validate", "--as-of", PRE_WORLD_CUP_CUTOFF, env=base_env),
            python_step(
                "pytest_initial_artifacts",
                "-m", "pytest", "-p", "no:cacheprovider", "-q",
                "--ignore=tests/test_model_dashboard.py",
                env=base_env,
            ),
        ],
        "temporal_boundary_replay": [
            python_step("replay_at_pre_worldcup_cutoff", "-m", "worldcup_brain.cli", "replay", "--as-of", PRE_WORLD_CUP_CUTOFF, env=base_env, timeout=600),
            python_step("validate_empty_boundary_indexes", "-m", "worldcup_brain.cli", "validate", "--as-of", PRE_WORLD_CUP_CUTOFF, env=base_env),
            python_step(
                "check_empty_indexes_have_headers",
                "-c",
                (
                    "from pathlib import Path; "
                    "paths=[Path('predictions/pre_match/index.csv'),Path('learning/game_analysis/index.csv')]; "
                    "assert all(p.read_text(encoding='utf-8').strip() for p in paths), paths; "
                    "print('Boundary indexes contain stable headers')"
                ),
                env=base_env,
            ),
        ],
        "temporal_current": [
            python_step(
                "configure_fast_diagnostic_simulation",
                "-c",
                (
                    "from pathlib import Path; import yaml; "
                    "p=Path('config/worldcup_temporal.yaml'); "
                    "d=yaml.safe_load(p.read_text(encoding='utf-8')); "
                    "d['simulation_iterations']=500; "
                    "p.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True),encoding='utf-8'); "
                    "print('Diagnostic simulation_iterations=500 (production remains unchanged)')"
                ),
                env=base_env,
            ),
            python_step("collect", *collect_args, env=network_env, timeout=600),
            python_step("daily_replay", "-m", "worldcup_brain.cli", "daily", "--as-of", cutoff, env=base_env, timeout=900),
            python_step("validate_current", "-m", "worldcup_brain.cli", "validate", "--as-of", cutoff, env=base_env),
            python_step("export_dashboard", "scripts/export_model_dashboard.py", env=base_env),
            python_step("pytest_current", "-m", "pytest", "-p", "no:cacheprovider", "-q", env=base_env),
        ],
        "static_pages": [
            python_step(
                "validate_static_entrypoints",
                "-c",
                (
                    "from pathlib import Path; "
                    "required=['index.html','rede-neural.html','modelo-evolucao.html',"
                    "'modelo-previsoes.html','modelo-aprendizado.html','modelo-simulacoes.html',"
                    "'modelo-versoes.html','src/model-analytics-data.js','src/model-pages.js']; "
                    "missing=[p for p in required if not Path(p).is_file()]; "
                    "assert not missing, f'Missing static files: {missing}'; print('Static files OK')"
                ),
                env=base_env,
            ),
        ],
    }


def copy_repository(destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc", ".pytest_cache", "*.egg-info",
        "build", "dist", "run_diagnostics",
    )
    shutil.copytree(ROOT, destination, ignore=ignored)


def classify_failure(output: str, exit_code: int | None, timed_out: bool) -> tuple[str, str]:
    if exit_code == 0 and not timed_out:
        return "NONE", "Etapa concluída."
    lowered = output.lower()
    if timed_out:
        return "TIMEOUT", "A etapa excedeu o limite; verifique espera de rede, retry excessivo ou processamento bloqueado."
    rules = [
        (("could not determine delimiter", "emptydataerror"), "EMPTY_CSV", "Um CSV vazio/sem cabeçalho foi lido com detecção automática de separador."),
        (("arquivo/pasta legado reapareceu", "legacy"), "LEGACY_ARTIFACT", "Arquivos proibidos pela validação de integridade ainda existem ou foram recriados."),
        (("modulenotfounderror", "no module named"), "DEPENDENCY_OR_IMPORT", "Dependência ausente, instalação incompleta ou caminho de importação incorreto."),
        (("no such file or directory", "filenotfounderror"), "MISSING_FILE", "O workflow referencia um arquivo que não existe no checkout."),
        (("non-fast-forward", "failed to push", "rejected"), "GIT_PUSH_RACE", "Outro workflow ou commit atualizou a branch durante a run."),
        (("429", "too many requests", "rate limit"), "RATE_LIMIT", "A fonte externa limitou as requisições."),
        (("connectionerror", "httpserror", "read timed out", "connect timeout", "temporary failure in name resolution"), "NETWORK_PROVIDER", "Falha de rede, DNS, timeout ou indisponibilidade do provedor."),
        (("assertionerror", "failed"), "TEST_OR_VALIDATION", "Teste ou contrato de dados falhou; consulte as últimas linhas do log."),
        (("permission denied", "resource not accessible by integration"), "PERMISSION", "Permissões do token ou do filesystem são insuficientes."),
        (("yaml", "scannererror", "parsererror"), "CONFIGURATION", "Arquivo YAML/configuração inválido ou incompatível."),
    ]
    for needles, label, cause in rules:
        if any(needle in lowered for needle in needles):
            return label, cause
    return "UNKNOWN", "Falha sem assinatura conhecida; examine o log completo preservado no relatório."


def execute_step(step: Step, cwd: Path, log_path: Path, scenario: str, iteration: int) -> StepResult:
    env = os.environ.copy()
    env.update(step.env or {})
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            step.command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=step.timeout_seconds,
            check=False,
        )
        output = completed.stdout or ""
        exit_code: int | None = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        output = f"{partial}\nTIMEOUT after {step.timeout_seconds}s\n"
    duration = round(time.monotonic() - started, 3)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8", errors="replace")
    classification, cause = classify_failure(output, exit_code, timed_out)
    status = "SUCCESS" if exit_code == 0 and not timed_out else "FAILED"
    tail = "\n".join(output.splitlines()[-40:])
    return StepResult(
        scenario=scenario,
        iteration=iteration,
        step=step.name,
        command=step.command,
        status=status,
        exit_code=exit_code,
        duration_seconds=duration,
        classification=classification,
        probable_cause=cause,
        log_path=log_path.as_posix(),
        tail=tail,
    )


def workflow_analysis() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    workflow_dir = ROOT / ".github" / "workflows"
    writer_groups: dict[str, list[str]] = defaultdict(list)
    workflow_names: set[str] = set()
    payloads: dict[str, dict[str, Any]] = {}

    for path in sorted(workflow_dir.glob("*.yml")):
        try:
            payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader) or {}
            payloads[path.name] = payload
            workflow_names.add(str(payload.get("name", "")))
        except Exception as exc:
            findings.append({"severity": "ERROR", "workflow": path.name, "check": "yaml", "message": str(exc)})
            continue
        permissions = payload.get("permissions", {})
        if isinstance(permissions, dict) and permissions.get("contents") == "write":
            concurrency = payload.get("concurrency", {})
            group = concurrency.get("group", "MISSING") if isinstance(concurrency, dict) else "MISSING"
            writer_groups[str(group)].append(path.name)
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"python(?:3)?\s+([^\s|;&]+\.py)", text):
            referenced = match.group(1).strip('"\'')
            if "$" not in referenced and not (ROOT / referenced).exists():
                findings.append({
                    "severity": "ERROR", "workflow": path.name, "check": "missing_script",
                    "message": f"Referenced script does not exist: {referenced}",
                })
        if "git push" in text and "git pull --rebase" not in text:
            findings.append({
                "severity": "INFO", "workflow": path.name, "check": "push_without_rebase",
                "message": "git push has no rebase retry; global writer concurrency must remain shared.",
            })

    if len(writer_groups) > 1:
        findings.append({
            "severity": "WARNING",
            "workflow": "MULTIPLE",
            "check": "writer_concurrency",
            "message": f"Write workflows use multiple concurrency groups: {dict(writer_groups)}",
        })
    elif writer_groups:
        group, members = next(iter(writer_groups.items()))
        findings.append({
            "severity": "PASS",
            "workflow": "MULTIPLE",
            "check": "writer_concurrency",
            "message": f"All {len(members)} write workflows are serialized by {group}.",
        })

    for filename, payload in payloads.items():
        trigger = payload.get("on", {})
        if not isinstance(trigger, dict) or "workflow_run" not in trigger:
            continue
        configured = trigger["workflow_run"].get("workflows", []) if isinstance(trigger["workflow_run"], dict) else []
        for expected in configured:
            if expected not in workflow_names:
                findings.append({
                    "severity": "ERROR", "workflow": filename, "check": "workflow_run_name",
                    "message": f"workflow_run references unknown workflow name: {expected}",
                })
    return findings


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Diagnóstico das GitHub Actions",
        "",
        f"Gerado em: `{payload['generated_at']}`",
        f"Iterações: **{payload['iterations']}**",
        f"Status geral: **{payload['status']}**",
        "",
        "## Resumo das etapas",
        "",
        "| Cenário | Iteração | Etapa | Status | Classe | Duração |",
        "|---|---:|---|---|---|---:|",
    ]
    for item in payload["steps"]:
        lines.append(
            f"| {item['scenario']} | {item['iteration']} | {item['step']} | {item['status']} | "
            f"{item['classification']} | {item['duration_seconds']:.3f}s |"
        )
    lines.extend(["", "## Falhas recorrentes", ""])
    if payload["recurring_failures"]:
        for item in payload["recurring_failures"]:
            lines.append(
                f"- **{item['classification']}** em `{item['scenario']} / {item['step']}`: "
                f"{item['failures']}/{payload['iterations']} iterações. {item['probable_cause']}"
            )
    else:
        lines.append("Nenhuma falha foi reproduzida.")
    lines.extend(["", "## Análise estática dos workflows", ""])
    for finding in payload["workflow_findings"]:
        lines.append(
            f"- **{finding['severity']}** `{finding['workflow']}` / `{finding['check']}` — {finding['message']}"
        )
    failed = [item for item in payload["steps"] if item["status"] == "FAILED"]
    if failed:
        lines.extend(["", "## Últimas linhas das falhas", ""])
        for item in failed:
            lines.extend([
                f"### {item['scenario']} · {item['step']} · iteração {item['iteration']}",
                "",
                f"Causa provável: {item['probable_cause']}",
                "",
                "```text",
                item["tail"][-6000:],
                "```",
                "",
            ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose failing GitHub Actions-equivalent runs")
    parser.add_argument("--iterations", type=int, default=2, help="How many isolated repetitions per scenario")
    parser.add_argument("--scenario", action="append", help="Scenario to run; repeat to select multiple")
    parser.add_argument("--allow-network", action="store_true", help="Enable configured public network sources")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero when a step fails")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.iterations < 1 or args.iterations > 10:
        raise SystemExit("--iterations must be between 1 and 10")
    available = scenarios(args.allow_network)
    selected = args.scenario or list(available)
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise SystemExit(f"Unknown scenarios: {unknown}; available: {sorted(available)}")

    output_dir = args.output_dir.resolve()
    logs_dir = output_dir / "logs"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    results: list[StepResult] = []
    with tempfile.TemporaryDirectory(prefix="wc2026_run_diagnostics_") as temp_root:
        temp_root_path = Path(temp_root)
        for iteration in range(1, args.iterations + 1):
            for scenario_name in selected:
                workspace = temp_root_path / f"iteration_{iteration}" / scenario_name
                copy_repository(workspace)
                scenario_failed = False
                for step in available[scenario_name]:
                    log_path = logs_dir / f"{scenario_name}__iteration_{iteration}__{step.name}.log"
                    result = execute_step(step, workspace, log_path, scenario_name, iteration)
                    results.append(result)
                    marker = "PASS" if result.status == "SUCCESS" else "FAIL"
                    print(f"[{marker}] {scenario_name} / {step.name} ({result.duration_seconds:.3f}s)")
                    if result.status == "FAILED":
                        scenario_failed = True
                        # Later steps usually depend on the failed artifact; stop this isolated scenario.
                        break
                if scenario_failed:
                    continue

    failure_counter: Counter[tuple[str, str, str]] = Counter()
    cause_by_key: dict[tuple[str, str, str], str] = {}
    for item in results:
        if item.status != "FAILED":
            continue
        key = (item.scenario, item.step, item.classification)
        failure_counter[key] += 1
        cause_by_key[key] = item.probable_cause
    recurring = [
        {
            "scenario": key[0],
            "step": key[1],
            "classification": key[2],
            "failures": count,
            "recurring": count == args.iterations,
            "probable_cause": cause_by_key[key],
        }
        for key, count in sorted(failure_counter.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    workflow_findings = workflow_analysis()
    has_failures = any(item.status == "FAILED" for item in results)
    has_workflow_errors = any(item["severity"] == "ERROR" for item in workflow_findings)
    payload: dict[str, Any] = {
        "generated_at": now_iso(),
        "repository": ROOT.as_posix(),
        "iterations": args.iterations,
        "selected_scenarios": selected,
        "network_enabled": args.allow_network,
        "status": "FAILURES_REPRODUCED" if has_failures or has_workflow_errors else "NO_FAILURE_REPRODUCED",
        "summary": {
            "steps_executed": len(results),
            "steps_succeeded": sum(item.status == "SUCCESS" for item in results),
            "steps_failed": sum(item.status == "FAILED" for item in results),
            "workflow_findings": len(workflow_findings),
        },
        "recurring_failures": recurring,
        "workflow_findings": workflow_findings,
        "steps": [asdict(item) for item in results],
    }
    json_path = output_dir / "run_diagnostics.json"
    md_path = output_dir / "run_diagnostics.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = markdown_report(payload)
    md_path.write_text(md, encoding="utf-8")
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(md)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {md_path}")
    return 1 if args.fail_on_error and (has_failures or has_workflow_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
