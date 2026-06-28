# Copa 2026 — Visualizador com rede neural

Visualizador estático para acompanhar a Copa 2026 com resultados reais e previsões geradas pela rede neural `CopaMatchNet`.

## Páginas

- `grupos-resultados.html` — classificação geral dos grupos.
- `grupos-jogos.html` — lista de jogos da fase de grupos.
- `mata-mata-chave.html` — chaveamento do mata-mata.
- `mata-mata-jogos.html` — lista dos jogos eliminatórios.
- `rede-neural.html` — arquitetura, métricas, treino, desempenho, erros e visualização da rede.

## Fonte de previsão

A previsão exibida no front vem apenas da rede neural:

```txt
data/rede_neural/previsoes_rede_neural.csv
src/rede-neural-data.js
```

A previsão do front é gerada somente pela rede neural.

## Atualização

1. Coloque novas linhas em:

```txt
data/entrada/novos_resultados.csv
```

2. Rode:

```bash
python scripts/atualizar_modelo.py
```

Esse script atualiza os resultados reais, reexecuta o treino da rede neural e exporta os dados para o front.

## Treinar manualmente

```bash
python scripts/treinar_rede_neural_copa.py
```

## Reaplicar a rede treinada

```bash
python scripts/aplicar_rede_neural_copa.py
```

## Estrutura principal

```txt
neural_copa/            código PyTorch da rede
scripts/                automações de atualização e treino
data/rede_neural/       dataset, métricas, checkpoint e previsões da rede
src/rede-neural-data.js export JS consumido pelo front
assets/teams/           bandeiras e ícones das seleções
```
