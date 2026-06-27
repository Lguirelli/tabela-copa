# Atualização completa de 26/06/2026

Entradas processadas a partir dos CSVs enviados:

- jogos_26-06_resultados_e_desempenho.csv
- desempenho_jogadores_26-06.csv

## Jogos reais adicionados/confirmados

- Noruega 1 x 4 França
- Senegal 5 x 0 Iraque
- Cabo Verde 0 x 0 Arábia Saudita
- Uruguai 0 x 1 Espanha

## Estado do modelo após atualização

- Jogos com resultado real: 64
- Correções registradas: 64
- Proximidade média: 23.3%
- Acerto de vencedor: 34.4%
- Placar exato: 7.8%
- Última entrada real: 2026-06-26

## Efeito esperado

Os resultados reais atualizam `correcoes_modelo.csv`, `model_state.json`, força contextual por seleção, previsões futuras, mata-mata e rede neural PyTorch. O desempenho individual dos jogadores foi incorporado à base de desempenho e passa a influenciar a variável de desempenho dos jogadores no modelo contextual.
