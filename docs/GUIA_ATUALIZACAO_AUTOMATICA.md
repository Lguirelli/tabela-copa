# Atualização automática do modelo

Este repositório agora possui um workflow do GitHub Actions em:

```txt
.github/workflows/atualizar-modelo.yml
```

## Quando ele roda

O recálculo é executado automaticamente quando houver `push` em arquivos de entrada ou de modelo, principalmente:

```txt
data/entrada/**
data/resultados_reais.csv
data/desempenho_*.csv
data/matches.csv
data/database/**
scripts/**
neural_copa/**
```

Também pode ser executado manualmente pela aba **Actions** do GitHub, usando **Run workflow**.

Há ainda um agendamento diário às 09:00 de Brasília. Esse agendamento apenas recalcula com os dados que já estiverem versionados no repositório. Ele não busca resultados na internet sozinho.

## Fluxo recomendado para novos resultados

1. Edite `data/entrada/novos_resultados.csv`.
2. Adicione uma linha por jogo finalizado.
3. Faça commit e push.
4. O GitHub Actions roda `python scripts/atualizar_modelo.py`.
5. O workflow valida com `python scripts/validar_recalculo_probabilidades.py`.
6. Se houver alterações, o próprio workflow commita os CSVs e JS recalculados.

## Formato de `novos_resultados.csv`

Use separador `;`:

```csv
data;dia_semana;fase;time_1;gols_time_1;gols_time_2;time_2;placar;status;vencedor_real;placar_penaltis_real;vencedor_penaltis_real;fonte
2026-07-04;sábado;Oitavas de final;Canadá;1;1;Marrocos;1-1;Finalizado;Marrocos;4-5;Marrocos;FIFA
```

Para jogo sem pênaltis, deixe `placar_penaltis_real` e `vencedor_penaltis_real` vazios.

## Importante

- Resultado real não é sobrescrito pelo modelo.
- O script limpa `data/entrada/novos_resultados.csv` depois de processar as linhas novas.
- Probabilidades são recalculadas para todos os jogos.
- No mata-mata, o frontend passa a priorizar probabilidade de classificação, não apenas vitória em 90 minutos.
- O site estático não roda Python no navegador; ele lê os CSVs/JS já gerados pelo workflow.
