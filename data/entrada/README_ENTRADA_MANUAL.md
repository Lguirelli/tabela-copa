# Entrada manual de dados da Copa 2026

Esta pasta é a única fonte versionada para novos dados da Copa.

## Arquivos que devem ser editados manualmente

### `novos_resultados.csv`
Use para inserir jogos finalizados.

Colunas esperadas:

```csv
data;dia_semana;fase;time_1;gols_time_1;gols_time_2;time_2;placar;status;fonte
```

Exemplo:

```csv
2026-06-29;segunda-feira;16 avos de final;Brasil;2;1;Japão;2-1;Finalizado;https://fonte-confiavel
```

Após rodar `python scripts/atualizar_modelo.py`, as entradas processadas são incorporadas em `data/resultados_reais.csv` e o arquivo volta a ficar apenas com o cabeçalho.

### `desempenho_manual.csv`
Use para inserir estatísticas e observações auditáveis de desempenho por seleção/jogo.

Regras:

- Não inventar valores.
- Quando uma estatística não estiver disponível em fonte confiável, deixar vazio ou `NA`.
- Cada linha deve trazer uma fonte.
- Pode haver uma linha por seleção no jogo, ou linhas extras para jogadores relevantes.
- O modelo diário lê diretamente este arquivo, sem depender de bases duplicadas em `data/desempenho/`.

## Arquivos removidos do versionamento

As bases consolidadas/geradas de desempenho foram removidas para evitar conflito no Git. Elas não devem ser editadas nem comitadas. A entrada manual fica centralizada aqui.
