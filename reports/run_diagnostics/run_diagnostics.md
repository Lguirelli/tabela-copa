# Diagnóstico das GitHub Actions

Gerado em: `2026-07-22T01:40:38.252574+00:00`
Iterações: **2**
Status geral: **NO_FAILURE_REPRODUCED**

## Resumo das etapas

| Cenário | Iteração | Etapa | Status | Classe | Duração |
|---|---:|---|---|---|---:|
| repository_quality | 1 | pytest | SUCCESS | NONE | 3.900s |
| repository_quality | 1 | validate_repository | SUCCESS | NONE | 1.332s |
| repository_quality | 1 | integrity | SUCCESS | NONE | 0.570s |
| temporal_boundary_replay | 1 | replay_at_pre_worldcup_cutoff | SUCCESS | NONE | 0.931s |
| temporal_boundary_replay | 1 | validate_empty_boundary_indexes | SUCCESS | NONE | 0.605s |
| temporal_boundary_replay | 1 | check_empty_indexes_have_headers | SUCCESS | NONE | 0.510s |
| repository_quality | 2 | pytest | SUCCESS | NONE | 3.696s |
| repository_quality | 2 | validate_repository | SUCCESS | NONE | 1.298s |
| repository_quality | 2 | integrity | SUCCESS | NONE | 0.549s |
| temporal_boundary_replay | 2 | replay_at_pre_worldcup_cutoff | SUCCESS | NONE | 0.919s |
| temporal_boundary_replay | 2 | validate_empty_boundary_indexes | SUCCESS | NONE | 0.547s |
| temporal_boundary_replay | 2 | check_empty_indexes_have_headers | SUCCESS | NONE | 0.558s |

## Falhas recorrentes

Nenhuma falha foi reproduzida.

## Análise estática dos workflows

- **INFO** `01_pre_worldcup_training.yml` / `push_without_rebase` — git push has no rebase retry; global writer concurrency must remain shared.
- **INFO** `02_daily_tournament_simulation.yml` / `push_without_rebase` — git push has no rebase retry; global writer concurrency must remain shared.
- **INFO** `03_post_match_learning.yml` / `push_without_rebase` — git push has no rebase retry; global writer concurrency must remain shared.
- **INFO** `daily_update.yml` / `push_without_rebase` — git push has no rebase retry; global writer concurrency must remain shared.
- **INFO** `model_training.yml` / `push_without_rebase` — git push has no rebase retry; global writer concurrency must remain shared.
- **INFO** `post_match_update.yml` / `push_without_rebase` — git push has no rebase retry; global writer concurrency must remain shared.
- **PASS** `MULTIPLE` / `writer_concurrency` — All 6 write workflows are serialized by repository-write-${{ github.ref }}.
