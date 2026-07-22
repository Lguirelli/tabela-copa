# Análise das falhas das GitHub Actions

## Falhas reproduzidas no repositório recebido

### 1. Validação temporal quebrava com CSV vazio

O workflow `01_pre_worldcup_training.yml` executava um replay até `2026-06-10T23:59:59-04:00`, antes da primeira previsão do campeonato. O replay gerava `predictions/pre_match/index.csv` e `learning/game_analysis/index.csv` somente com uma quebra de linha. Em seguida, `worldcup_brain.io.read_csv()` usava `csv.Sniffer` por meio de `pandas.read_csv(..., sep=None, engine="python")`, causando:

```text
_csv.Error: Could not determine delimiter
```

Correções aplicadas:

- CSVs temporais vazios agora são escritos com cabeçalhos estáveis;
- arquivos vazios ou contendo somente espaços/quebras de linha são lidos como `DataFrame` vazio;
- foi adicionado teste de regressão para esse caso.

### 2. O workflow pré-Copa destruía o dashboard final

Após o replay no corte pré-Copa, o workflow exportava `src/model-analytics-data.js`. Como ainda não existiam previsões por partida naquele corte, o bundle passava a ter zero jogos. O teste falhava com:

```text
assert payload["summary"]["matches"] == 104
assert 0 == 104
```

Além da falha, o passo de commit podia substituir os artefatos finais por um estado vazio pré-Copa.

Correções aplicadas:

- o workflow pré-Copa agora executa apenas `prepare`;
- não executa replay destrutivo sobre os diretórios canônicos;
- não exporta nem adiciona o dashboard final ao commit;
- os testes iniciais ignoram somente `tests/test_model_dashboard.py`, que valida artefatos finais completos.

### 3. Dois arquivos legados reprovavam todas as runs com teste de integridade

A etapa `scripts/testes/test_integridade_dados.py` falhava porque estes arquivos voltaram ao diretório canônico:

```text
data/atualizacoes_entrada_26-06.csv
data/atualizacoes_entrada_26-06_resultados_desempenho.csv
```

Eles não eram consumidos por nenhum pipeline atual. Foram preservados em:

```text
data/archive/legacy_inputs/
```

### 4. Risco de conflito entre commits de workflows

Os workflows temporais e os workflows da engine esportiva utilizavam grupos de concorrência diferentes, embora todos fizessem `git push` na mesma branch. Isso permitia falhas intermitentes por atualização concorrente, como `non-fast-forward`.

Correção aplicada:

```text
repository-write-${{ github.ref }}
```

Agora os seis workflows que escrevem no repositório são serializados pelo mesmo grupo.

## Loop diagnóstico adicionado

O script abaixo reproduz os fluxos em cópias temporárias, preserva logs completos e classifica falhas recorrentes:

```bash
python scripts/diagnose_github_actions.py --iterations 2
```

Cenários cobertos:

- testes e contratos gerais do repositório;
- pipeline multicampeonato;
- preparação pré-Copa;
- replay exatamente no limite pré-Copa;
- coleta e replay diário até o corte atual;
- arquivos necessários para GitHub Pages;
- análise estática dos workflows, scripts referenciados e concorrência de escrita.

O workflow `.github/workflows/00_run_diagnostics.yml` dispara automaticamente quando uma das principais Actions falha e publica `reports/run_diagnostics/` como artefato, sem fazer commit.

## Resultado das validações locais após as correções

- suíte Pytest: **22 testes aprovados**;
- `scripts/validate_repository.py`: **VALID**;
- `scripts/testes/test_integridade_dados.py`: **OK**;
- pipeline `sports_engine.cli run-registry`: **aprovado**;
- replay no corte pré-Copa em duas iterações: **aprovado**;
- replay diário com configuração diagnóstica reduzida: **aprovado**;
- exportação do dashboard após replay diário: **aprovada**;
- validação dos arquivos do GitHub Pages: **aprovada**.

A coleta externa com rede continua dependente da disponibilidade e dos limites das fontes públicas. O loop classifica separadamente timeout, erro HTTP, rate limit e falha de DNS para não confundir indisponibilidade externa com defeito do código.
