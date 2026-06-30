# Integração da pesquisa Copa 2026 - corte 2026-06-30

Este patch adiciona uma camada complementar de dados auditáveis ao repositório, sem substituir a base principal de placares.

## Correções aplicadas

- `data/resultados.csv` e `data/resultados_reais.csv`: adicionada a linha oficial do jogo 75, Países Baixos 1-1 Marrocos, Marrocos 3-2 nos pênaltis.
- `data/matches.csv`, `data/database/matches.csv`, `data/matches.json`, `src/data.js` e `src/results.js`: jogo 75 atualizado de `Modelo diário` para `Finalizado`.
- `data/modelo_diario/projecao_chaveamento_completa.csv` e `data/rede_neural/previsoes_rede_neural.csv`: jogo 75 marcado como real, preservando previsões/model outputs já existentes.
- `data/modelo_diario/validacao_dia_a_dia.csv`: removido o sufixo inválido `(pên. nan)` de placares reais sem disputa por pênaltis.

## Novos arquivos de dados

- `data/desempenho_jogo_a_jogo.csv`: 32 linhas, cobrindo 16 jogos em visão por seleção.
- `data/desempenho_fase_grupos_selecoes.csv`: 48 seleções com consolidação de fase de grupos e tags analíticas.
- `data/desempenho_jogadores_destaques.csv`: 20 jogadores/ações de destaque.
- `data/desempenho_penaltis.csv`: 4 linhas de decisões por pênaltis.
- `data/fontes_dados.csv`: fontes utilizadas e nível de confiança.
- `data/pendencias_dados.csv`: lacunas ainda abertas para coleta posterior.
- `data/auditoria_dados.csv`: trilha de auditoria da integração.

## Regra metodológica

Campos avançados como xG, finalizações, grandes chances, ratings e detalhe integral de cobranças foram mantidos como `NA` quando não havia fonte homogênea e verificável. O `jogo_id` da pesquisa foi normalizado ao ID real do repositório: `R32_75` = Países Baixos x Marrocos e `R32_76` = Brasil x Japão.
