# Copa 2026 — Visualização de tabelas sem resultados

Repositório estático para visualizar a tabela de jogos da Copa do Mundo FIFA 2026 em duas partes:

1. **Fase de grupos**: lista filtrável por grupo, equipe, estádio e cidade.
2. **Mata-mata**: chave visual e tabela completa usando apenas os slots oficiais de classificação.

## Importante

Este repositório **não usa placares, resultados, classificação atual ou equipes classificadas via resultados de Copa**.

No mata-mata, os confrontos aparecem como:

- `1º Grupo A`
- `2º Grupo B`
- `3º Grupo C/E/F/H/I`
- `Vencedor do jogo 73`
- `Perdedor do jogo 101`

Isso mantém a tabela neutra para uso antes ou durante o torneio, sem depender de resultados.

## Como rodar

### Opção 1 — abrir direto

Abra o arquivo `index.html` no navegador.

### Opção 2 — servidor local simples

No terminal, dentro da pasta do repositório:

```bash
python -m http.server 8000
```

Depois acesse:

```text
http://localhost:8000
```

## Estrutura

```text
.
├── index.html
├── src
│   ├── app.js
│   ├── data.js
│   └── styles.css
├── data
│   ├── matches.json
│   └── matches.csv
└── docs
    └── fontes.md
```

## Dados

- `data/matches.json`: base completa usada pela interface.
- `data/matches.csv`: versão tabular para conferência ou edição.
- `src/data.js`: mesma base em formato JavaScript para uso estático sem build.

## Fontes

As fontes estão documentadas em `docs/fontes.md`.
