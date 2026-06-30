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
- **acuracia_vencedor_percentual**: 58.67
- **placar_exato_percentual**: 8.0
- **erro_medio_total_gols**: 2.24
- **erro_medio_xg_total**: 2.011
- **proximidade_media_0_100**: 43.73
- **dias_validados**: 19
- **peso_resultado_anterior**: momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time
- **peso_desempenho**: menções de jogadores/desempenho entram somente após o jogo validado
- **gols_separados**: gols marcados atualizam forma ofensiva; gols sofridos atualizam forma defensiva com dano ajustado pela força ofensiva/rating do adversário; saldo não é usado como atalho principal
- **peso_adversario**: resultado e gols marcados são valorizados contra adversários fortes; gols sofridos contra adversários fortes têm punição reduzida e contra fracos têm punição maior
- **rede_neural_como_calibrador**: rede neural tem peso máximo de 8% e não pode inverter favorito quando xG/rating dão vantagem clara ao outro lado
- **rede_neural**: MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual
- **sklearn_disponivel**: True
- **neural_min_samples**: 16
- **simulations_parameter**: 8000

## Times com maior rating atualizado
- Argentina: 77.865 | momentum 1.317 | jogos 3 | saldo 7
- Suíça: 76.294 | momentum 1.148 | jogos 3 | saldo 4
- Portugal: 76.279 | momentum 0.359 | jogos 3 | saldo 5
- Estados Unidos: 75.431 | momentum 0.174 | jogos 3 | saldo 4
- Brasil: 75.286 | momentum 1.387 | jogos 4 | saldo 7
- Bélgica: 75.252 | momentum 0.644 | jogos 3 | saldo 4
- Países Baixos: 75.225 | momentum 1.066 | jogos 3 | saldo 6
- Espanha: 75.092 | momentum 1.1 | jogos 3 | saldo 5
- Alemanha: 74.337 | momentum 0.071 | jogos 4 | saldo 6
- Inglaterra: 74.115 | momentum 0.926 | jogos 3 | saldo 4
- Croácia: 73.853 | momentum 0.981 | jogos 3 | saldo 0
- Escócia: 73.261 | momentum -0.404 | jogos 3 | saldo -3

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 1-2 / Espanha (baixa)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 1-0 / Estados Unidos (média)
- Jogo 95 (2026-07-07): Argentina x Austrália → 1-0 / Argentina (média)
- Jogo 96 (2026-07-07): Suíça x Colômbia → 1-0 / Suíça (baixa)
- Jogo 97 (2026-07-09): Canadá x França → 1-2 / França (baixa)
- Jogo 98 (2026-07-10): Espanha x Estados Unidos → 1-2 / Estados Unidos (baixa)
- Jogo 99 (2026-07-11): Brasil x México → 0-1 / México (baixa)
- Jogo 100 (2026-07-11): Suíça x Argentina → 1-2 / Argentina (baixa)
- Jogo 101 (2026-07-14): Canadá x Estados Unidos → 1-2 / Estados Unidos (baixa)
- Jogo 102 (2026-07-15): México x Argentina → 1-0 / México (baixa)
- Jogo 103 (2026-07-18): Canadá x Argentina → 1-2 / Argentina (baixa)
- Jogo 104 (2026-07-19): Estados Unidos x México → 0-1 / México (baixa)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
