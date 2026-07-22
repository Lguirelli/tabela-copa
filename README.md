# Plataforma preditiva esportiva multicampeonato

Este repositório preserva o visualizador final da Copa do Mundo 2026 e adiciona uma **engine replicável de engenharia de dados, análise estatística, feedback preditivo, simulação e recalibração de modelos**.

A arquitetura é composta somente por código, scripts, módulos e GitHub Actions versionados. Não existe agente autônomo, sistema conversacional ou processo externo oculto.

## Status atual

- Copa do Mundo 2026: **104 partidas finalizadas** e preservadas como dados observados.
- Validação estrutural: **VALID**, sem placares impossíveis, IDs duplicados ou conflitos entre calendário e resultados.
- Dados completos de escalação, minutos, participação e disponibilidade ainda não estão disponíveis para todas as partidas; esses campos permanecem `NA` e estão registrados na fila de pendências.
- O modelo recalibrado mais recente foi mantido como candidato rejeitado porque não superou o baseline no holdout cronológico. A simulação continua usando os xG configurados, evitando promoção automática de um modelo pior.

## Arquitetura

```text
config/
  competitions.yaml              configuração por campeonato e temporada
  data_contracts.yaml            contratos e aliases de dados

sports_engine/
  config.py                      seleção do campeonato
  io.py                          leitura, escrita atômica, NA e hashes
  lineage.py                     manifesto de entradas
  sources.py                     adaptadores de coleta e merge seguro
  analytics.py                   preparação analítica
  modeling.py                    recalibração ridge
  pipeline.py                    execução ordenada dos loops
  cli.py                         comandos locais e de CI
  loops/
    completeness.py              Loop 01
    enrichment.py                Loop 02
    validation.py                Loop 03
    patterns.py                  Loop 04
    feedback.py                  Loop 05
    features.py                  Loop 06
    simulation.py                Loop 07
    recalibration.py             Loop 08

data/
  queues/missing_data.json       fila consolidada de dados ausentes
  platform/                      schemas canônicos ainda não preenchidos
  raw/                           respostas brutas coletadas, quando houver
  staging/                       dados coletados antes da validação/merge

logs/enrichment_log.json         histórico de tentativas de enriquecimento
models/competitions/<id>/        artefatos analíticos isolados por campeonato
models/patterns.json             alias do último campeonato processado
models/error_learning.json       alias do último feedback processado
models/features_registry.json    alias do último registro de features
models/model_versions/<id>/      versões candidatas e promovidas por competição
models/simulations/              aliases de compatibilidade da última simulação
reports/competitions/<id>/       relatórios isolados por campeonato
reports/                         aliases e auditoria global
```

A descrição completa está em [`docs/PLATFORM_ARCHITECTURE.md`](docs/PLATFORM_ARCHITECTURE.md).

## Os oito loops analíticos

### 01 — Data completeness check

Verifica cobertura por partida para resultados, datas, competição, eventos, estatísticas, escalações e dados individuais. Gera:

```text
data/queues/missing_data.json
reports/data_completeness_report.json
```

A fila agrupa entidades afetadas, prioridade, campo ausente e IDs de partidas. Ela não cria valores substitutos.

### 02 — Data enrichment

Lê a fila, ordena fontes por prioridade e executa somente adaptadores configurados. A implementação atual suporta:

- datasets locais já coletados;
- scoreboard público ESPN para resultados ausentes;
- summary público ESPN para eventos, estatísticas, escalações e desempenho individual quando o endpoint fornecer esses campos;
- armazenamento bruto com SHA-256;
- staging antes do merge;
- inserção apenas de registros ausentes.

Dados observados existentes não são sobrescritos. Em execução local, a rede fica desativada por padrão; os workflows definem `SPORTS_ENGINE_NETWORK=1` e limitam a coleta a 12 partidas por execução para reduzir carga e respeitar a fonte. O script `scripts/cleanup_external_mappings.py` documenta a migração dos registros ESPN legados: somente mapeamentos determinísticos foram aplicados, e 18 registros antigos sem vínculo validável foram preservados em `data/conflicts/` como `CONFLICTING_DATA`. Falhas e fontes insuficientes ficam registradas em:

