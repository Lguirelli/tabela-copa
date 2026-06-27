# Model Card — Rede Neural Copa 2026

## Objetivo
Prever placar, vencedor e tendência de gols em jogos da Copa 2026, usando dados já presentes no repositório.

## Arquitetura
`CopaMatchNet`: rede neural PyTorch com:

- embeddings para seleção 1 e seleção 2;
- variáveis numéricas padronizadas;
- MLP com LayerNorm, SiLU e Dropout;
- saída com dois valores: saldo de gols e total de gols.

## Variáveis consideradas

- força contextual da seleção;
- competitividade média das ligas dos jogadores;
- desempenho proxy dos jogadores;
- intensidade, posse e pressão do técnico;
- ataque, meio, defesa e goleiro;
- experiência, caps e gols pela seleção;
- momentum por data;
- correções de aprendizado;
- arbitragem simulada;
- previsão contextual anterior.

## Limitações
A base de resultados reais ainda é pequena para uma rede profunda. Por isso, a previsão final usa um blend entre a rede neural e o modelo contextual anterior, reduzindo overfit.

## Como treinar

```bash
python scripts/treinar_rede_neural_copa.py
```

## Como aplicar inferência

```bash
python scripts/aplicar_rede_neural_copa.py
```
