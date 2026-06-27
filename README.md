# Copa 2026 — Visualizador responsivo de jogos

Repositório estático em HTML/CSS/JS para visualizar resultados, previsões e chaveamento da Copa 2026.

## Telas principais

- `grupos-resultados.html` — resultados gerais e tabelas dos grupos.
- `grupos-jogos.html` — tabela paginada dos jogos da fase de grupos.
- `mata-mata-chave.html` — chaveamento visual em tela única.
- `mata-mata-jogos.html` — lista paginada dos jogos do mata-mata.
- `analise.html` — menu lateral de análise do modelo, variáveis e melhorias.

O `index.html` redireciona para `grupos-resultados.html`.

## Responsividade

As páginas foram divididas para caber em uma visualização sem scroll de página. Quando há muitos dados, a visualização usa paginação interna, não rolagem vertical.

## Atualização de resultados

Adicione novas entradas em:

```txt
data/entrada/novos_resultados.csv
```

Depois rode:

```bash
python scripts/atualizar_modelo.py
```

O script atualiza:

- resultados reais;
- correções previsão x real;
- força contextual das seleções;
- chaveamento do mata-mata;
- arquivos JS usados pelo front.

## Variáveis consideradas pelo modelo contextual

O script `scripts/recalcular_modelo_contextual.py` considera:

- força base do elenco;
- competitividade do campeonato dos jogadores;
- desempenho dos jogadores;
- resultado anterior com peso por data;
- correção acumulada do modelo.

Saídas principais:

```txt
data/modelo/modelo_times.csv
data/modelo/matriz_variaveis.csv
src/modelo-dados.js
```

## Rodar localmente

Pode abrir os HTMLs diretamente no navegador. Para evitar bloqueios locais em alguns browsers, use:

```bash
python -m http.server 8000
```

Depois acesse:

```txt
http://localhost:8000/grupos-resultados.html
```

## Rede neural da Copa

Foi adicionada uma rede neural PyTorch inspirada na organização modular do repositório NVIDIA DeepLearningExamples, mas adaptada para a base da Copa 2026.

Arquivos principais:

```text
neural_copa/config.py
neural_copa/data_utils.py
neural_copa/modeling.py
neural_copa/train.py
neural_copa/inference.py
neural_copa/export_frontend.py
scripts/treinar_rede_neural_copa.py
scripts/aplicar_rede_neural_copa.py
data/rede_neural/
src/rede-neural-data.js
```

Para treinar e atualizar o front:

```bash
python scripts/treinar_rede_neural_copa.py
```

Para apenas reaplicar inferência a partir do checkpoint salvo:

```bash
python scripts/aplicar_rede_neural_copa.py
```

A rede `CopaMatchNet` usa embeddings de seleções e variáveis numéricas como força contextual, competitividade de ligas, desempenho de jogadores, momentum por data, técnico, arbitragem simulada e correções anteriores. Ela prevê saldo de gols e total de gols, depois converte isso em placar. Como ainda há poucos resultados reais, a saída final mistura rede neural e baseline contextual para reduzir overfit.
