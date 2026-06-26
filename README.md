# Copa 2026 | Visualizador de resultados

Repositório estático para visualizar a tabela da Copa 2026 em duas áreas:

- Fase de grupos
- Mata-mata

## Como rodar

Abra `index.html` no navegador.

Também é possível rodar com servidor local:

```bash
python -m http.server 8000
```

Depois acesse:

```txt
http://localhost:8000
```

## Atualização de resultados

O arquivo principal para atualizar placares é:

```txt
data/resultados.txt
```

Formato:

```txt
jogo;status;placar;equipe1;equipe2;vencedor
1;Finalizado;2-1;México;África do Sul;México
73;Finalizado;0-2;África do Sul;Catar;Catar
```

## Base de dados

A base CSV fica dentro de `data/` e `data/database/`.
Esses arquivos permanecem no repositório, mas não aparecem como abas ou seções no front.