```text
logs/enrichment_log.json
reports/enrichment_report.json
```

### 03 — Data validation

Valida duplicidades, IDs, placares, fontes, probabilidades e conflitos entre datasets. Os status possíveis são:

```text
VALID
INVALID
CONFLICTING_DATA
```

Campos legados explicitamente marcados como simulados são reportados como aviso e excluídos da descoberta automática de features.

### 04 — Pattern discovery

Monta uma visão time-partida e mede associações entre resultado e fatores como:

- primeiro gol;
- posse;
- finalizações;
- finalizações no alvo;
- xG, quando disponível;
- cartões;
- escanteios;
- passes;
- desarmes e interceptações.

O arquivo `models/patterns.json` registra amostra, impacto, confiança, método e ressalva de que associação não implica causalidade.

### 05 — Prediction feedback

Compara previsão anterior e resultado real, calculando:

- acurácia do desfecho;
- acerto exato do placar;
- erro absoluto de gols;
- Brier score multiclasse;
- maior sinal padronizado por partida como diagnóstico, sem atribuição causal.

Saída:

```text
models/error_learning.json
```

### 06 — Feature discovery

Avalia variáveis de viagem, descanso, idade, experiência, estilo, arbitragem, calendário, desgaste, qualidade de liga, qualidade dos jogadores e forma recente.

Uma feature só é aceita quando:

1. possui amostra mínima configurada;
2. ultrapassa o limiar de correlação absoluta;
3. mantém a mesma direção nas duas metades cronológicas da amostra;
4. não é sintética/simulada.

Saída:

```text
models/features_registry.json
```

### 07 — Simulation update

Executa Monte Carlo com seed reprodutível e produz:

- vitória, empate e derrota;
- média de gols;
- top 10 placares;
- probabilidade de prorrogação;
- probabilidade de o empate persistir após uma prorrogação simulada de 30 minutos e exigir pênaltis;
- probabilidade do vencedor dos pênaltis somente quando existe evidência/modelo configurado — caso contrário, `NA`.

Saídas:

```text
models/simulations/latest.csv
models/simulations/latest.json
```

### 08 — Model recalibration

Treina regressões ridge para diferença de gols e total de gols com divisão cronológica 80/20. Cada execução gera uma versão auditável e isolada por competição em:

```text
models/model_versions/<competition_id>/<content_hash>.json
```

A versão só é copiada para `models/model_versions/<competition_id>/latest.json` quando reduz o MAE médio no holdout. Candidatos piores são preservados, mas não promovidos.

## Instalação

Requer Python 3.11 ou superior.

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

A rede neural legada da Copa usa PyTorch e permanece opcional:

```bash
python -m pip install -r requirements-legacy-ml.txt
```

## Execução

Pipeline completo de uma competição:

```bash
python -m sports_engine.cli run-all --competition world_cup_2026
```

Todos os campeonatos executáveis configurados, ignorando templates:

```bash
python -m sports_engine.cli run-registry
```

Loops individuais:

```bash
python -m sports_engine.cli completeness --competition world_cup_2026
python -m sports_engine.cli enrich --competition world_cup_2026
python -m sports_engine.cli validate --competition world_cup_2026
python -m sports_engine.cli patterns --competition world_cup_2026
python -m sports_engine.cli feedback --competition world_cup_2026
python -m sports_engine.cli features --competition world_cup_2026
python -m sports_engine.cli recalibrate --competition world_cup_2026
python -m sports_engine.cli simulate --competition world_cup_2026
```

Também é possível usar:

```bash
make all COMPETITION=world_cup_2026
make all-competitions
make test
```

## GitHub Actions

### `daily_update.yml`

