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
- **jogos_com_placar_real_validado**: 76
- **acuracia_vencedor_percentual**: 56.58
- **placar_exato_percentual**: 9.21
- **erro_medio_total_gols**: 2.303
- **erro_medio_xg_total**: 1.989
- **proximidade_media_0_100**: 43.18
- **dias_validados**: 19
- **peso_resultado_anterior**: momentum por seleção atualizado após cada placar real e usado no próximo jogo do mesmo time
- **peso_desempenho**: menções de jogadores/desempenho entram somente após o jogo validado
- **gols_separados**: gols marcados atualizam forma ofensiva; gols sofridos atualizam forma defensiva com dano ajustado pela força ofensiva/rating do adversário; saldo não é usado como atalho principal
- **peso_adversario**: resultado e gols marcados são valorizados contra adversários fortes; gols sofridos contra adversários fortes têm punição reduzida e contra fracos têm punição maior
- **recalibracao_forca_caminho**: a força média dos adversários e os pontos ajustados por adversário têm peso maior no mata-mata; goleadas contra adversários fracos são amortecidas
- **probabilidade_classificacao**: em mata-mata, o modelo calcula chance de avançar separada da chance de vitória no tempo regulamentar
- **rede_neural_como_calibrador**: rede neural tem peso máximo de 3,5% e não pode sobrepor xG, força do caminho e desempenho recente
- **rede_neural**: MLPClassifier sequencial quando há amostra real mínima; antes disso usa prior contextual
- **sklearn_disponivel**: False
- **neural_min_samples**: 16
- **simulations_parameter**: 8000

## Times com maior rating atualizado
- Argentina: 77.74 | momentum 1.304 | jogos 3 | saldo 7
- Portugal: 76.297 | momentum 0.356 | jogos 3 | saldo 5
- Suíça: 76.206 | momentum 1.13 | jogos 3 | saldo 4
- Estados Unidos: 75.703 | momentum 0.206 | jogos 3 | saldo 4
- Brasil: 75.299 | momentum 1.385 | jogos 4 | saldo 7
- Bélgica: 75.276 | momentum 0.651 | jogos 3 | saldo 4
- Espanha: 75.13 | momentum 1.11 | jogos 3 | saldo 5
- Países Baixos: 75.054 | momentum 0.576 | jogos 4 | saldo 6
- Alemanha: 74.37 | momentum 0.076 | jogos 4 | saldo 6
- Inglaterra: 74.094 | momentum 0.927 | jogos 3 | saldo 4
- Croácia: 73.807 | momentum 0.981 | jogos 3 | saldo 0
- Escócia: 73.309 | momentum -0.401 | jogos 3 | saldo -3

## Últimas previsões processadas
- Jogo 93 (2026-07-06): Portugal x Espanha → 1-2 / Espanha (baixa)
- Jogo 94 (2026-07-06): Estados Unidos x Bélgica → 1-0 / Estados Unidos (média)
- Jogo 95 (2026-07-07): Argentina x Austrália → 1-0 / Argentina (alta)
- Jogo 96 (2026-07-07): Suíça x Colômbia → 1-0 / Suíça (média)
- Jogo 97 (2026-07-09): Marrocos x França → 0-1 / França (média)
- Jogo 98 (2026-07-10): Espanha x Estados Unidos → 2-1 / Espanha (baixa)
- Jogo 99 (2026-07-11): Brasil x México → 1-0 / Brasil (média)
- Jogo 100 (2026-07-11): Suíça x Argentina → 0-1 / Argentina (média)
- Jogo 101 (2026-07-14): França x Espanha → 2-1 / França (baixa)
- Jogo 102 (2026-07-15): Brasil x Argentina → 2-1 / Brasil (baixa)
- Jogo 103 (2026-07-18): França x Brasil → 1-2 / Brasil (média)
- Jogo 104 (2026-07-19): Espanha x Argentina → 1-2 / Argentina (média)

## Observação importante
Os arquivos `data/previsoes_modelo.csv`, `data/database/simulated_matches.csv`, `data/database/simulated_referee_assignments.csv` e `data/neural/*` não são usados como entrada deste modelo.
