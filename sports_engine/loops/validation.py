from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CompetitionConfig, ROOT
from ..io import find_column, is_missing, read_table, write_json_copies
from ..lineage import metadata


def _issue(level: str, code: str, dataset: str, details: str, records: list[Any] | None = None) -> dict[str, Any]:
    return {"status": level, "code": code, "dataset": dataset, "details": details, "records": records or []}


def run(config: CompetitionConfig) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    inputs: list[Path] = []
    frames: dict[str, pd.DataFrame] = {}
    for name, rel in config.data.get("datasets", {}).items():
        path = ROOT / str(rel)
        if path.exists():
            inputs.append(path)
            try:
                frames[name] = read_table(path, required=False)
            except Exception as exc:
                issues.append(_issue("INVALID", "PARSE_ERROR", name, str(exc)))
        elif name in {"matches", "results", "predictions"}:
            issues.append(_issue("INVALID", "MISSING_REQUIRED_DATASET", name, f"Missing {path.relative_to(ROOT)}"))

    for name, frame in frames.items():
        if frame.empty:
            continue
        exact_duplicates = frame[frame.duplicated(keep=False)]
        if not exact_duplicates.empty:
            issues.append(_issue(
                "INVALID",
                "EXACT_DUPLICATE_ROWS",
                name,
                "Byte-equivalent structured rows appear more than once in the dataset",
                exact_duplicates.index.astype(int).tolist()[:100],
            ))

    matches = frames.get("matches", pd.DataFrame())
    results = frames.get("results", pd.DataFrame())
    predictions = frames.get("predictions", pd.DataFrame())

    for name, frame in [("matches", matches), ("results", results), ("predictions", predictions)]:
        if frame.empty:
            continue
        id_col = find_column(frame, "jogo", "match_id")
        if not id_col:
            issues.append(_issue("INVALID", "MISSING_MATCH_ID", name, "No match identifier column found"))
            continue
        ids = pd.to_numeric(frame[id_col], errors="coerce")
        if ids.isna().any():
            issues.append(_issue("INVALID", "INVALID_MATCH_ID", name, "Non-numeric or empty match IDs found"))
        duplicated = ids[ids.duplicated()].dropna().astype(int).unique().tolist()
        if duplicated:
            issues.append(_issue("INVALID", "DUPLICATE_MATCH", name, "Duplicate match identifiers", duplicated[:100]))

    if not matches.empty:
        id_col = find_column(matches, "jogo", "match_id")
        team1 = find_column(matches, "equipe1", "team1", "home_team")
        team2 = find_column(matches, "equipe2", "team2", "away_team")
        date_col = find_column(matches, "data", "date", "datetime_utc")
        if team1 and team2:
            same_team = matches[
                matches[team1].astype(str).str.strip().str.casefold()
                == matches[team2].astype(str).str.strip().str.casefold()
            ]
            if not same_team.empty:
                records = same_team[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "SAME_TEAM_MATCH", "matches", "A match cannot contain the same team on both sides", records[:100]))
        if date_col:
            parsed_dates = pd.to_datetime(matches[date_col], errors="coerce")
            invalid_dates = matches[matches[date_col].map(is_missing) | parsed_dates.isna()]
            if not invalid_dates.empty:
                records = invalid_dates[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "INVALID_DATE", "matches", "Missing or unparseable match dates found", records[:100]))

    if not results.empty:
        g1 = find_column(results, "gols1_real", "gols1", "home_score")
        g2 = find_column(results, "gols2_real", "gols2", "away_score")
        source = find_column(results, "fonte", "source", "source_url")
        id_col = find_column(results, "jogo", "match_id")
        if g1 and g2:
            n1 = pd.to_numeric(results[g1], errors="coerce")
            n2 = pd.to_numeric(results[g2], errors="coerce")
            missing_scores = results[results[g1].map(is_missing) | results[g2].map(is_missing) | n1.isna() | n2.isna()]
            if not missing_scores.empty:
                recs = missing_scores[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "MISSING_FINAL_SCORE", "results", "Result rows contain missing or non-numeric scores", recs[:100]))
            invalid = results[(n1 < 0) | (n2 < 0) | ((n1 % 1) != 0) | ((n2 % 1) != 0)]
            if not invalid.empty:
                recs = invalid[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "IMPOSSIBLE_SCORE", "results", "Negative or non-integer goals found", recs[:100]))
        if source:
            missing_source = results[results[source].map(is_missing)]
            if not missing_source.empty:
                recs = missing_source[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "MISSING_LINEAGE", "results", "Observed results without source", recs[:100]))

    if not matches.empty and not results.empty:
        mid = find_column(matches, "jogo", "match_id"); rid = find_column(results, "jogo", "match_id")
        mt1 = find_column(matches, "equipe1", "team1"); mt2 = find_column(matches, "equipe2", "team2")
        rt1 = find_column(results, "equipe1", "team1"); rt2 = find_column(results, "equipe2", "team2")
        if all([mid, rid, mt1, mt2, rt1, rt2]):
            merged = matches[[mid, mt1, mt2]].merge(results[[rid, rt1, rt2]], left_on=mid, right_on=rid, how="inner", suffixes=("_m", "_r"))
            conflict = merged[(merged[f"{mt1}_m"].astype(str) != merged[f"{rt1}_r"].astype(str)) | (merged[f"{mt2}_m"].astype(str) != merged[f"{rt2}_r"].astype(str))]
            if not conflict.empty:
                issues.append(_issue("CONFLICTING_DATA", "TEAM_CONFLICT", "matches/results", "Teams differ for the same match ID", conflict[mid].astype(int).tolist()[:100]))

    if not predictions.empty:
        id_col = find_column(predictions, "jogo", "match_id")
        prob_cols = [col for col in predictions.columns if col.startswith("prob_vitoria_") or col == "prob_empate"]
        for col in prob_cols:
            values = pd.to_numeric(predictions[col], errors="coerce")
            invalid = predictions[values.notna() & ((values < 0) | (values > 1))]
            if not invalid.empty:
                recs = invalid[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "INVALID_PROBABILITY", "predictions", f"{col} outside 0..1", recs[:100]))
        required_probs = [find_column(predictions, "prob_vitoria_equipe1"), find_column(predictions, "prob_empate"), find_column(predictions, "prob_vitoria_equipe2")]
        if all(required_probs):
            total = sum(pd.to_numeric(predictions[col], errors="coerce") for col in required_probs if col)
            invalid = predictions[total.notna() & ((total - 1).abs() > 0.02)]
            if not invalid.empty:
                recs = invalid[id_col].tolist() if id_col else []
                issues.append(_issue("INVALID", "PROBABILITY_SUM", "predictions", "W/D/L probabilities do not sum to 1 within tolerance", recs[:100]))

    composite_keys = {
        "events": [("jogo", "match_id"), ("event_id",)],
        "team_match_stats": [("jogo", "match_id"), ("team_norm", "team", "team_espn")],
        "lineups": [("match_id", "jogo"), ("team", "selecao"), ("player_id", "player_name", "jogador")],
        "player_match_stats": [("match_id", "jogo"), ("team", "selecao"), ("player_id", "player_name", "jogador")],
    }
    for dataset_name, candidate_groups in composite_keys.items():
        frame = frames.get(dataset_name, pd.DataFrame())
        if frame.empty:
            continue
        selected = [find_column(frame, *group) for group in candidate_groups]
        if all(selected):
            key_columns = [column for column in selected if column]
            valid_key = pd.Series(True, index=frame.index)
            for column in key_columns:
                valid_key = valid_key & ~frame[column].map(is_missing)
            duplicate_mask = pd.Series(False, index=frame.index)
            duplicate_mask.loc[valid_key] = frame.loc[valid_key].duplicated(subset=key_columns, keep=False)
            if duplicate_mask.any():
                issues.append(_issue(
                    "INVALID",
                    "DUPLICATE_ENTITY_KEY",
                    dataset_name,
                    f"Duplicate composite keys found for {selected}",
                    frame.index[duplicate_mask].astype(int).tolist()[:100],
                ))

    bounded_fields = {
        "player_match_stats": {
            "minutes": (0, 130), "goals": (0, None), "assists": (0, None),
            "shots": (0, None), "xg": (0, None), "xa": (0, None),
        },
        "team_match_stats": {
            "stat_possessionPct": (0, 100), "posse_pct": (0, 100),
            "stat_totalShots": (0, None), "stat_shotsOnTarget": (0, None),
            "stat_yellowCards": (0, None), "stat_redCards": (0, None),
        },
    }
    for dataset_name, rules in bounded_fields.items():
        frame = frames.get(dataset_name, pd.DataFrame())
        if frame.empty:
            continue
        for candidate, (minimum, maximum) in rules.items():
            column = find_column(frame, candidate)
            if not column:
                continue
            values = pd.to_numeric(frame[column], errors="coerce")
            invalid_mask = values.notna() & (values < minimum)
            if maximum is not None:
                invalid_mask = invalid_mask | (values.notna() & (values > maximum))
            if invalid_mask.any():
                issues.append(_issue(
                    "INVALID",
                    "IMPOSSIBLE_STATISTIC",
                    dataset_name,
                    f"{column} is outside the accepted range {minimum}..{maximum if maximum is not None else 'unbounded'}",
                    frame.index[invalid_mask].astype(int).tolist()[:100],
                ))

    referees = frames.get("referees", pd.DataFrame())
    if not referees.empty:
        synthetic = [col for col in referees.columns if "simulad" in col.lower()]
        if synthetic:
            issues.append(_issue("WARNING", "SYNTHETIC_FIELDS_PRESENT", "referees", "Synthetic fields are isolated from automatic feature discovery and must not be treated as observations", synthetic))

    status = "VALID"
    if any(item["status"] == "INVALID" for item in issues):
        status = "INVALID"
    elif any(item["status"] == "CONFLICTING_DATA" for item in issues):
        status = "CONFLICTING_DATA"
    report = metadata("03_data_validation", config.competition_id, inputs, ROOT, {
        "status": status,
        "summary": {
            "datasets_checked": len(frames),
            "invalid_issues": sum(item["status"] == "INVALID" for item in issues),
            "conflicts": sum(item["status"] == "CONFLICTING_DATA" for item in issues),
            "warnings": sum(item["status"] == "WARNING" for item in issues),
        },
        "issues": issues,
    })
    write_json_copies(
        report,
        config.scoped_path("reports", "validation_report.json"),
        ROOT / "reports" / "validation_report.json",
    )
    return report
