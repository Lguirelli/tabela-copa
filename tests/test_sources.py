from sports_engine.sources import _parse_espn_summary


def test_espn_summary_parser_preserves_observed_values():
    payload = {
        "plays": [
            {
                "id": "p1",
                "period": {"number": 1},
                "clock": {"displayValue": "12'"},
                "type": {"id": "goal", "text": "Goal"},
                "team": {"displayName": "Mexico"},
                "participants": [{"athlete": {"displayName": "Jogador Teste"}}],
                "text": "Goal by Jogador Teste",
                "scoringPlay": True,
                "shootout": False,
            }
        ],
        "boxscore": {
            "teams": [
                {
                    "team": {"displayName": "Mexico"},
                    "statistics": [
                        {"name": "possessionPct", "value": 55.5},
                        {"name": "totalShots", "value": 10},
                    ],
                }
            ]
        },
        "rosters": [
            {
                "team": {"displayName": "Mexico"},
                "roster": [
                    {
                        "athlete": {"id": "1", "displayName": "Jogador Teste"},
                        "starter": True,
                        "position": {"abbreviation": "FW"},
                        "statistics": [
                            {"name": "minutes", "value": 90},
                            {"name": "goals", "value": 1},
                        ],
                    }
                ],
            }
        ],
    }
    parsed = _parse_espn_summary(payload, 1, "760415", "https://example.test", "fixture.json")
    assert parsed["events"][0]["scoring_play"] is True
    assert parsed["team_stats"][0]["stat_possessionPct"] == 55.5
    assert parsed["player_stats"][0]["minutes"] == 90
    assert parsed["player_stats"][0]["goals"] == 1
    assert parsed["lineups"][0]["starter"] is True


def test_incremental_merge_keeps_partial_match_records(tmp_path):
    from sports_engine.io import read_table
    from sports_engine.sources import _append_new_records

    target = tmp_path / "events.csv"
    first = [
        {"jogo": 1, "event_id": "a", "text": "first"},
        {"jogo": 1, "event_id": "b", "text": "second"},
    ]
    assert _append_new_records(target, first, (("jogo", "event_id"),)) == 2
    assert _append_new_records(
        target,
        [
            {"jogo": 1, "event_id": "b", "text": "duplicate"},
            {"jogo": 1, "event_id": "c", "text": "third"},
        ],
        (("jogo", "event_id"),),
    ) == 1
    frame = read_table(target)
    assert len(frame) == 3
    assert set(frame["event_id"]) == {"a", "b", "c"}
