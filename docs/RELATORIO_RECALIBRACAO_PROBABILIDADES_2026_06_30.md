# Relatório de recalibração das probabilidades — 2026-06-30

## Objetivo

Reavaliar todos os jogos do repositório para que as probabilidades sejam recalculadas sempre que houver resultado e desempenho disponível, sem manter cards em estado de `precisa_recalculo`.

## Ajustes aplicados

1. **Probabilidade de classificação separada da probabilidade em 90 minutos**
   - `prob_vitoria_equipe1`, `prob_empate` e `prob_vitoria_equipe2` continuam representando o tempo regulamentar.
   - Em mata-mata, foram adicionadas/exportadas:
     - `prob_classificacao_equipe1`
     - `prob_classificacao_equipe2`
     - `prob_penaltis_equipe1_modelo`
     - `vencedor_classificacao_previsto`
   - O `vencedor_previsto` em mata-mata passa a usar a maior probabilidade de classificação.

2. **Força do caminho com peso maior**
   - `feature_schedule_strength_diff` e `feature_opponent_adjusted_points_diff` agora pesam mais na formação do xG.
   - Goleadas contra adversários mais fracos são amortecidas por um fator de credibilidade do caminho.

3. **Rede neural como calibrador, não decisor absoluto**
   - Peso máximo da MLP reduzido de 8% para 3,5%.
   - A rede não deve sobrepor xG, força dos adversários e desempenho recente quando a amostra real ainda é pequena.

4. **Pênaltis com lógica própria**
   - Pênaltis usam mais goleiro, experiência, momentum, memória de desempenho e força do caminho.
   - Pênaltis não copiam diretamente o favoritismo dos 90 minutos.

5. **Sincronização de artefatos**
   - `data/modelo_diario/projecao_chaveamento_completa.csv`
   - `data/modelo_diario/previsoes_dia_a_dia.csv`
   - `src/modelo-diario-data.js`
   - `data/previsoes_modelo.csv`
   - `src/model-data.js`
   - `data/rede_neural/previsoes_rede_neural.csv`
   - `src/rede-neural-data.js`
   - `data/matches.csv`, `data/database/matches.csv`, `data/matches.json`, `src/data.js`

## Exemplo corrigido: jogo 89

Antes, Canadá aparecia como favorito por excesso de peso em desempenho recente bruto. Após a recalibração:

| Campo | Valor |
|---|---:|
| Jogo | 89 |
| Confronto | Canadá x Marrocos |
| Prob. Canadá em 90 min | 36,55% |
| Prob. empate | 28,35% |
| Prob. Marrocos em 90 min | 35,10% |
| Prob. classificação Canadá | 49,41% |
| Prob. classificação Marrocos | 50,59% |
| Vencedor previsto | Marrocos |
| Placar previsto | 1-2 |

## Validação

Arquivos de validação gerados:

- `VALIDACAO_RECALCULO_PROBABILIDADES_2026_06_30.json`
- `VALIDACAO_RECALIBRACAO_CLASSIFICACAO_2026_06_30.json`

Resumo:

- 104 jogos avaliados.
- 76 jogos reais preservados.
- 28 jogos projetados.
- 0 jogos com `precisa_recalculo = Sim`.
- 0 jogos sem probabilidades de 90 minutos.
- 32 jogos de mata-mata com probabilidade de classificação.
- 0 conflitos de chaveamento.
