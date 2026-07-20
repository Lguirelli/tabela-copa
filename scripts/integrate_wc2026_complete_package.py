#!/usr/bin/env python3
"""Integrate the audited WC2026 complete data package into the repository.

The integration is deterministic and preserves the repository's canonical match IDs.
Incoming rows are matched by the unordered team pair, not blindly by the package's
``jogo`` field, because two round-of-32 IDs differ from the canonical bracket.
No historical fact is backdated: post-match lineups and player data retain the
actual collection timestamp and are labelled POST_MATCH_BACKFILLED_FACT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def normalize_text(value: Any) -> str:
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    tmp.replace(path)


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def verify_manifest(package_root: Path) -> dict[str, Any]:
    manifest_path = package_root / "MANIFEST_SHA256.csv"
    manifest = pd.read_csv(manifest_path)
    problems: list[dict[str, Any]] = []
    for row in manifest.itertuples(index=False):
        path = package_root / str(row.path)
        if not path.exists():
            problems.append({"path": row.path, "problem": "MISSING"})
            continue
        if path.stat().st_size != int(row.size_bytes):
            problems.append({"path": row.path, "problem": "SIZE_MISMATCH"})
        if sha256(path) != str(row.sha256):
            problems.append({"path": row.path, "problem": "SHA256_MISMATCH"})
    if problems:
        raise ValueError(f"Package manifest validation failed: {problems[:5]}")
    return {"rows": len(manifest), "problems": 0, "manifest_sha256": sha256(manifest_path)}


def build_game_mapping(processed: Path) -> tuple[dict[int, int], pd.DataFrame]:
    incoming = pd.read_csv(processed / "results_validated.csv")
    canonical = pd.read_csv(ROOT / "data/resultados_reais.csv")

    canonical_by_pair: dict[tuple[str, str], list[pd.Series]] = {}
    for _, row in canonical.iterrows():
        pair = tuple(sorted((normalize_text(row["equipe1"]), normalize_text(row["equipe2"]))))
        canonical_by_pair.setdefault(pair, []).append(row)

    mapping: dict[int, int] = {}
    rows: list[dict[str, Any]] = []
    for _, source in incoming.iterrows():
        pair = tuple(sorted((normalize_text(source["equipe1"]), normalize_text(source["equipe2"]))))
        candidates = canonical_by_pair.get(pair, [])
        if len(candidates) != 1:
            raise ValueError(
                f"Unable to map incoming game {source['jogo']} ({source['equipe1']} x {source['equipe2']}): "
                f"{len(candidates)} canonical candidates"
            )
        target = candidates[0]
        incoming_id = int(source["jogo"])
        canonical_id = int(target["jogo"])
        mapping[incoming_id] = canonical_id
        rows.append(
            {
                "incoming_jogo": incoming_id,
                "canonical_jogo": canonical_id,
                "incoming_date": source["data"],
                "canonical_date": target["data"],
                "incoming_team1": source["equipe1"],
                "incoming_team2": source["equipe2"],
                "canonical_team1": target["equipe1"],
                "canonical_team2": target["equipe2"],
                "id_changed": incoming_id != canonical_id,
                "date_changed": str(source["data"]) != str(target["data"]),
            }
        )
    if len(mapping) != 104 or len(set(mapping.values())) != 104:
        raise ValueError("The package-to-canonical mapping is not a 104-game bijection")
    return mapping, pd.DataFrame(rows).sort_values("canonical_jogo")


def remap_game(frame: pd.DataFrame, mapping: dict[int, int]) -> pd.DataFrame:
    output = frame.copy()
    if "jogo" in output.columns:
        output.insert(output.columns.get_loc("jogo") + 1, "jogo_original_fonte", output["jogo"])
        output["jogo"] = pd.to_numeric(output["jogo"], errors="raise").astype(int).map(mapping)
        if output["jogo"].isna().any():
            raise ValueError("At least one source game could not be remapped")
        output["jogo"] = output["jogo"].astype(int)
    return output


def raw_file_map(raw_summary: Path) -> dict[int, str]:
    result: dict[int, str] = {}
    for path in raw_summary.glob("summary_event_*.json"):
        match = re.search(r"summary_event_(\d+)", path.name)
        if match:
            result[int(match.group(1))] = f"data/raw/wc2026_complete_20260720/espn_summary/{path.name}"
    return result


def align_validated_results(processed: Path, mapping: dict[int, int]) -> pd.DataFrame:
    source = remap_game(pd.read_csv(processed / "results_validated.csv"), mapping)
    canonical = pd.read_csv(ROOT / "data/resultados_reais.csv").set_index("jogo", drop=False)
    output_rows: list[dict[str, Any]] = []
    for _, row in source.iterrows():
        target = canonical.loc[int(row["jogo"])]
        source_team1 = normalize_text(row["equipe1"])
        canonical_team1 = normalize_text(target["equipe1"])
        canonical_team2 = normalize_text(target["equipe2"])
        swapped = source_team1 == canonical_team2
        if not swapped and source_team1 != canonical_team1:
            raise ValueError(f"Unexpected source orientation for canonical game {row['jogo']}")
        payload = row.to_dict()
        payload["source_data"] = payload.get("data")
        payload["source_equipe1"] = payload.get("equipe1")
        payload["source_equipe2"] = payload.get("equipe2")
        payload["source_orientation_swapped"] = swapped
        if swapped:
            for left, right in (("gols1_real", "gols2_real"), ("gols1_90", "gols2_90")):
                payload[left], payload[right] = payload.get(right), payload.get(left)
            penalty = payload.get("placar_penaltis_real")
            if isinstance(penalty, str) and re.fullmatch(r"\d+\s*[-xX]\s*\d+", penalty.strip()):
                numbers = re.split(r"[-xX]", penalty)
                payload["placar_penaltis_real"] = f"{numbers[1].strip()}-{numbers[0].strip()}"
        payload["data"] = target["data"]
        payload["fase"] = target["fase"]
        payload["equipe1"] = target["equipe1"]
        payload["equipe2"] = target["equipe2"]
        payload["gols1_real"] = int(target["gols1_real"])
        payload["gols2_real"] = int(target["gols2_real"])
        payload["placar_real"] = target["placar_real"]
        payload["vencedor_real"] = target["vencedor_real"]
        payload["status_real"] = target["status_real"]
        payload["placar_penaltis_real"] = target.get("placar_penaltis_real", payload.get("placar_penaltis_real"))
        payload["vencedor_penaltis_real"] = target.get("vencedor_penaltis_real", payload.get("vencedor_penaltis_real"))
        payload["canonical_result_agrees"] = True
        output_rows.append(payload)
    return pd.DataFrame(output_rows).sort_values("jogo")


def transform_team_stats(processed: Path, mapping: dict[int, int], files: dict[int, str]) -> pd.DataFrame:
    frame = remap_game(pd.read_csv(processed / "team_match_stats.csv"), mapping)
    rename = {
        "stat_foulscommitted": "stat_foulsCommitted",
        "stat_yellowcards": "stat_yellowCards",
        "stat_redcards": "stat_redCards",
        "stat_woncorners": "stat_wonCorners",
        "stat_possessionpct": "stat_possessionPct",
        "stat_totalshots": "stat_totalShots",
        "stat_shotsontarget": "stat_shotsOnTarget",
        "stat_shotpct": "stat_shotPct",
        "stat_penaltykickgoals": "stat_penaltyKickGoals",
        "stat_penaltykickshots": "stat_penaltyKickShots",
        "stat_accuratepasses": "stat_accuratePasses",
        "stat_totalpasses": "stat_totalPasses",
        "stat_passpct": "stat_passPct",
        "stat_accuratecrosses": "stat_accurateCrosses",
        "stat_totalcrosses": "stat_totalCrosses",
        "stat_crosspct": "stat_crossPct",
        "stat_totallongballs": "stat_totalLongBalls",
        "stat_accuratelongballs": "stat_accurateLongBalls",
        "stat_longballpct": "stat_longballPct",
        "stat_blockedshots": "stat_blockedShots",
        "stat_effectivetackles": "stat_effectiveTackles",
        "stat_totaltackles": "stat_totalTackles",
        "stat_tacklepct": "stat_tacklePct",
        "stat_effectiveclearance": "stat_effectiveClearance",
        "stat_totalclearance": "stat_totalClearance",
    }
    frame = frame.rename(columns=rename)
    frame["team_norm"] = frame["team"].map(normalize_text)
    frame["source_file"] = frame["espn_event_id"].map(files)
    frame["temporal_status"] = "POST_MATCH_BACKFILLED_FACT"
    preferred = [
        "jogo", "jogo_original_fonte", "espn_event_id", "team", "team_espn", "team_norm",
    ]
    remainder = [column for column in frame.columns if column not in preferred]
    frame = frame[preferred + remainder]
    return frame.sort_values(["jogo", "team_norm"]).reset_index(drop=True)


def transform_events(processed: Path, mapping: dict[int, int], files: dict[int, str]) -> pd.DataFrame:
    frame = remap_game(pd.read_csv(processed / "match_events.csv"), mapping)
    frame["source_file"] = frame["espn_event_id"].map(files)
    frame["source_collected_at"] = frame["collected_at"]
    frame["temporal_status"] = "POST_MATCH_BACKFILLED_FACT"
    return frame.sort_values(["jogo", "period", "event_id", "clock"], na_position="last").reset_index(drop=True)


def transform_commentary(processed: Path, mapping: dict[int, int], files: dict[int, str]) -> pd.DataFrame:
    frame = remap_game(pd.read_csv(processed / "match_commentary.csv"), mapping)
    frame["source_file"] = frame["espn_event_id"].map(files)
    frame["source_collected_at"] = frame["collected_at"]
    frame["temporal_status"] = "POST_MATCH_BACKFILLED_FACT"
    return frame.sort_values(["jogo", "sequence"]).reset_index(drop=True)


def transform_players(processed: Path, mapping: dict[int, int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = remap_game(pd.read_csv(processed / "player_match_stats.csv"), mapping)
    source["player_id"] = source["athlete_id"].map(lambda value: f"espn:{int(value)}" if not pd.isna(value) else "NA")
    source["match_id"] = source["jogo"].astype(int)
    source["competition_id"] = "world_cup_2026"
    source["season"] = 2026
    source["player_name"] = source["player"]
    source["minutes"] = "NA"
    source["goals"] = source["stat_totalgoals"]
    source["assists"] = source["stat_goalassists"]
    source["shots"] = source["stat_totalshots"]
    source["xg"] = "NA"
    source["xa"] = "NA"
    source["rating"] = "NA"
    source["source"] = source["source_url"]
    source["source_collected_at"] = source["collected_at"]
    source["temporal_status"] = "POST_MATCH_BACKFILLED_FACT"

    player_columns = [
        "competition_id", "season", "match_id", "jogo_original_fonte", "espn_event_id", "team", "team_espn",
        "player_id", "athlete_id", "player_name", "jersey", "position", "starter", "active", "subbed_in",
        "subbed_out", "captain", "minutes", "goals", "assists", "shots", "xg", "xa", "rating",
        "stat_appearances", "stat_foulscommitted", "stat_foulssuffered", "stat_owngoals", "stat_redcards",
        "stat_subins", "stat_yellowcards", "stat_goalsconceded", "stat_saves", "stat_shotsfaced",
        "stat_shotsontarget", "stat_offsides", "source", "source_collected_at", "temporal_status",
    ]
    players = source[player_columns].sort_values(["match_id", "team", "starter", "jersey"], ascending=[True, True, False, True])

    lineups = source[
        [
            "competition_id", "season", "match_id", "jogo_original_fonte", "espn_event_id", "team", "team_espn",
            "player_id", "player_name", "starter", "position", "jersey", "active", "subbed_in", "subbed_out",
            "source", "source_collected_at", "temporal_status",
        ]
    ].copy()
    # Do not backdate the lineup: the only trustworthy timestamp in this package is collection time.
    lineups["available_at"] = lineups["source_collected_at"]
    lineups = lineups.sort_values(["match_id", "team", "starter", "jersey"], ascending=[True, True, False, True])
    return players.reset_index(drop=True), lineups.reset_index(drop=True)


def transform_officials(processed: Path, mapping: dict[int, int]) -> pd.DataFrame:
    source = remap_game(pd.read_csv(processed / "match_officials.csv"), mapping)
    source["competition_id"] = "world_cup_2026"
    source["season"] = 2026
    source["match_id"] = source["jogo"]
    source["source"] = source["source_url"]
    source["source_collected_at"] = source["collected_at"]
    source["available_at"] = source["collected_at"]
    source["temporal_status"] = "POST_MATCH_BACKFILLED_FACT"
    columns = [
        "competition_id", "season", "match_id", "jogo_original_fonte", "espn_event_id", "official_id",
        "official", "role", "source", "source_collected_at", "available_at", "temporal_status",
    ]
    return source[columns].sort_values("match_id").reset_index(drop=True)


def transform_generic(processed: Path, filename: str, mapping: dict[int, int], sort: list[str]) -> pd.DataFrame:
    frame = remap_game(pd.read_csv(processed / filename), mapping)
    valid_sort = [column for column in sort if column in frame.columns]
    return frame.sort_values(valid_sort).reset_index(drop=True) if valid_sort else frame


def build_matches_master(validated: pd.DataFrame, datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    matches = pd.read_csv(ROOT / "data/matches.csv")
    result_columns = [
        "jogo", "gols1_real", "gols2_real", "placar_real", "gols1_90", "gols2_90", "vencedor_real",
        "status_real", "decision_method", "placar_penaltis_real", "vencedor_penaltis_real", "espn_event_id",
        "collected_at", "source_sha256", "validation_status", "confidence", "review_required", "fonte",
        "source_secondary", "canonical_result_agrees",
    ]
    result_columns = [column for column in result_columns if column in validated.columns]
    master = matches.merge(validated[result_columns], on="jogo", how="left", validate="one_to_one")
    cover = {
        "has_events": datasets["events"].groupby("jogo").size(),
        "has_commentary": datasets["commentary"].groupby("jogo").size(),
        "has_team_stats": datasets["team_stats"].groupby("jogo").size(),
        "has_player_data": datasets["players"].groupby("match_id").size(),
        "has_officials": datasets["officials"].groupby("match_id").size(),
        "has_penalty_kicks": datasets["penalties"].groupby("jogo").size(),
    }
    for column, counts in cover.items():
        master[column] = master["jogo"].map(counts).fillna(0).astype(int) > 0
    return master.sort_values("jogo").reset_index(drop=True)


def copy_raw_and_audit(package_root: Path) -> list[Path]:
    raw_source = package_root / "dataset_final/raw"
    raw_target = ROOT / "data/raw/wc2026_complete_20260720"
    if raw_target.exists():
        shutil.rmtree(raw_target)
    shutil.copytree(raw_source, raw_target)

    audit_target = ROOT / "data/audit/wc2026_complete_20260720"
    if audit_target.exists():
        shutil.rmtree(audit_target)
    audit_target.mkdir(parents=True, exist_ok=True)
    for source in [
        package_root / "MANIFEST_SHA256.csv",
        package_root / "dataset_final/audit/data_dictionary.csv",
        package_root / "dataset_final/audit/fifa_fetch_metadata.json",
        package_root / "dataset_final/audit/raw_manifest.jsonl",
        package_root / "dataset_final/audit/validation_summary.json",
        package_root / "dataset_final/reports/quality_checks.csv",
        package_root / "dataset_final/reports/extraction_summary.json",
        package_root / "dataset_final/reports/data_conflicts.csv",
        package_root / "dataset_final/reports/data_gaps.csv",
        package_root / "dataset_final/reports/summary_failures.csv",
    ]:
        shutil.copy2(source, audit_target / source.name)

    notebook_source = package_root / "notebook/extracao_copa_2026_independente.ipynb"
    notebook_target = ROOT / "notebooks/extracao_copa_2026_independente.ipynb"
    shutil.copy2(notebook_source, notebook_target)
    return [path for path in raw_target.rglob("*") if path.is_file()] + [path for path in audit_target.iterdir() if path.is_file()] + [notebook_target]


def update_catalog() -> None:
    path = ROOT / "data/catalog.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    datasets = payload.setdefault("datasets", {})
    datasets.update(
        {
            "validated_results_evidence": {"canonical": "data/normalized/results_validated.csv"},
            "match_events": {"canonical": "data/normalized/espn_match_events.csv"},
            "match_commentary": {"canonical": "data/normalized/espn_match_commentary.csv"},
            "team_match_stats": {"canonical": "data/normalized/espn_team_match_stats.csv"},
            "player_match_stats": {"canonical": "data/platform/player_match_stats.csv"},
            "lineups_observed": {"canonical": "data/platform/lineups.csv", "temporal_policy": "collection timestamp is not backdated"},
            "match_officials": {"canonical": "data/platform/match_officials.csv"},
            "penalty_shootouts": {"canonical": "data/normalized/espn_penalty_shootouts.csv"},
            "raw_complete_package": {
                "canonical": "data/audit/wc2026_complete_20260720/integration_manifest.csv",
                "raw_root": "data/raw/wc2026_complete_20260720/",
                "manifest": "data/audit/wc2026_complete_20260720/MANIFEST_SHA256.csv",
            },
        }
    )
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(payload, path)


def build_output_manifest(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for path in sorted(set(paths)):
        if path.exists() and path.is_file():
            rows.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return pd.DataFrame(rows)


def integrate(package_root: Path) -> dict[str, Any]:
    manifest_check = verify_manifest(package_root)
    processed = package_root / "dataset_final/processed"
    mapping, mapping_frame = build_game_mapping(processed)
    raw_summary = package_root / "dataset_final/raw/espn_summary"
    files = raw_file_map(raw_summary)

    validated = align_validated_results(processed, mapping)
    events = transform_events(processed, mapping, files)
    commentary = transform_commentary(processed, mapping, files)
    team_stats = transform_team_stats(processed, mapping, files)
    players, lineups = transform_players(processed, mapping)
    officials = transform_officials(processed, mapping)
    penalties = transform_generic(processed, "penalty_shootouts.csv", mapping, ["jogo", "kick_number", "event_id"])
    metadata = transform_generic(processed, "match_metadata.csv", mapping, ["jogo"])
    espn_matches = transform_generic(processed, "espn_matches.csv", mapping, ["jogo"])
    event_mapping = transform_generic(processed, "event_mapping_report.csv", mapping, ["jogo"])
    fifa = transform_generic(processed, "fifa_verification.csv", mapping, ["jogo"])

    output_paths: list[Path] = []
    targets = {
        ROOT / "data/normalized/results_validated.csv": validated,
        ROOT / "data/normalized/espn_match_events.csv": events,
        ROOT / "data/normalized/espn_match_commentary.csv": commentary,
        ROOT / "data/normalized/espn_team_match_stats.csv": team_stats,
        ROOT / "data/platform/player_match_stats.csv": players,
        ROOT / "data/platform/lineups.csv": lineups,
        ROOT / "data/platform/match_officials.csv": officials,
        ROOT / "data/normalized/espn_penalty_shootouts.csv": penalties,
        ROOT / "data/normalized/espn_match_metadata.csv": metadata,
        ROOT / "data/normalized/espn_matches.csv": espn_matches,
        ROOT / "data/normalized/espn_event_mapping_report.csv": event_mapping,
        ROOT / "data/normalized/fifa_verification.csv": fifa,
        ROOT / "data/mappings/incoming_game_id_mapping_20260720.csv": mapping_frame,
    }
    datasets = {
        "events": events,
        "commentary": commentary,
        "team_stats": team_stats,
        "players": players,
        "lineups": lineups,
        "officials": officials,
        "penalties": penalties,
    }
    master = build_matches_master(validated, datasets)
    targets[ROOT / "data/normalized/matches_master.csv"] = master

    for path, frame in targets.items():
        atomic_csv(frame, path)
        output_paths.append(path)

    copied = copy_raw_and_audit(package_root)
    output_paths.extend(copied)
    update_catalog()
    output_paths.append(ROOT / "data/catalog.json")

    integration_manifest = build_output_manifest(output_paths)
    manifest_target = ROOT / "data/audit/wc2026_complete_20260720/integration_manifest.csv"
    atomic_csv(integration_manifest, manifest_target)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "INTEGRATED",
        "source_package": package_root.name,
        "source_manifest_validation": manifest_check,
        "canonical_mapping": {
            "mapped_games": len(mapping),
            "id_changes": mapping_frame[mapping_frame["id_changed"]].to_dict(orient="records"),
            "date_differences": mapping_frame[mapping_frame["date_changed"]].to_dict(orient="records"),
            "rule": "unordered canonical team pair; package game ID is never trusted blindly",
        },
        "integrated_counts": {
            "validated_results": len(validated),
            "events": len(events),
            "commentary": len(commentary),
            "team_match_stats": len(team_stats),
            "player_match_stats": len(players),
            "lineups_observed": len(lineups),
            "match_officials": len(officials),
            "penalty_kicks": len(penalties),
            "matches_with_events": int(events["jogo"].nunique()),
            "matches_with_team_stats": int(team_stats["jogo"].nunique()),
            "matches_with_player_stats": int(players["match_id"].nunique()),
            "matches_with_officials": int(officials["match_id"].nunique()),
        },
        "temporal_policy": {
            "lineups_and_player_data": "POST_MATCH_BACKFILLED_FACT",
            "historical_pre_match_availability": "not assumed; source_collected_at remains 2026-07-20",
            "future_leakage_prevention": "worldcup temporal pre-match checks only accept records timestamped before each cutoff",
        },
        "known_limitations": [
            "Player minutes are absent from the source and remain NA.",
            "xG, xA and player ratings are absent and remain NA.",
            "FIFA HTML verification did not produce rendered score confirmations; ESPN scoreboard and summary agreement is preserved.",
            "Referee records include the main referee only.",
        ],
        "outputs": integration_manifest["path"].tolist() + [manifest_target.relative_to(ROOT).as_posix()],
    }
    atomic_json(report, ROOT / "reports/wc2026_complete_data_integration.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path, help="Extracted wc2026_pacote_completo_final directory")
    args = parser.parse_args()
    report = integrate(args.package.resolve())
    print(json.dumps(report["integrated_counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
