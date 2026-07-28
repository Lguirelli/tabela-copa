from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_complete_package_coverage_and_mapping() -> None:
    mapping = pd.read_csv(ROOT / "data/mappings/incoming_game_id_mapping_20260720.csv")
    assert len(mapping) == 104
    assert mapping["canonical_jogo"].nunique() == 104
    changes = dict(zip(mapping.loc[mapping["id_changed"], "incoming_jogo"], mapping.loc[mapping["id_changed"], "canonical_jogo"]))
    assert changes == {89: 90, 90: 89}

    events = pd.read_csv(ROOT / "data/normalized/espn_match_events.csv")
    commentary = pd.read_csv(ROOT / "data/normalized/espn_match_commentary.csv")
    team_stats = pd.read_csv(ROOT / "data/normalized/espn_team_match_stats.csv")
    players = pd.read_csv(ROOT / "data/platform/player_match_stats.csv")
    officials = pd.read_csv(ROOT / "data/platform/match_officials.csv")
    penalties = pd.read_csv(ROOT / "data/normalized/espn_penalty_shootouts.csv")

    assert (len(events), events["jogo"].nunique()) == (4248, 104)
    assert (len(commentary), commentary["jogo"].nunique()) == (11815, 104)
    assert (len(team_stats), team_stats["jogo"].nunique()) == (208, 104)
    assert team_stats.groupby("jogo").size().eq(2).all()
    assert (len(players), players["match_id"].nunique()) == (5323, 104)
    assert (len(officials), officials["match_id"].nunique()) == (104, 104)
    assert (len(penalties), penalties["jogo"].nunique()) == (40, 4)


def test_player_derived_minutes_keep_provenance_and_no_duplicate_keys() -> None:
    players = pd.read_csv(ROOT / "data/platform/player_match_stats.csv")
    minutes = pd.to_numeric(players["minutes"], errors="coerce")
    assert minutes.notna().all()
    assert minutes.between(0, 120).all()
    assert players["minutes_method"].notna().all()
    assert players["minutes_data_quality"].eq("DERIVED_POST_MATCH").all()
    assert players["minutes_derived_from"].eq("lineups+substitution_events+match_duration").all()
    assert players["xg"].isna().all()
    assert players["xa"].isna().all()
    assert players["rating"].isna().all()
    assert not players.duplicated(["match_id", "team", "player_id"]).any()

    lineups = pd.read_csv(ROOT / "data/platform/lineups.csv")
    assert not lineups.duplicated(["match_id", "team", "player_id"]).any()
    available = pd.to_datetime(lineups["available_at"], utc=True)
    collected = pd.to_datetime(lineups["source_collected_at"], utc=True)
    assert available.equals(collected)
    assert (available >= pd.Timestamp("2026-07-20T00:00:00Z")).all()

    availability = pd.read_csv(ROOT / "data/platform/player_availability.csv")
    assert availability["match_id"].nunique() == 104
    assert availability["status"].eq("AVAILABLE_MATCHDAY_SQUAD").all()
    assert availability["temporal_status"].eq("POST_MATCH_DERIVED_FACT").all()
    assert availability["data_quality"].eq("DERIVED_POST_MATCH").all()
    assert not availability.duplicated(["match_id", "team", "player_name"]).any()


def test_validated_results_are_aligned_to_canonical_results() -> None:
    canonical = pd.read_csv(ROOT / "data/resultados_reais.csv").sort_values("jogo").reset_index(drop=True)
    validated = pd.read_csv(ROOT / "data/normalized/results_validated.csv").sort_values("jogo").reset_index(drop=True)
    assert len(validated) == 104
    for column in ("jogo", "equipe1", "equipe2", "gols1_real", "gols2_real", "placar_real", "vencedor_real"):
        assert canonical[column].astype(str).equals(validated[column].astype(str))
    assert validated["canonical_result_agrees"].astype(bool).all()


def test_integration_report_and_manifest_exist() -> None:
    report = json.loads((ROOT / "reports/wc2026_complete_data_integration.json").read_text(encoding="utf-8"))
    assert report["status"] in {"INTEGRATED", "INTEGRATED_AND_VALIDATED"}
    assert report["source_manifest_validation"]["problems"] == 0
    assert report["integrated_counts"]["matches_with_player_stats"] == 104

    manifest = pd.read_csv(ROOT / "data/audit/wc2026_complete_20260720/integration_manifest.csv")
    assert not manifest.empty
    assert manifest["sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
