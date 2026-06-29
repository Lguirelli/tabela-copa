# Git remove — limpeza para manter apenas entrada manual de desempenho

Execute na raiz do repositório depois de aplicar o patch.

```bash
git rm -r --ignore-unmatch data/desempenho
git rm --ignore-unmatch src/desempenho-data.js
git rm --ignore-unmatch scripts/atualizar_desempenho_copa.py
git rm --ignore-unmatch .github/workflows/atualizar-desempenho-copa.yml
```

Depois confira:

```bash
git status
git add .gitignore data/entrada/README_ENTRADA_MANUAL.md scripts/atualizar_modelo.py scripts/modelo_neural_diario.py
git commit -m "Centraliza desempenho em entrada manual"
```

A partir daqui, os únicos arquivos editáveis para novos dados são:

```txt
data/entrada/novos_resultados.csv
data/entrada/desempenho_manual.csv
```
