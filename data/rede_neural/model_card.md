# CopaMatchNet — Rede neural da Copa 2026

Este repositório usa a rede neural `CopaMatchNet` como fonte única para previsões de jogos.

## Entradas usadas

- calendário e fase do jogo;
- seleções envolvidas;
- embeddings treináveis das seleções;
- força do elenco;
- desempenho agregado dos jogadores;
- competitividade média dos campeonatos dos jogadores;
- experiência, gols pela seleção e indicadores por setor;
- resultados reais já registrados.

## Saídas

A rede prevê:

- saldo de gols;
- total de gols;
- placar arredondado;
- vencedor provável.

## Observação

O front lê `src/rede-neural-data.js`, gerado a partir de `data/rede_neural/previsoes_rede_neural.csv`.