Executa diariamente todos os campeonatos não marcados como `template`, ou somente o ID escolhido manualmente:

1. verificação de completude;
2. enriquecimento seguro;
3. validação;
4. padrões e feedback;
5. descoberta de features;
6. recalibração;
7. simulações;
8. testes e commit dos artefatos gerados.

### `post_match_update.yml`

É acionado quando calendários, resultados, previsões, estatísticas ou entradas manuais mudam. Em eventos `push`, processa o registro completo para não associar um caminho novo ao campeonato errado; em execução manual, aceita um ID específico.

### `model_training.yml`

Executa após o workflow pós-jogo, por disparo manual ou quando a configuração de campeonatos muda. Processa todos os campeonatos configurados por padrão e verifica a amostra mínima antes de recalibrar.

### `static.yml`

Mantém a publicação do visualizador estático existente.

## Como adicionar outro campeonato

Use o template em `config/competitions.yaml` e crie os datasets da temporada. O código não precisa ser alterado.

Exemplo:

```yaml
competitions:
  brasileirao_2027:
    name: Brasileirão
    season: 2027
    country: Brasil
    format: league
    datasets:
      matches: data/competitions/brasileirao/2027/matches.csv
      results: data/competitions/brasileirao/2027/results.csv
      predictions: data/competitions/brasileirao/2027/predictions.csv
      team_match_stats: data/competitions/brasileirao/2027/team_match_stats.csv
      events: data/competitions/brasileirao/2027/events.csv
      lineups: data/competitions/brasileirao/2027/lineups.csv
      player_match_stats: data/competitions/brasileirao/2027/player_match_stats.csv
      player_availability: data/competitions/brasileirao/2027/player_availability.csv
```

Depois:

```bash
python -m sports_engine.cli run-all --competition brasileirao_2027
# ou processe todos os campeonatos configurados
python -m sports_engine.cli run-registry
```

Artefatos persistentes ficam separados em `models/competitions/brasileirao_2027/`, `reports/competitions/brasileirao_2027/`, `logs/competitions/brasileirao_2027/` e `data/competitions/brasileirao_2027/queues/`. Os arquivos de nível superior continuam como aliases de compatibilidade do último campeonato processado.
Consulte [`docs/ADDING_A_COMPETITION.md`](docs/ADDING_A_COMPETITION.md).

