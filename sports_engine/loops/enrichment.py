from __future__ import annotations

from pathlib import Path
from typing import Any
import os

<<<<<<< HEAD
import pandas as pd

from ..config import CompetitionConfig, ROOT
from ..io import read_json, read_table, utc_now, write_json_copies
from ..lineage import metadata
from ..sources import (
    fetch_espn_scoreboard,
    fetch_espn_summaries,
    fetch_football_data_matches,
    fetch_open_meteo_previous_runs,
    merge_scoreboard_results,
)
=======
from ..config import CompetitionConfig, ROOT
from ..io import read_json, read_table, utc_now, write_json_copies
from ..lineage import metadata
from ..sources import fetch_espn_scoreboard, fetch_espn_summaries, merge_scoreboard_results
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
from ..player_facts import derive_player_facts
from .completeness import _coverage_for_dataset


def run(config: CompetitionConfig) -> dict[str, Any]:
    queue_path = config.scoped_path("data", "queues", "missing_data.json")
    queue_alias = ROOT / "data" / "queues" / "missing_data.json"
    queue_payload = read_json(queue_path, read_json(queue_alias, {"items": []}))
    items = queue_payload.get("items", [])
    log_path = config.scoped_path("logs", "enrichment_log.json")
    log_alias = ROOT / "logs" / "enrichment_log.json"
    history = read_json(log_path, [])
    if not isinstance(history, list):
        history = []
    sources = sorted(config.data.get("sources", []), key=lambda item: int(item.get("priority", 99)))
    session_cache: dict[str, dict[str, Any]] = {}
    resolved = 0
<<<<<<< HEAD
    supplemental: list[dict[str, Any]] = []
    network_enabled = os.getenv("SPORTS_ENGINE_NETWORK", "0").lower() in {"1", "true", "yes"}

    # Independent feeds run once per network-enabled pipeline even when the
    # completeness queue is already satisfied by the canonical source.
    for source in sources:
        if not network_enabled or not source.get("enabled", True) or not source.get("proactive", False):
            continue
        source_id = str(source.get("id"))
        try:
            if source.get("type") == "football_data_v4":
                session_cache[source_id] = fetch_football_data_matches(source, config)
            elif source.get("type") == "open_meteo_previous_runs":
                matches = read_table(config.dataset("matches"))
                match_col = next((name for name in ("jogo", "match_id") if name in matches.columns), None)
                all_ids = set(pd.to_numeric(matches[match_col], errors="coerce").dropna().astype(int)) if match_col else set()
                covered, _ = _coverage_for_dataset(config, "pre_match_weather", "weather", all_ids)
                max_matches = int(config.engine.get("max_enrichment_matches_per_run", 24))
                session_cache[source_id] = fetch_open_meteo_previous_runs(source, config, sorted(all_ids - covered)[:max_matches])
            else:
                continue
            supplemental.append({"source": source_id, **session_cache[source_id]})
        except Exception as exc:
            supplemental.append({"source": source_id, "success": False, "reason": f"{type(exc).__name__}: {exc}"})
=======
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3

    for item in items:
        if item.get("status") != "OPEN":
            continue
        field = item.get("missing_field")
        candidates = [source for source in sources if source.get("enabled", True) and field in source.get("provides", [])]
        attempt = {
            "requested_data": item,
            "source": "NA",
            "date": utc_now(),
            "success": False,
            "confidence": "NA",
            "details": "No configured source provides this field.",
        }
        for source in candidates:
            attempt["source"] = source.get("id", "NA")
<<<<<<< HEAD
            if source.get("type") in {"espn_summary", "espn_scoreboard", "football_data_v4", "open_meteo_previous_runs", "http_json"} and os.getenv("SPORTS_ENGINE_NETWORK", "0").lower() not in {"1", "true", "yes"}:
