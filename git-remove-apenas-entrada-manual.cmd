@echo off
REM Execute este arquivo na raiz do repositorio.

git rm -r --ignore-unmatch data/desempenho
git rm --ignore-unmatch src/desempenho-data.js
git rm --ignore-unmatch scripts/atualizar_desempenho_copa.py
git rm --ignore-unmatch .github/workflows/atualizar-desempenho-copa.yml

echo.
echo Remocao concluida. Agora rode:
echo git status
echo git add .gitignore data/entrada/README_ENTRADA_MANUAL.md scripts/atualizar_modelo.py scripts/modelo_neural_diario.py
echo git commit -m "Centraliza desempenho em entrada manual"
