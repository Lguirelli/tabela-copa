# Copa 2026 — Visualizador com modelo diário

Visualizador estático para acompanhar a Copa 2026 com resultados reais, chaveamento e previsões do modelo diário incremental.

## Páginas

- `grupos-resultados.html` — classificação geral dos grupos.
- `grupos-jogos.html` — lista de jogos da fase de grupos.
- `mata-mata-chave.html` — chaveamento do mata-mata.
- `mata-mata-jogos.html` — lista dos jogos eliminatórios.
- `rede-neural.html` — painel do modelo ativo, métricas, desempenho, erros e visualizações.

## Fonte ativa de placar no front

A prioridade do front agora é:

```txt
1. placar real, quando disponível
2. previsão do modelo diário incremental
3. rede neural pura como fallback/referência secundária
```

Arquivos principais consumidos pelo front:

```txt
data/matches.csv
src/data.js

data/modelo_diario/previsoes_dia_a_dia.csv
src/modelo-diario-data.js
src/prediction-source.js

data/rede_neural/previsoes_rede_neural.csv
src/rede-neural-data.js
```

O chaveamento usa `src/prediction-source.js` para unificar as fontes e evitar conflito entre placar real, previsão diária e previsão neural antiga.

## Modelo diário

O modelo diário usa desempenho dentro da Copa como variável, sem vazar informação futura. Ele atualiza por seleção:

```txt
rating_atual_0_100
momentum_resultado_anterior
memoria_desempenho
jogos_validados
gols_pro
gols_contra
saldo
pontos
```

As principais features expostas no front são:

```txt
feature_rating_diff
feature_momentum_diff
feature_performance_memory_diff
feature_attack_vs_defense
feature_defense_vs_attack
feature_player_quality_diff
feature_league_diff
feature_rest_diff
feature_knockout
```

## Atualização

1. Coloque novas linhas em:

```txt
data/entrada/novos_resultados.csv
```

2. Rode:

```bash
python scripts/atualizar_modelo.py
```

Esse script atualiza os resultados reais, reexecuta a rede neural de referência, recalcula o modelo diário e exporta os dados para o front.

## Recalcular apenas o modelo diário

```bash
python scripts/modelo_neural_diario.py
```

## Treinar manualmente a rede neural de referência

```bash
python scripts/treinar_rede_neural_copa.py
```

## Estrutura principal

```txt
scripts/                         automações de atualização e treino
data/modelo_diario/              previsões, estado dos times e métricas do modelo ativo
data/rede_neural/                dataset, métricas, checkpoint e previsões da rede de referência
src/modelo-diario-data.js        export JS do modelo diário
src/prediction-source.js         adaptador de prioridade: real > diário > rede
src/rede-neural-data.js          export JS da rede de referência
assets/teams/                    bandeiras e ícones das seleções
```


## Entrada manual de resultados e desempenho

Para evitar conflitos no Git, o repositório agora mantém apenas as entradas manuais versionadas em `data/entrada/`:

- `data/entrada/novos_resultados.csv` — inserir jogos finalizados.
- `data/entrada/desempenho_manual.csv` — inserir estatísticas confiáveis de time/jogador, sempre com fonte.

As bases consolidadas antigas em `data/desempenho/` foram removidas do versionamento. O modelo diário lê `desempenho_manual.csv` diretamente, então não há mais necessidade de comitar snapshots intermediários, relatórios por data ou exports duplicados.

Para atualizar após novos jogos, preencha os CSVs manuais e rode:

```bash
python scripts/atualizar_modelo.py
```

O GitHub Actions de atualização automática de desempenho também foi removido para impedir commits conflitantes.

## Chaveamento completo com entrada manual

O fluxo atual preserva resultados reais e recalcula apenas jogos sem resultado real.

Entradas manuais versionadas:

```txt
data/entrada/novos_resultados.csv
data/entrada/desempenho_manual.csv
```

Para atualizar a tabela completa depois de adicionar novos resultados ou desempenho:

```bash
python scripts/atualizar_modelo.py
```

Esse comando atualiza a rede neural de referência, recalcula o modelo diário e depois executa:

```bash
python scripts/recalcular_chaveamento_completo.py
```

Regras do chaveamento:

1. placar real nunca é sobrescrito;
2. jogos sem resultado real são simulados pelo modelo diário incremental;
3. vencedores reais/projetados alimentam as fases seguintes;
4. em mata-mata, empate é resolvido por pênaltis;
5. a tabela completa fica sempre preenchida, sem “Aguardando recálculo” quando o jogo ainda não tem resultado real.


## Integração da pesquisa Copa 2026 - 2026-06-30

Foi adicionada uma camada complementar em CSV para análise/modelagem, baseada na pesquisa aprofundada com corte em 2026-06-30. A base oficial de placares continua em `data/resultados_reais.csv`; a camada nova fica nos arquivos `data/desempenho_*.csv`, `data/fontes_dados.csv`, `data/pendencias_dados.csv` e `data/auditoria_dados.csv`.

Correção aplicada: jogo 75 atualizado como `Países Baixos 1-1 Marrocos`, com Marrocos avançando por 3-2 nos pênaltis. Campos avançados sem verificação homogênea permanecem como `NA`.
