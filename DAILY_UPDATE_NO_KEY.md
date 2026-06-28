# Atualização diária sem API key e sem proxy

Este repositório foi preparado para atualizar automaticamente os jogos finalizados da Copa 2026.

## O que foi adicionado

- `scripts/daily_extract_finished_matches.py`
- `notebooks/daily_update_finished_matches.ipynb`
- `notebooks/extracao_copa_2026_sem_key_repo_incremental.ipynb`
- `.github/workflows/daily-data-update.yml`
- `requirements-daily.txt`
- `data/mappings/team_name_aliases.csv`
- `data/daily_updates/`

## Regras

- Não usa proxy.
- Não estima resultado, estatística, lesão, escalação ou desempenho.
- Não usa fontes com API key.
- Quando o dado não vier direto da fonte, permanece `NA`.
- Dados de jogos finalizados são marcados como `post_match_only`.
- O script não força scraping quando uma fonte bloqueia ou falha.

## Fonte pública sem chave

O script usa o endpoint público JSON da ESPN para scoreboard da FIFA World Cup:

`https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard`

Quando disponível, também consulta o resumo do jogo:

`https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event=<event_id>`

Esses endpoints não exigem chave, mas são públicos/undocumented. Por isso, se ficarem indisponíveis, o script não inventa dados.

## Como rodar manualmente

Na raiz do repositório:

```bash
pip install -r requirements-daily.txt
python scripts/daily_extract_finished_matches.py --repo-root . --days-back 5 --days-forward 0
```

Para verificar todas as datas passadas do calendário:

```bash
python scripts/daily_extract_finished_matches.py --repo-root . --all-past
```

Para rodar sem internet, usando apenas cache e dados já existentes:

```bash
python scripts/daily_extract_finished_matches.py --repo-root . --offline --all-past
```

## Saídas atualizadas

- `data/daily_updates/finished_matches_espn.csv`
- `data/daily_updates/finished_match_team_stats_espn.csv`
- `data/daily_updates/finished_match_events_espn.csv`
- `data/daily_updates/sources_used_daily.csv`
- `data/daily_updates/request_log_daily.csv`
- `data/daily_updates/last_run_report.md`
- `data/resultados_reais.csv`
- `data/resultados.csv`
- `data/database/matches.csv`

## Trigger diário

O workflow `.github/workflows/daily-data-update.yml` roda diariamente às 09:20 UTC e também pode ser executado manualmente em **Actions > Daily World Cup Data Update > Run workflow**.

## Observação importante

Como a exigência é não usar proxy e não usar API key, a cobertura de estatísticas avançadas pode ser limitada. Se o endpoint público não retornar estatísticas de jogadores ou eventos, os campos ficam `NA`.