## Testes e validação

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python scripts/validate_repository.py
python scripts/testes/test_integridade_dados.py
```

Os testes verificam configuração, YAML dos workflows, geração da fila, merge incremental idempotente, integridade dos datasets, aliases controlados, exclusão de campos simulados, execução dos loops, sincronização do visualizador legado e integridade das seis páginas analíticas do modelo. O validador estrutural grava `reports/repository_integrity_report.json`.

## Arquivos de auditoria e status

```text
reports/repository_audit.json
reports/validation_report.json
reports/final_system_status.json
```

`repository_audit.json` descreve o estado do repositório antes da transformação. `final_system_status.json` registra o resultado dos loops, limitações conhecidas e situação dos testes.

## Compatibilidade com o projeto Copa 2026

As páginas HTML, `src/`, `neural_copa/`, dados finais e scripts de atualização existentes foram preservados. A nova plataforma funciona como uma camada adicional e não altera os 104 resultados reais nem promove automaticamente modelos que não superem o baseline.

---

## Cérebro preditivo temporal — Copa 2026

O repositório também contém uma reconstrução walk-forward completa da Copa do Mundo FIFA 2026. Essa camada prevê cada partida antes do início, libera resultados somente após o encerramento estimado, aprende com o erro e salva uma versão diária do modelo.

### Execução

```bash
python -m worldcup_brain.cli prepare
python -m worldcup_brain.cli replay
python -m worldcup_brain.cli validate
```

Para reconstruir apenas até uma data histórica:

```bash
python -m worldcup_brain.cli replay --as-of "2026-07-05T23:59:59-04:00"
```

A coleta complementar usa:

```bash
python -m worldcup_brain.cli collect --allow-network
```

Registros coletados posteriormente não podem resolver uma lacuna pré-jogo antiga sem `published_at` ou `available_at` compatível. Consulte [`docs/TEMPORAL_WORLD_CUP_BRAIN.md`](docs/TEMPORAL_WORLD_CUP_BRAIN.md) para arquitetura, artefatos e limitações.

## Integração do pacote completo de dados — 20/07/2026

O pacote auditado `wc2026_pacote_completo_final` foi integrado sem substituir cegamente os IDs ou resultados canônicos do repositório.

Cobertura adicionada:

- 4.248 eventos estruturados em 104 partidas;
- 11.815 linhas de narração;
- 208 registros de estatísticas por equipe, exatamente dois por partida;
- 5.323 registros individuais de jogadores;
- 5.323 registros de escalações observadas;
- árbitro principal das 104 partidas;
- 40 cobranças individuais em quatro disputas de pênaltis;
- respostas brutas ESPN/FIFA, manifesto SHA-256 e dicionário de dados.

A integração usa a dupla de seleções como chave canônica. Isso evita conflitos causados pelos IDs 89 e 90, que aparecem invertidos no pacote de origem. As cinco diferenças de data por conversão de fuso permanecem documentadas em `data/mappings/incoming_game_id_mapping_20260720.csv`.

Os dados individuais são fatos pós-jogo retroativamente coletados. O campo `source_collected_at` não é alterado, portanto escalações e arbitragem não são inseridas em previsões históricas anteriores à coleta. Minutos, xG, xA e rating permanecem `NA`.

Para reproduzir a integração a partir do pacote extraído:

```bash
python scripts/integrate_wc2026_complete_package.py /caminho/wc2026_pacote_completo_final
python -m sports_engine.cli run-all --competition world_cup_2026
python -m worldcup_brain.cli replay
python -m worldcup_brain.cli validate
```

Consulte [`docs/WC2026_COMPLETE_DATA_INTEGRATION.md`](docs/WC2026_COMPLETE_DATA_INTEGRATION.md) e `reports/wc2026_complete_data_integration.json`.

## Visualização expandida do modelo

A antiga página única de rede neural foi reorganizada em seis páginas estáticas, todas compatíveis com GitHub Pages:

```text
rede-neural.html             visão geral, métricas finais e segurança temporal
modelo-evolucao.html         evolução diária de acurácia, perdas e calibração
modelo-previsoes.html        explorador das 104 previsões pré-jogo
modelo-aprendizado.html      acertos, erros, fatores observados e ajustes
modelo-simulacoes.html       evolução das hipóteses de classificação e título
modelo-versoes.html          versões temporais, checkpoints e parâmetros
```

O frontend não consulta APIs durante a navegação. O script abaixo compacta os artefatos existentes em um bundle JavaScript rastreável:

```bash
python scripts/export_model_dashboard.py
# ou
make export-dashboard
```

Saída:

```text
src/model-analytics-data.js
```

O exportador não cria novas métricas nem estima valores ausentes. Ele utiliza somente previsões, relatórios, simulações, versões e análises já produzidos pelo pipeline. Os workflows temporais e multicampeonato executam o exportador após cada atualização para manter o GitHub Pages sincronizado.

## Diagnóstico em loop das runs

Para reproduzir as etapas dos workflows em cópias isoladas do repositório, repetir as execuções e classificar falhas recorrentes:

```bash
python scripts/diagnose_github_actions.py --iterations 2
```

Os relatórios completos são gravados em:

```text
reports/run_diagnostics/run_diagnostics.md
reports/run_diagnostics/run_diagnostics.json
reports/run_diagnostics/logs/
```

O workflow `00_run_diagnostics.yml` também é executado automaticamente quando uma das principais GitHub Actions termina com falha. Ele não faz commit: publica os relatórios e logs como artefato da run.
