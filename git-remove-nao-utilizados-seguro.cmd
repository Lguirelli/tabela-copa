@echo off
REM Remoção segura para o front atual. Execute na raiz do repositório.
git rm -- "src/app.js"
git rm -- "src/analysis.js"
git rm -- "src/model-data.js"
git rm -- "src/modelo-dados.js"
git rm -- "src/results.js"
git rm -- "data/analise/matriz_influencia.csv"
git rm -- "data/atualizacoes_entrada_26-06.csv"
git rm -- "data/atualizacoes_entrada_26-06_resultados_desempenho.csv"
git rm -- "docs/analise_deeplearningexamples.md"
git rm -- "docs/analise_dl_visualization_adaptacao.md"
git rm -- "docs/analise_pixijs_visualizacao.md"
git rm -- "VALIDACAO_CORRECAO_FRONTEND.md"
