# Correção definitiva das falhas das GitHub Actions

## Falhas reproduzidas no ZIP recebido

### 1. CSVs legados duplicados no diretório canônico

Os arquivos abaixo estavam simultaneamente em `data/` e em `data/archive/legacy_inputs/`:

- `data/atualizacoes_entrada_26-06.csv`
- `data/atualizacoes_entrada_26-06_resultados_desempenho.csv`

As cópias eram byte a byte idênticas às versões arquivadas. A validação `scripts/testes/test_integridade_dados.py` reprova corretamente a presença desses caminhos legados, causando falha nas runs de atualização diária, atualização pós-jogo e treinamento.

Correção:

- as cópias de `data/` foram removidas;
- as versões arquivadas foram preservadas;
- `scripts/ci_preflight.py` agora limpa automaticamente esses caminhos antes de cada workflow que escreve no repositório;
- conteúdo divergente nunca é descartado: é preservado em `data/archive/legacy_inputs/conflicts/` com hash no nome.

### 2. O próprio workflow criava `__pycache__` e depois reprovava a integridade

Os comandos do pipeline eram executados sem `PYTHONDONTWRITEBYTECODE=1`. Isso criava diretórios como:

- `sports_engine/__pycache__/`
- `sports_engine/loops/__pycache__/`

Na etapa seguinte, `test_integridade_dados.py` encontrava esses artefatos e encerrava com código 1. Assim, o código e os dados podiam estar corretos, mas a run falhava por arquivos temporários criados pelo próprio job.

Correção:

- todos os workflows Python agora definem `PYTHONDONTWRITEBYTECODE=1` no nível do job;
- o alvo `make test` depende de `clean-cache` e remove `__pycache__`, `.pyc` e `.pytest_cache` antes da suíte;
- as três validações foram centralizadas em `make test`.

### 3. Coleta externa podia consumir quase todo o timeout da Action

A configuração anterior permitia até 45 segundos por requisição, três tentativas e até 12 partidas por execução. Somente os summaries poderiam consumir aproximadamente 27 minutos em indisponibilidade total, sem contar scoreboard, pipeline, simulação e testes. Os jobs têm timeout de 30 ou 45 minutos.

Correção:

- timeout por requisição reduzido para 8 segundos;
- retries reduzidos para uma tentativa por run;
- valores podem ser sobrescritos por `SPORTS_ENGINE_NETWORK_TIMEOUT` e `SPORTS_ENGINE_NETWORK_RETRIES`;
- falha de provedor continua registrada como dado indisponível/fallback, sem interromper o pipeline completo.

### 4. A coleta repetia sempre as primeiras partidas incompletas

A seleção de partidas usava sempre os primeiros IDs da fila agregada, mesmo quando esses IDs já possuíam cobertura. Isso fazia a automação consultar repetidamente as mesmas partidas e não avançar pela base.

Correção:

- a fila agora calcula `entity_ids - covered_ids` antes de selecionar as próximas partidas;
- cada run avança para IDs ainda sem cobertura;
- merges permanecem incrementais e idempotentes.

### 5. Workflows temporais não versionavam todos os dados coletados

Os workflows `02` e `03` coletavam dados em `data/raw`, `data/normalized`, `data/platform` e filas, mas o `git add` incluía apenas alguns subdiretórios temporais. A coleta podia ser descartada ao final da run.

Correção:

- workflows temporais agora usam `git add -A data ...`;
- exclusões feitas pelo preflight e novos dados de rede são incluídos no mesmo commit.

## Validação após as correções

- `make test`: **23 testes aprovados**;
- `scripts/validate_repository.py`: **VALID**, zero problemas;
- `scripts/testes/test_integridade_dados.py`: **OK**;
- pipeline esportivo com rede habilitada: concluiu localmente em aproximadamente **32 segundos**;
- replay temporal completo com 4.000 simulações: concluído e validado;
- diagnóstico isolado dos workflows principais: **15/15 etapas aprovadas**;
- diagnóstico temporal atual: **6/6 etapas aprovadas**;
- workflow pré-Copa: aprovado;
- arquivos obrigatórios do GitHub Pages: presentes;
- todos os YAMLs em `.github/workflows/`: válidos;
- simulação de commit: as duas exclusões legadas foram versionadas e o checkout terminou sem alterações pendentes.

## Observação externa ao código

Se uma run ainda falhar especificamente em `git push` com mensagens como `Resource not accessible by integration`, `protected branch` ou `permission denied`, a causa será configuração do repositório no GitHub, não o pipeline Python. Nesse caso, o repositório precisa permitir **Read and write permissions** para GitHub Actions ou aceitar commits do bot na regra de proteção da branch.
