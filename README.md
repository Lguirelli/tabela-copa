# Copa 2026 — Visualizador de resultados com correção incremental

Repositório estático para visualizar jogos da Copa 2026 com **previsão ao lado do resultado real**.

Quando o resultado real existe, o site mostra:

- placar previsto;
- placar real;
- status **Finalizado**;
- erro de previsão;
- proximidade do modelo.

Quando o resultado real ainda não existe, o site mostra:

- placar previsto atualizado;
- status **Simulação**.

## Como abrir

Abra `index.html` no navegador.

Também pode rodar localmente:

```bash
python -m http.server 8000
```

Depois acesse `http://localhost:8000`.

## Como registrar novos resultados

1. Edite o arquivo:

```text
data/entrada/novos_resultados.csv
```

2. Adicione as novas linhas no mesmo formato:

```csv
data;dia_semana;fase;time_1;gols_time_1;gols_time_2;time_2;placar;status;fonte
2026-06-26;Sexta-feira;Fase de grupos;Noruega;0;0;França;Noruega 0 x 0 França;Finalizado;
```

3. Rode:

```bash
python scripts/atualizar_modelo.py
```

O script compara a previsão anterior com o resultado real, registra o erro e atualiza a próxima simulação.

## Arquivos principais

```text
index.html
src/app.js
src/data.js
src/model-data.js
data/matches.csv
data/previsoes_modelo.csv
data/resultados_reais.csv
data/neural/correcoes_modelo.csv
data/neural/estado_times.csv
data/neural/model_state.json
data/desempenho/jogos_finalizados_copa_2026_ate_25-06.csv
data/desempenho/jogadores_citados_desempenho_copa_2026.csv
data/desempenho/resumo_desempenho_por_jogo_copa_2026.csv
scripts/atualizar_modelo.py
```

## Estado inicial

- Resultados reais carregados: **60**
- Correções registradas: **60**
- Proximidade média inicial: **24.7%**
- Última data real na base: **2026-06-25**



## Atualização aplicada

- `data/team_colors.csv` e `src/team-colors.js` guardam as cores por seleção.
- O front usa essas cores apenas como identidade visual dos cards e chips, sem exibir a base CSV.
- O mata-mata foi recalculado com a classificação projetada dos grupos, usando resultado real quando existe e simulação quando ainda não existe resultado.
- Arquivos auxiliares do recálculo:
  - `data/neural/classificacao_projetada_grupos.csv`
  - `data/neural/melhores_terceiros_projetados.csv`
  - `data/neural/terceiros_colocados_mata_mata.csv`
