# Patch 1 — Segurança, validação e workflow restrito

Aplicado em 2026-06-30.

## Objetivo

Este patch adiciona barreiras de integridade sem alterar a arquitetura principal do repositório. Ele não move pastas, não remove arquivos duplicados e não consolida os pipelines. O foco é impedir commits automáticos com dados quebrados.

## Alterações

- Adicionado `scripts/testes/test_integridade_dados.py`.
- O GitHub Actions agora executa validação de integridade antes e depois do recálculo.
- O `git add` automático foi restringido a artefatos derivados do pipeline.
- O commit automático recebeu `[skip ci]` como camada extra contra reexecução indesejada.
- Corrigida a geração de `placar_real` em `scripts/modelo_neural_diario.py` para evitar sufixos inválidos como `(pên. nan)`.

## O que a validação cobre

- Total de 104 jogos em `matches.csv`, `matches.json` e `src/data.js`.
- IDs de jogos únicos.
- Sincronização entre `data/matches.csv` e `data/database/matches.csv` enquanto ambos existirem.
- Sincronização entre `data/resultados.csv` e `data/resultados_reais.csv` enquanto ambos existirem.
- Probabilidades entre 0 e 1.
- Soma das probabilidades principais próxima de 1.
- Ausência de jogos marcados como `precisa_recalculo`.
- Ausência de `NaN`, `None` e `(pên. nan)` nos artefatos gerados principais.
- Quantidade de previsões nos JS gerados do frontend.

## Como rodar localmente

```bash
python scripts/testes/test_integridade_dados.py
python scripts/atualizar_modelo.py
python scripts/validar_recalculo_probabilidades.py
python scripts/testes/test_integridade_dados.py
```

## Observação

A limpeza de arquivos órfãos, unificação de fonte da verdade e reorganização para `data/verdade` e `data/gerado` ficam para os próximos patches.
