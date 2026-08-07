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
- **jogos_com_placar_real_validado**: 104
- **acuracia_vencedor_percentual**: 63.46
- **placar_exato_percentual**: 14.42
- **erro_medio_total_gols**: 2.058
- **erro_medio_xg_total**: 1.97
- **proximidade_media_0_100**: 49.73
- **dias_validados**: 34
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
- Argentina: 78.841 | momentum 0.55 | jogos 8 | saldo 11
- Espanha: 78.02 | momentum 1.662 | jogos 8 | saldo 13
- Portugal: 76.289 | momentum 0.15 | jogos 5 | saldo 5
- Suíça: 76.188 | momentum 0.254 | jogos 6 | saldo 4
- Bélgica: 76.133 | momentum 0.399 | jogos 6 | saldo 7
- Estados Unidos: 75.401 | momentum 0.054 | jogos 5 | saldo 3
- Inglaterra: 75.312 | momentum 1.007 | jogos 8 | saldo 8
- Países Baixos: 75.104 | momentum 0.588 | jogos 4 | saldo 6
- Brasil: 74.779 | momentum 0.384 | jogos 5 | saldo 6
- Alemanha: 74.41 | momentum 0.09 | jogos 4 | saldo 6
- Croácia: 73.552 | momentum 0.182 | jogos 4 | saldo -1
- Colômbia: 73.524 | momentum 0.593 | jogos 5 | saldo 4

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 0-1 / Espanha (baixa)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 2-1 / Estados Unidos (baixa)
- Jogo 95 (2026-07-07): Argentina x Egito → 2-0 / Argentina (alta)
- Jogo 96 (2026-07-07): Suíça x Colômbia → 1-0 / Suíça (baixa)
- Jogo 97 (2026-07-09): França x Marrocos → 1-0 / França (baixa)
- Jogo 98 (2026-07-10): Espanha x Bélgica → 2-1 / Espanha (baixa)
- Jogo 99 (2026-07-11): Noruega x Inglaterra → 1-2 / Inglaterra (baixa)
- Jogo 100 (2026-07-11): Argentina x Suíça → 2-1 / Argentina (baixa)
- Jogo 101 (2026-07-14): França x Espanha → 1-2 / Espanha (baixa)
- Jogo 102 (2026-07-15): Inglaterra x Argentina → 1-2 / Argentina (baixa)
- Jogo 103 (2026-07-18): França x Inglaterra → 1-2 / Inglaterra (baixa)
- Jogo 104 (2026-07-19): Espanha x Argentina → 2-1 / Espanha (baixa)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
