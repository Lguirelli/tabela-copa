# Relatório Patch 2 — limpeza segura de órfãos e legados

Data: 2026-06-30

## Objetivo

Aplicar somente a limpeza segura de arquivos órfãos e legados, preservando documentação histórica e sem reorganizar a arquitetura principal do repositório.

Este patch não altera a regra de cálculo do modelo, não move `data/matches.csv`, não muda a fonte de verdade e não reorganiza `data/verdade/` ou `data/gerado/`. Essas mudanças ficam para uma etapa posterior.

## Itens removidos

### Frontend legado

```bash
git rm src/analysis.js
git rm src/app.js
git rm src/results.js
git rm src/model-data.js
git rm src/modelo-dados.js
```

Esses arquivos não são carregados pelas páginas HTML atuais. O frontend ativo usa `src/data.js`, `src/team-colors.js`, `src/team-assets.js`, `src/rede-neural-data.js`, `src/modelo-diario-data.js`, `src/prediction-source.js`, `src/dashboard.js`, `src/pixi-neural-view.js` e `src/neural-data-viz.js`.

### Scripts Python legados

```bash
git rm scripts/recalcular_mata_mata.py
git rm scripts/recalcular_modelo_contextual.py
```

A orquestração ativa continua sendo `scripts/atualizar_modelo.py`, que chama `scripts/treinar_rede_neural_copa.py`, `scripts/modelo_neural_diario.py` e `scripts/recalcular_chaveamento_completo.py`.

### Dados legados ou duplicados fora do fluxo atual

```bash
git rm data/previsoes_modelo.csv
git rm data/database/simulated_matches.csv
git rm data/database/simulated_referee_assignments.csv
git rm data/atualizacoes_entrada_26-06.csv
git rm data/atualizacoes_entrada_26-06_resultados_desempenho.csv
git rm -r data/neural
git rm -r data/modelo
```

O modelo diário atual declara explicitamente que não usa previsões/simulações antigas como entrada. As saídas ativas seguem em `data/modelo_diario/` e `data/rede_neural/`.

### Artefatos locais Python

```bash
git rm -r neural_copa/__pycache__ scripts/__pycache__
```

Os diretórios `__pycache__` e arquivos `.pyc` são artefatos locais e já estão cobertos pelo `.gitignore`.

## Itens preservados

A documentação histórica foi preservada:

- `README*.md`
- `VALIDACAO*.md`
- `VALIDACAO*.json`
- `docs/`
- `scripts/README_integracao_pesquisa_2026_06_30.md`

## Ajustes adicionais de segurança

- `scripts/testes/test_integridade_dados.py` agora falha se arquivos legados removidos no Patch 2 reaparecerem.
- `scripts/modelo_neural_diario.py` foi atualizado para não gerar novas referências ativas aos arquivos legados removidos.
- `data/analise/matriz_influencia.csv` foi atualizado para apontar para as fontes ativas do modelo diário, em vez de arquivos legados removidos.

## Validação executada

```bash
python scripts/atualizar_modelo.py
python scripts/validar_recalculo_probabilidades.py
python scripts/testes/test_integridade_dados.py
```

Resultado:

- 104 jogos totais
- 76 resultados reais preservados
- 28 jogos projetados
- 0 jogos com `precisa_recalculo`
- CSV, JSON e JS sincronizados
- Nenhum caminho legado reapareceu
- Nenhum `__pycache__` ou `.pyc` versionado
