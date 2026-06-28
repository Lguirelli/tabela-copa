# Copa 2026 — Visualizador com rede neural

Visualizador estático para acompanhar a Copa 2026 com resultados reais e previsões geradas pela rede neural `CopaMatchNet`.

## Páginas

- `grupos-resultados.html` — classificação geral dos grupos.
- `grupos-jogos.html` — lista de jogos da fase de grupos.
- `mata-mata-chave.html` — chaveamento do mata-mata.
- `mata-mata-jogos.html` — lista dos jogos eliminatórios.
- `rede-neural.html` — arquitetura, métricas, treino, desempenho, erros e visualização da rede.

## Fonte de previsão

A previsão exibida no front vem apenas da rede neural:

```txt
data/rede_neural/previsoes_rede_neural.csv
src/rede-neural-data.js
```

A previsão do front é gerada somente pela rede neural.

## Atualização

1. Coloque novas linhas em:

```txt
data/entrada/novos_resultados.csv
```

2. Rode:

```bash
python scripts/atualizar_modelo.py
```

Esse script atualiza os resultados reais, reexecuta o treino da rede neural e exporta os dados para o front.

## Treinar manualmente

```bash
python scripts/treinar_rede_neural_copa.py
```

## Reaplicar a rede treinada

```bash
python scripts/aplicar_rede_neural_copa.py
```

## Estrutura principal

```txt
neural_copa/            código PyTorch da rede
scripts/                automações de atualização e treino
data/rede_neural/       dataset, métricas, checkpoint e previsões da rede
src/rede-neural-data.js export JS consumido pelo front
assets/teams/           bandeiras e ícones das seleções
```

---

## Atualização diária sem API key e sem proxy

Este repositório inclui uma rotina automática para coletar **jogos finalizados** e atualizar os CSVs de resultados sem usar API key e sem criar proxies.

Arquivos principais:

- `scripts/daily_extract_finished_matches.py`
- `.github/workflows/daily-data-update.yml`
- `notebooks/daily_update_finished_matches.ipynb`
- `notebooks/extracao_copa_2026_sem_key_repo_incremental.ipynb`
- `DAILY_UPDATE_NO_KEY.md`

A rotina roda diariamente no GitHub Actions e atualiza:

- `data/resultados_reais.csv`
- `data/resultados.csv`
- `data/database/matches.csv`
- `data/daily_updates/finished_matches_espn.csv`
- `data/daily_updates/sources_used_daily.csv`

Regra aplicada: **sem proxy, sem estimativa e sem API key**. Quando uma informação não vem diretamente da fonte pública, permanece `NA`.
