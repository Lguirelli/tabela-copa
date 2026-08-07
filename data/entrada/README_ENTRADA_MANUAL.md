# Entrada manual de dados da Copa 2026

Esta pasta é a única fonte versionada para novos dados pesquisados da Copa.

## Arquivos ativos

- `novos_resultados.csv`: resultados finalizados ainda não processados. Aceita `vencedor_real`, `placar_penaltis_real` e `vencedor_penaltis_real` para mata-mata decidido nos pênaltis.
- `desempenho_manual.csv`: base manual usada pelo modelo diário. Inclui linhas por jogo e agregados de fase de grupos.
- `desempenho_times_fase_grupos.csv`: snapshot de estudo com desempenho geral das 48 seleções na fase de grupos.
- `desempenho_jogadores_destaques.csv`: jogadores e sinais individuais relevantes para estudo pós-Copa.

## Regra de uso

1. Resultado real nunca é sobrescrito.
2. Dados de desempenho entram somente depois do jogo/fase estar finalizado.
3. Quando houver pênaltis, mantenha o placar do jogo em `gols_time_1` e `gols_time_2`, e coloque a decisão em `placar_penaltis_real` e `vencedor_penaltis_real`.
4. Quando uma estatística não estiver disponível em fonte confiável, use `NA`.

## Fontes principais desta versão

- FOX Sports Team Stats: https://www.foxsports.com/soccer/fifa-world-cup/team-stats?category=standard&groupId=12&season=2026&sort=t_xg&sortOrder=desc
- FOX Sports Player/Team leaders: https://www.foxsports.com/soccer/fifa-world-cup/stats
- Reuters Technical Study Group: https://www.reuters.com/sports/soccer/substitutes-shine-world-cup-group-stage-delivers-goal-feast-2026-06-29/
- Guardian live Germany x Paraguay: https://www.theguardian.com/football/live/2026/jun/29/germany-v-paraguay-world-cup-2026-last-32-live
