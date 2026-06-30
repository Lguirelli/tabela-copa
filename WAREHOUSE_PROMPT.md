DATA WAREHOUSE AGENT - FIFA 2026

Objective:
Build a structured, auditable football data warehouse for FIFA 2026.

Rules:
- no simulation
- NA for missing data
- CONFLICTING_DATA for conflicts
- source traceability required

Output tables:
fact_matches
fact_player_performance
fact_events
dim_players
dim_teams
dim_matches

Pipeline must ingest, normalize, validate, enrich.

Sources priority:
FIFA > Opta > ESPN > FBref > Transfermarkt > Reuters/AP