=======
            if source.get("type") in {"espn_summary", "espn_scoreboard", "http_json"} and os.getenv("SPORTS_ENGINE_NETWORK", "0").lower() not in {"1", "true", "yes"}:
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
                attempt["details"] = "Network collection is disabled for this local run. GitHub Actions enables it explicitly."
                continue
            attempt["confidence"] = source.get("confidence", "NA")
            try:
                if source.get("type") == "local_dataset":
                    path = ROOT / str(source.get("path", ""))
                    frame = read_table(path, required=False)
                    if not frame.empty:
                        all_ids = set(int(value) for value in item.get("entity_ids", []))
                        covered, note = _coverage_for_dataset(config, item.get("provider_dataset", ""), str(field), all_ids)
                        complete = all_ids.issubset(covered)
                        attempt.update({"success": complete, "details": {"path": path.relative_to(ROOT).as_posix(), "coverage_note": note, "covered": len(covered), "requested": len(all_ids)}})
                        if complete:
                            break
                elif source.get("type") == "derived_player_facts":
                    source_id = str(source.get("id"))
                    if source_id not in session_cache:
                        session_cache[source_id] = derive_player_facts(config)
                    derived = session_cache[source_id]
                    all_ids = set(int(value) for value in item.get("entity_ids", []))
                    covered, note = _coverage_for_dataset(config, item.get("provider_dataset", ""), str(field), all_ids)
                    complete = all_ids.issubset(covered)
                    attempt.update({
                        "success": complete,
                        "details": {
                            "derivation": derived.get("summary", derived),
                            "coverage_note": note,
                            "covered": len(covered),
                            "requested": len(all_ids),
                        },
                    })
                    if complete:
                        break
                elif source.get("type") == "espn_summary":
                    source_id = str(source.get("id"))
                    if source_id not in session_cache:
                        provided = set(source.get("provides", []))
                        priority_rank = {"high": 0, "medium": 1, "low": 2}
                        relevant = sorted(
                            [queued for queued in items if queued.get("status") == "OPEN" and queued.get("missing_field") in provided],
                            key=lambda queued: (priority_rank.get(str(queued.get("priority", "medium")), 1), str(queued.get("missing_field", ""))),
                        )
                        needed_ids: list[int] = []
                        seen_ids: set[int] = set()
                        for queued in relevant:
                            all_ids = {int(value) for value in queued.get("entity_ids", [])}
                            covered, _ = _coverage_for_dataset(
                                config,
                                queued.get("provider_dataset", ""),
                                str(queued.get("missing_field", "")),
                                all_ids,
                            )
                            for value in sorted(all_ids - covered):
                                match_id = int(value)
                                if match_id not in seen_ids:
                                    seen_ids.add(match_id)
                                    needed_ids.append(match_id)
                        max_matches = int(config.engine.get("max_enrichment_matches_per_run", 12))
                        session_cache[source_id] = fetch_espn_summaries(source, config, needed_ids[:max_matches])
                    fetched = session_cache[source_id]
                    all_ids = set(int(value) for value in item.get("entity_ids", []))
                    covered, note = _coverage_for_dataset(config, item.get("provider_dataset", ""), str(field), all_ids)
                    complete = all_ids.issubset(covered)
                    attempt.update({"success": complete, "details": {"fetch": fetched, "coverage_note": note, "covered": len(covered), "requested": len(all_ids)}})
                    if complete:
                        break
                elif source.get("type") == "espn_scoreboard":
                    source_id = str(source.get("id"))
                    if source_id not in session_cache:
                        session_cache[source_id] = fetch_espn_scoreboard(source, config)
                    fetched = session_cache[source_id]
                    if fetched.get("success"):
                        merged = merge_scoreboard_results(config, ROOT / fetched["staging_path"])
                        attempt.update({"success": merged.get("inserted", 0) > 0, "details": {"fetch": fetched, "merge": merged}})
                        if attempt["success"]:
                            break
<<<<<<< HEAD
                elif source.get("type") == "football_data_v4":
                    source_id = str(source.get("id"))
                    if source_id not in session_cache:
                        session_cache[source_id] = fetch_football_data_matches(source, config)
                    fetched = session_cache[source_id]
                    attempt.update({"success": bool(fetched.get("success")), "details": fetched})
                    if attempt["success"]:
                        break
                elif source.get("type") == "open_meteo_previous_runs":
                    source_id = str(source.get("id"))
                    all_ids = {int(value) for value in item.get("entity_ids", [])}
                    covered, _ = _coverage_for_dataset(config, "pre_match_weather", "weather", all_ids)
                    needed = sorted(all_ids - covered)
                    if source_id not in session_cache:
                        max_matches = int(config.engine.get("max_enrichment_matches_per_run", 24))
                        session_cache[source_id] = fetch_open_meteo_previous_runs(source, config, needed[:max_matches])
                    fetched = session_cache[source_id]
                    covered_after, note = _coverage_for_dataset(config, "pre_match_weather", "weather", all_ids)
                    complete = all_ids.issubset(covered_after)
                    attempt.update({
                        "success": complete,
                        "details": {"fetch": fetched, "coverage_note": note, "covered": len(covered_after), "requested": len(all_ids)},
                    })
                    if complete:
                        break
=======
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
                else:
                    attempt["details"] = f"Adapter '{source.get('type')}' is configured but not implemented for structured merge."
            except Exception as exc:
                attempt["details"] = f"{type(exc).__name__}: {exc}"
        if attempt["success"]:
            item["status"] = "RESOLVED"
            item["resolved_at"] = utc_now()
            resolved += 1
        history.append(attempt)

    write_json_copies({"generated_at": utc_now(), "competition_id": config.competition_id, "items": items}, queue_path, queue_alias)
    write_json_copies(history, log_path, log_alias)
    report = metadata("02_data_enrichment", config.competition_id, [queue_path], ROOT, {
<<<<<<< HEAD
        "summary": {
            "queue_items": len(items),
            "resolved_this_run": resolved,
            "remaining_open": sum(1 for item in items if item.get("status") == "OPEN"),
            "supplemental_sources_checked": len(supplemental),
        },
        "supplemental_sources": supplemental,
=======
        "summary": {"queue_items": len(items), "resolved_this_run": resolved, "remaining_open": sum(1 for item in items if item.get("status") == "OPEN")},
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
        "log_path": log_path.relative_to(ROOT).as_posix(),
    })
    write_json_copies(
        report,
        config.scoped_path("reports", "enrichment_report.json"),
        ROOT / "reports" / "enrichment_report.json",
    )
    return report
