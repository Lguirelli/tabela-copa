# Atualização técnica do repositório — 6 de agosto de 2026

## Resultado

O repositório foi consolidado em um único pipeline de atualização, validado em modo temporal e preparado para consumir fontes complementares sem introduzir informação futura nas previsões.

## Melhorias aplicadas

- Redução de oito workflows sobrepostos para três fluxos com responsabilidades claras: integração contínua, publicação estática e atualização do modelo.
- Remoção de scripts de produção duplicados; as versões históricas continuam preservadas em `legacy/` apenas como referência.
- Publicação estática restrita aos arquivos necessários do site, sem expor dados internos, relatórios, modelos ou código Python.
- Instalação de dependências unificada pelo `pyproject.toml`.
- Verificação de pré-voo realmente somente leitura quando executada com `--check`.
- Catálogo e contratos de dados ampliados com política explícita de disponibilidade temporal.
- Integrações opcionais para ranking FIFA, partidas do football-data.org, dados abertos da Hudl StatsBomb e clima pré-jogo do Open-Meteo Previous Runs.
- Ranking, forma recente e clima só podem ser usados quando `published_at` ou `available_at` é anterior ao instante da previsão.
- Recalibração de pesos mantida em modo sombra: candidatos são avaliados, mas só podem substituir o modelo vigente depois de superar os critérios de promoção. O candidato desta revisão foi rejeitado por piorar o replay, preservando o modelo mais estável.
- Interface dark redesenhada com sistema visual inspirado em produtos de dados/IA: superfícies em camadas, contraste reforçado, acentos ciano/verde, estados de foco acessíveis e responsividade preservada.

## Validação executada

- Estado operacional: `READY`.
- Testes automatizados: 30 aprovados.
- Validação estrutural: 74 arquivos Python, 7 YAML, 708 JSON e 82 CSV analisados sem erro.
- Replay temporal: 104 previsões, 104 análises pós-jogo e 5.571 registros de conhecimento, sem vazamento de dados futuros.
- Comparação na fase de grupos: ganho de 5,56 pontos percentuais em acerto de resultado e de placar exato em relação ao modelo congelado, com redução de log loss e Brier score.
- Pipeline canônico: todas as etapas concluídas com sucesso.

## Limitação conhecida

Dezoito linhas de estatísticas externas antigas continuam em quarentena por conflito de dados. Elas ficam preservadas para auditoria e são excluídas dos cálculos, portanto não bloqueiam a execução.

## Configuração opcional

O coletor do football-data.org usa a variável de ambiente `FOOTBALL_DATA_API_TOKEN`. Sem esse token e sem acesso de rede, o pipeline continua funcionando com os dados canônicos locais. O Open-Meteo não exige chave, mas também respeita a opção de rede do pipeline.
