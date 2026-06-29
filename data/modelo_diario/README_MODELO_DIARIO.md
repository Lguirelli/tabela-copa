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
- **jogos_com_placar_real_validado**: 74
- **acuracia_vencedor_percentual**: 51.35
- **placar_exato_percentual**: 6.76
- **erro_medio_total_gols**: 2.324
- **erro_medio_xg_total**: 2.018
- **proximidade_media_0_100**: 40.43
- **dias_validados**: 19
- **peso_resultado_anterior**: momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time
- **peso_desempenho**: menções de jogadores/desempenho entram somente após o jogo validado
- **rede_neural**: MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual
- **sklearn_disponivel**: True
- **neural_min_samples**: 16
- **simulations_parameter**: 8000

## Times com maior rating atualizado
- Argentina: 78.517 | momentum 2.314 | jogos 3 | saldo 7
- Suíça: 76.837 | momentum 1.76 | jogos 3 | saldo 4
- Portugal: 76.729 | momentum 0.858 | jogos 3 | saldo 5
- Países Baixos: 76.326 | momentum 1.913 | jogos 3 | saldo 6
- Bélgica: 76.289 | momentum 1.717 | jogos 3 | saldo 4
- Brasil: 75.941 | momentum 2.435 | jogos 4 | saldo 7
- Estados Unidos: 75.678 | momentum 0.58 | jogos 3 | saldo 4
- Espanha: 75.461 | momentum 1.926 | jogos 3 | saldo 5
- Alemanha: 75.427 | momentum 0.528 | jogos 3 | saldo 6
- Inglaterra: 74.726 | momentum 1.706 | jogos 3 | saldo 4
- França: 74.001 | momentum 2.5 | jogos 3 | saldo 8
- Colômbia: 73.964 | momentum 1.278 | jogos 3 | saldo 3

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 1-2 / Espanha (alta)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 1-0 / Estados Unidos (alta)
- Jogo 95 (2026-07-07): Argentina x Egito → 1-0 / Argentina (alta)
- Jogo 96 (2026-07-07): Suíça x Gana → 1-0 / Suíça (alta)
- Jogo 97 (2026-07-09): Canadá x Alemanha → 1-2 / Alemanha (média)
- Jogo 98 (2026-07-10): Portugal x Estados Unidos → 2-1 / Portugal (média)
- Jogo 99 (2026-07-11): Brasil x Equador → 1-0 / Brasil (alta)
- Jogo 100 (2026-07-11): Argentina x Gana → 1-0 / Argentina (alta)
- Jogo 101 (2026-07-14): Alemanha x Portugal → 0-1 / Portugal (baixa)
- Jogo 102 (2026-07-15): Equador x Argentina → 2-1 / Equador (baixa)
- Jogo 103 (2026-07-18): Portugal x Argentina → 2-1 / Portugal (média)
- Jogo 104 (2026-07-19): Alemanha x Equador → 1-0 / Alemanha (alta)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
