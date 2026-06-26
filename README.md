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
