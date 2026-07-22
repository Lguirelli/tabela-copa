# Diagnóstico das GitHub Actions

Gerado em: `2026-07-22T17:17:00.442100+00:00`
Iterações: **1**
Status geral: **NO_FAILURE_REPRODUCED**

## Resumo das etapas

| Cenário | Iteração | Etapa | Status | Classe | Duração |
|---|---:|---|---|---|---:|
| temporal_current | 1 | configure_fast_diagnostic_simulation | SUCCESS | NONE | 0.539s |
| temporal_current | 1 | collect | SUCCESS | NONE | 1.108s |
| temporal_current | 1 | daily_replay | SUCCESS | NONE | 6.370s |
| temporal_current | 1 | validate_current | SUCCESS | NONE | 0.747s |
| temporal_current | 1 | export_dashboard | SUCCESS | NONE | 0.592s |
| temporal_current | 1 | pytest_current | SUCCESS | NONE | 3.606s |

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
