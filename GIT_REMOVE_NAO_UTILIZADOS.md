# Lista de `git rm` para arquivos não utilizados

Esta lista considera o front atual, que carrega apenas:

```txt
src/data.js
src/team-colors.js
src/team-assets.js
src/rede-neural-data.js
src/modelo-diario-data.js
src/prediction-source.js
src/dashboard.js
src/pixi-neural-view.js
src/neural-data-viz.js
src/styles.css
```

## Remoção segura para o front atual

Esses arquivos não são carregados por nenhuma página HTML atual e não fazem parte do fluxo ativo `placar real > modelo diário > rede neural`.

```bat
git rm -- "src/app.js"
git rm -- "src/analysis.js"
git rm -- "src/model-data.js"
git rm -- "src/modelo-dados.js"
git rm -- "src/results.js"
git rm -- "data/analise/matriz_influencia.csv"
git rm -- "data/atualizacoes_entrada_26-06.csv"
git rm -- "data/atualizacoes_entrada_26-06_resultados_desempenho.csv"
git rm -- "docs/analise_deeplearningexamples.md"
git rm -- "docs/analise_dl_visualization_adaptacao.md"
git rm -- "docs/analise_pixijs_visualizacao.md"
git rm -- "VALIDACAO_CORRECAO_FRONTEND.md"
```

## Remoção opcional se for abandonar o pipeline antigo de simulação/contextual

Não execute esta parte se ainda quiser usar `scripts/recalcular_mata_mata.py`, `scripts/recalcular_modelo_contextual.py` ou manter os arquivos históricos de comparação.

```bat
git rm -- "scripts/recalcular_mata_mata.py"
git rm -- "scripts/recalcular_modelo_contextual.py"
git rm -- "data/previsoes_modelo.csv"
git rm -- "data/database/simulated_matches.csv"
git rm -- "data/database/simulated_referee_assignments.csv"
git rm -- "data/modelo/matriz_variaveis.csv"
git rm -- "data/modelo/modelo_times.csv"
git rm -- "data/neural/classificacao_projetada_grupos.csv"
git rm -- "data/neural/correcoes_modelo.csv"
git rm -- "data/neural/debug_mata_mata_atualizado.json"
git rm -- "data/neural/estado_times.csv"
git rm -- "data/neural/melhores_terceiros_projetados.csv"
git rm -- "data/neural/model_state.json"
git rm -- "data/neural/terceiros_colocados_mata_mata.csv"
```

## Remoção opcional de snapshots antigos de desempenho

Mantenha `data/desempenho/jogadores_citados_desempenho_copa_2026.csv`, porque o modelo diário usa esse arquivo como entrada de desempenho. Os demais abaixo são snapshots antigos ou relatórios intermediários.

```bat
git rm -- "data/desempenho/desempenho_jogadores_26-06.csv"
git rm -- "data/desempenho/desempenho_jogadores_26-27_completo.csv"
git rm -- "data/desempenho/desempenho_jogadores_faltantes_27-06.csv"
git rm -- "data/desempenho/jogos_26-06_resultados_e_desempenho.csv"
git rm -- "data/desempenho/jogos_26-27_resultados_e_desempenho.csv"
git rm -- "data/desempenho/jogos_28-06_resultados_e_desempenho.csv"
git rm -- "data/desempenho/jogos_faltantes_resultados_e_desempenho_27-06.csv"
git rm -- "data/desempenho/jogos_finalizados_copa_2026_ate_25-06.csv"
git rm -- "data/desempenho/jogos_finalizados_copa_2026_fase_grupos_completa.csv"
git rm -- "data/desempenho/novos_jogos_finalizados_26-06.csv"
git rm -- "data/desempenho/novos_jogos_finalizados_28-06.csv"
git rm -- "data/desempenho/novos_jogos_finalizados_faltantes_27-06.csv"
git rm -- "data/desempenho/relatorio_atualizacao_26-06_completo.md"
git rm -- "data/desempenho/relatorio_atualizacao_28-06.md"
git rm -- "data/desempenho/relatorio_atualizacao_fase_grupos_completa.md"
git rm -- "data/desempenho/relatorio_atualizacao_jogos_26-06.md"
git rm -- "data/desempenho/resumo_desempenho_por_jogo_copa_2026.csv"
git rm -- "data/desempenho/resumo_desempenho_por_jogo_copa_2026_fase_grupos_completa.csv"
```
