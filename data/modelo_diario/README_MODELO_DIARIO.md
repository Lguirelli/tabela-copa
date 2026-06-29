# Modelo neural diário — Copa 2026
Este modelo foi gerado para prever jogo a jogo sem usar previsões ou simulações anteriores como entrada.

## O que o script faz
1. Lê elenco, força, estilo tático, calendário e árbitros agregados.
2. Ordena os jogos por data e número do jogo.
3. Antes de cada partida, gera xG, placar provável e probabilidades.
4. Depois da previsão, se existir placar real, valida e atualiza rating/momentum/desempenho.
5. O resultado anterior da seleção pesa nos próximos jogos do mesmo time.

## Arquivos gerados
- `features_times_iniciais.csv`
- `previsoes_dia_a_dia.csv`
- `validacao_dia_a_dia.csv`
- `resumo_diario_validacao.csv`
- `estado_times_dia_a_dia.csv`
- `metricas_modelo.json`
- `../../src/modelo-diario-data.js`

## Métricas da rodada atual
- **modelo**: neural incremental + prior Poisson contextual
- **usa_previsoes_anteriores_como_entrada**: False
- **usa_simulacoes_anteriores_como_entrada**: False
- **validacao_sem_vazamento**: True
- **jogos_previstos**: 104
- **jogos_com_placar_real_validado**: 73
- **acuracia_vencedor_percentual**: 52.05
- **placar_exato_percentual**: 6.85
- **erro_medio_total_gols**: 2.301
- **erro_medio_xg_total**: 2.036
- **proximidade_media_0_100**: 40.36
- **dias_validados**: 18
- **peso_resultado_anterior**: momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time
- **peso_desempenho**: menções de jogadores/desempenho entram somente após o jogo validado
- **rede_neural**: MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual
- **sklearn_disponivel**: True
- **neural_min_samples**: 16
- **simulations_parameter**: 8000

## Times com maior rating atualizado
- Argentina: 78.086 | momentum 2.095 | jogos 3 | saldo 7
- Portugal: 76.743 | momentum 0.772 | jogos 3 | saldo 5
- Suíça: 76.549 | momentum 1.631 | jogos 3 | saldo 4
- Bélgica: 76.077 | momentum 1.422 | jogos 3 | saldo 4
- Países Baixos: 75.952 | momentum 1.776 | jogos 3 | saldo 6
- Alemanha: 75.508 | momentum 0.461 | jogos 3 | saldo 6
- Estados Unidos: 75.495 | momentum 0.469 | jogos 3 | saldo 4
- Espanha: 75.296 | momentum 1.741 | jogos 3 | saldo 5
- Brasil: 75.048 | momentum 1.767 | jogos 3 | saldo 6
- Inglaterra: 74.426 | momentum 1.5 | jogos 3 | saldo 4
- Colômbia: 73.463 | momentum 1.041 | jogos 3 | saldo 3
- França: 73.296 | momentum 2.474 | jogos 3 | saldo 8

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Colômbia x Espanha → 0-1 / Espanha (alta)
- Jogo 94 (2026-07-06): Estados Unidos x Argélia → 1-0 / Estados Unidos (alta)
- Jogo 95 (2026-07-07): Argentina x Irã → 1-0 / Argentina (alta)
- Jogo 96 (2026-07-07): Suíça x Portugal → 1-0 / Suíça (baixa)
- Jogo 97 (2026-07-09): Países Baixos x Alemanha → 0-0 / Empate (média)
- Jogo 98 (2026-07-10): Espanha x Estados Unidos → 2-1 / Espanha (baixa)
- Jogo 99 (2026-07-11): Brasil x México → 2-1 / Brasil (baixa)
- Jogo 100 (2026-07-11): Argentina x Portugal → 0-0 / Empate (média)
- Jogo 101 (2026-07-14): Alemanha x Estados Unidos → 2-1 / Alemanha (baixa)
- Jogo 102 (2026-07-15): México x Portugal → 1-2 / Portugal (média)
- Jogo 103 (2026-07-18): Alemanha x México → 2-1 / Alemanha (baixa)
- Jogo 104 (2026-07-19): Estados Unidos x Portugal → 1-2 / Portugal (média)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
