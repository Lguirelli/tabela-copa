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
- **jogos_com_placar_real_validado**: 75
- **acuracia_vencedor_percentual**: 46.67
- **placar_exato_percentual**: 5.33
- **erro_medio_total_gols**: 2.333
- **erro_medio_xg_total**: 2.002
- **proximidade_media_0_100**: 38.8
- **dias_validados**: 19
- **peso_resultado_anterior**: momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time
- **peso_desempenho**: menções de jogadores/desempenho entram somente após o jogo validado
- **rede_neural**: MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual
- **sklearn_disponivel**: True
- **neural_min_samples**: 16
- **simulations_parameter**: 8000

## Times com maior rating atualizado
- Argentina: 78.073 | momentum 2.009 | jogos 3 | saldo 7
- Portugal: 76.907 | momentum 0.761 | jogos 3 | saldo 5
- Suíça: 76.349 | momentum 1.607 | jogos 3 | saldo 4
- Países Baixos: 75.946 | momentum 1.769 | jogos 3 | saldo 6
- Bélgica: 75.934 | momentum 1.266 | jogos 3 | saldo 4
- Estados Unidos: 75.551 | momentum 0.428 | jogos 3 | saldo 4
- Brasil: 75.533 | momentum 2.005 | jogos 4 | saldo 7
- Espanha: 75.397 | momentum 1.659 | jogos 3 | saldo 5
- Alemanha: 75.385 | momentum 0.25 | jogos 4 | saldo 6
- Inglaterra: 74.419 | momentum 1.393 | jogos 3 | saldo 4
- Croácia: 73.322 | momentum 1.284 | jogos 3 | saldo 0
- Canadá: 73.272 | momentum 1.178 | jogos 4 | saldo 6

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 1-2 / Espanha (alta)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 1-0 / Estados Unidos (média)
- Jogo 95 (2026-07-07): Argentina x Austrália → 1-2 / Austrália (baixa)
- Jogo 96 (2026-07-07): Suíça x Colômbia → 1-0 / Suíça (média)
- Jogo 97 (2026-07-09): Canadá x Paraguai → 1-2 / Paraguai (baixa)
- Jogo 98 (2026-07-10): Portugal x Estados Unidos → 0-0 / Empate (média)
- Jogo 99 (2026-07-11): Brasil x México → 0-1 / México (média)
- Jogo 100 (2026-07-11): Suíça x Argentina → 0-1 / Argentina (média)
- Jogo 101 (2026-07-14): Canadá x Portugal → 1-2 / Portugal (média)
- Jogo 102 (2026-07-15): Brasil x Suíça → 1-2 / Suíça (média)
- Jogo 103 (2026-07-18): Portugal x Suíça → 2-1 / Portugal (média)
- Jogo 104 (2026-07-19): Canadá x Brasil → 1-2 / Brasil (média)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
