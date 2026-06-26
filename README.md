# Copa 2026 — Visualizador de resultados

Repositório estático para visualizar a tabela da Copa do Mundo 2026 em duas partes:

1. Fase de grupos
2. Mata-mata

## Como atualizar os resultados

Edite somente este arquivo:

```txt
data/resultados.txt
```

Formato usado:

```txt
jogo;status;placar;equipe1;equipe2;vencedor
1;Finalizado;2-0;México;África do Sul;México
73;Agendado;;2º Grupo A;2º Grupo B;
```

Campos:

- `jogo`: número do jogo, de 1 a 104.
- `status`: Agendado, Ao vivo, Finalizado ou outro status que você quiser exibir.
- `placar`: use formatos como `2-0`, `2 x 0` ou `2:0`.
- `equipe1` e `equipe2`: use para substituir os placeholders do mata-mata quando as equipes forem definidas.
- `vencedor`: use nos jogos eliminatórios ou quando quiser destacar o vencedor.

## Como rodar

Abra `index.html` em um servidor local:

```bash
python -m http.server 8000
```

Depois acesse:

```txt
http://localhost:8000
```

## Estrutura

```txt
copa-2026-resultados-viewer-repo/
├── index.html
├── src/
│   ├── app.js
│   ├── data.js
│   └── styles.css
└── data/
    ├── matches.json
    ├── matches.csv
    └── resultados.txt
```
