# Cérebro preditivo temporal da Copa 2026

## Princípio central

A reconstrução é **walk-forward**. Cada previsão possui um `prediction_at`; somente registros cujo `available_at` seja anterior ou igual a esse instante podem ser usados. O resultado do próprio jogo é liberado apenas em `result_available_at`.

O motor não tenta esconder que parte da base foi compilada retrospectivamente. Dados estáticos que descrevem o período pré-Copa são marcados como `BACKFILLED_PRE_TOURNAMENT_FACT`. Resultados, eventos ou estatísticas da competição nunca são retrodatados.

## Fluxo

1. `prepare`: constrói o estado pré-Copa e a linha do tempo.
2. `collect`: verifica a fila de informações e aceita somente fontes com timestamp histórico compatível.
3. `replay`: executa previsões, liberação de resultados e análises pós-jogo na ordem temporal.
4. `validate`: verifica vazamento futuro, duplicidade, visibilidade do mata-mata e workflows.

```bash
python -m worldcup_brain.cli prepare
python -m worldcup_brain.cli replay
python -m worldcup_brain.cli validate
```

Replay parcial:

```bash
python -m worldcup_brain.cli replay --as-of "2026-06-25T23:59:59-04:00"
```

## Artefatos principais

- `data/pre_worldcup_state/teams.csv`
- `data/pre_worldcup_state/players.csv`
- `data/pre_worldcup_state/context.csv`
- `data/temporal/matches_timeline.csv`
- `data/temporal/missing_information_queue.json`
- `data/temporal/prediction_knowledge_ledger.csv`
- `predictions/pre_match/match_XXX.json`
- `learning/game_analysis/match_XXX.json`
- `learning/causal_analysis/match_XXX.json`
- `learning/result_significance/match_XXX.json`
- `models/versions/`
- `simulations/daily/`
- `reports/worldcup_learning_report.json`
- `reports/temporal_validation_report.json`

## Mata-mata sem vazamento

Os times dos jogos 73–88 só ficam visíveis após o jogo 72. Nas fases seguintes, o confronto só fica visível depois que os jogos-pais terminam. A simulação prévia à conclusão dos grupos publica probabilidades de classificação, mas não usa os confrontos oficiais futuros.

## Interpretação causal

A análise causal usa primeiro gol, cartões, finalizações, posse e eficiência quando disponíveis. Os resultados são descritos como associações observacionais, nunca como prova causal definitiva.

## Campos ausentes

Ranking pré-Copa, forma recente, lesões, minutos recentes, clima e viagem permanecem `NA` quando não existe uma fonte arquivada com `published_at` anterior ao cutoff. O pipeline pode coletar fontes atuais, mas não as usa para reescrever historicamente uma previsão antiga.
