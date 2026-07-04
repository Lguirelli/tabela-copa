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
- **jogos_com_placar_real_validado**: 88
- **acuracia_vencedor_percentual**: 61.36
- **placar_exato_percentual**: 9.09
- **erro_medio_total_gols**: 2.136
- **erro_medio_xg_total**: 1.949
- **proximidade_media_0_100**: 46.91
- **dias_validados**: 23
- **peso_resultado_anterior**: momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time
- **peso_desempenho**: menções de jogadores/desempenho entram somente após o jogo validado
- **gols_separados**: gols marcados atualizam forma ofensiva; gols sofridos atualizam forma defensiva com dano ajustado pela força ofensiva/rating do adversário; saldo não é usado como atalho principal
- **peso_adversario**: resultado e gols marcados são valorizados contra adversários fortes; gols sofridos contra adversários fortes têm punição reduzida e contra fracos têm punição maior
- **rede_neural_como_calibrador**: rede neural tem peso máximo de 8% e não pode inverter favorito quando xG/rating dão vantagem clara ao outro lado
- **placar_representativo**: placar exibido é escolhido dentro do resultado mais provável, considerando probabilidade, xG, margem e variação determinística; o placar modal bruto é preservado em placar_modal_bruto
- **probabilidade_penaltis**: em mata-mata calcula P(pênaltis) como P(empate em 90 minutos) vezes P(empate na prorrogação aproximada por xG/3)
- **rede_neural**: MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual
- **sklearn_disponivel**: True
- **neural_min_samples**: 16
- **simulations_parameter**: 12000

## Times com maior rating atualizado
- Argentina: 78.045 | momentum 1.452 | jogos 4 | saldo 8
- Suíça: 76.704 | momentum 1.355 | jogos 4 | saldo 6
- Portugal: 76.698 | momentum 0.926 | jogos 4 | saldo 6
- Estados Unidos: 76.096 | momentum 0.806 | jogos 4 | saldo 6
- Espanha: 75.933 | momentum 1.357 | jogos 4 | saldo 8
- Bélgica: 75.763 | momentum 1.112 | jogos 4 | saldo 5
- Brasil: 75.334 | momentum 1.41 | jogos 4 | saldo 7
- Países Baixos: 75.101 | momentum 0.588 | jogos 4 | saldo 6
- Inglaterra: 74.482 | momentum 1.253 | jogos 4 | saldo 5
- Alemanha: 74.391 | momentum 0.084 | jogos 4 | saldo 6
- Colômbia: 73.896 | momentum 1.057 | jogos 4 | saldo 6
- Croácia: 73.562 | momentum 0.187 | jogos 4 | saldo -1

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 0-1 / Espanha (baixa)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 2-1 / Estados Unidos (baixa)
- Jogo 95 (2026-07-07): Argentina x Egito → 2-0 / Argentina (alta)
- Jogo 96 (2026-07-07): Suíça x Colômbia → 1-0 / Suíça (baixa)
- Jogo 97 (2026-07-09): Canadá x França → 1-2 / França (baixa)
- Jogo 98 (2026-07-10): Portugal x Estados Unidos → 2-1 / Portugal (baixa)
- Jogo 99 (2026-07-11): Brasil x México → 1-1 / Empate (baixa)
- Jogo 100 (2026-07-11): Suíça x Argentina → 1-2 / Argentina (baixa)
- Jogo 101 (2026-07-14): França x Portugal → 1-2 / Portugal (baixa)
- Jogo 102 (2026-07-15): Brasil x Argentina → 2-1 / Brasil (baixa)
- Jogo 103 (2026-07-18): França x Argentina → 1-2 / Argentina (baixa)
- Jogo 104 (2026-07-19): Portugal x Brasil → 0-1 / Brasil (baixa)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
