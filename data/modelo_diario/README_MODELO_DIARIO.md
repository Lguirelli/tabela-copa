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
- **jogos_com_placar_real_validado**: 92
- **acuracia_vencedor_percentual**: 59.78
- **placar_exato_percentual**: 10.87
- **erro_medio_total_gols**: 2.141
- **erro_medio_xg_total**: 1.959
- **proximidade_media_0_100**: 46.8
- **dias_validados**: 25
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
- **simulations_parameter**: 8000

## Times com maior rating atualizado
- Argentina: 78.057 | momentum 1.454 | jogos 4 | saldo 8
- Portugal: 76.705 | momentum 0.931 | jogos 4 | saldo 6
- Suíça: 76.701 | momentum 1.354 | jogos 4 | saldo 6
- Estados Unidos: 76.094 | momentum 0.805 | jogos 4 | saldo 6
- Espanha: 75.932 | momentum 1.357 | jogos 4 | saldo 8
- Bélgica: 75.762 | momentum 1.111 | jogos 4 | saldo 5
- Países Baixos: 75.104 | momentum 0.588 | jogos 4 | saldo 6
- Inglaterra: 75.022 | momentum 1.462 | jogos 5 | saldo 6
- Brasil: 74.779 | momentum 0.384 | jogos 5 | saldo 6
- Alemanha: 74.41 | momentum 0.09 | jogos 4 | saldo 6
- Colômbia: 73.896 | momentum 1.056 | jogos 4 | saldo 6
- Croácia: 73.552 | momentum 0.182 | jogos 4 | saldo -1

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 0-1 / Espanha (baixa)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 2-1 / Estados Unidos (baixa)
- Jogo 95 (2026-07-07): Argentina x Egito → 2-0 / Argentina (alta)
- Jogo 96 (2026-07-07): Suíça x Colômbia → 1-0 / Suíça (baixa)
- Jogo 97 (2026-07-09): Marrocos x França → 0-1 / França (baixa)
- Jogo 98 (2026-07-10): Espanha x Estados Unidos → 2-1 / Espanha (baixa)
- Jogo 99 (2026-07-11): Brasil x México → 0-1 / México (baixa)
- Jogo 100 (2026-07-11): Suíça x Argentina → 1-2 / Argentina (baixa)
- Jogo 101 (2026-07-14): França x Espanha → 1-2 / Espanha (baixa)
- Jogo 102 (2026-07-15): México x Suíça → 0-1 / Suíça (baixa)
- Jogo 103 (2026-07-18): França x Suíça → 1-0 / França (baixa)
- Jogo 104 (2026-07-19): Espanha x México → 1-0 / Espanha (baixa)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
