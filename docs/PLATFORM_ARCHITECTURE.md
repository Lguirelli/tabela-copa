# Arquitetura da plataforma preditiva multicampeonato

## Princípios

A plataforma é composta por processos determinísticos executados dentro do repositório. Não há agente autônomo, sistema conversacional ou execução fora dos workflows versionados.

1. **Configuração por campeonato:** `config/competitions.yaml` define temporada, formato, datasets, fontes e limites estatísticos. `run-registry` executa todos os blocos não marcados como template.
2. **Dados observados preservados:** módulos de enriquecimento somente inserem registros ausentes; valores existentes não são sobrescritos.
3. **Ausência explícita:** dados não encontrados permanecem `NA` e geram itens em `data/queues/missing_data.json`.
4. **Rastreabilidade:** relatórios e modelos incluem hashes dos arquivos de entrada, horário UTC e método utilizado.
5. **Evidência antes de feature:** uma feature só entra no registro aceito quando possui amostra mínima, correlação mínima e direção estável no tempo.
6. **Sem causalidade implícita:** padrões e feedback descrevem associações e sinais diagnósticos, não causas comprovadas.

## Fluxo

```text
config/competitions.yaml
        │
        ▼
Loop 01 ──► fila de dados ausentes
        │
Loop 02 ──► fontes locais/HTTP configuradas ──► staging/raw/logs
        │
Loop 03 ──► relatório de validação
        │
Loop 04 ──► padrões estatísticos
        │
Loop 05 ──► feedback das previsões
        │
Loop 06 ──► registro de features com evidência
        │
Loop 08 ──► versão candidata/promovida do modelo
        │
Loop 07 ──► simulações Monte Carlo atualizadas
        ▼
reports/competitions/<id>/final_system_status.json
        └──► reports/final_system_status.json (alias de compatibilidade)
```

## Módulos

- `sports_engine/config.py`: carrega o campeonato selecionado.
- `sports_engine/io.py`: leitura tolerante a CSV, escrita atômica, normalização e hashes.
- `sports_engine/sources.py`: adaptadores de coleta; inclui dataset local e scoreboard público ESPN.
- `sports_engine/loops/`: oito loops independentes.
- `sports_engine/modeling.py`: regressão ridge reprodutível para recalibração.
- `sports_engine/pipeline.py`: orquestra os loops, sem comportamento autônomo.
- Artefatos de execução são persistidos por competição; caminhos globais exigidos pelo projeto são aliases do último campeonato processado.
- `sports_engine/cli.py`: interface executável para GitHub Actions e uso local.

## Fontes e confiança

As fontes são ordenadas por prioridade. A configuração atual mantém fonte oficial como prioridade conceitual, API pública como complementar e arquivos locais já coletados como fallback. Um adaptador sem parser seguro não altera datasets: registra a tentativa e mantém `NA`.

Campos que contenham indicação de simulação, como os perfis sintéticos de arbitragem legados, são excluídos automaticamente da descoberta de features.

## Modelo e promoção

A recalibração usa divisão cronológica 80/20 e regressão ridge para diferença de gols e total de gols. O modelo só é promovido para `models/model_versions/<competition_id>/latest.json` quando reduz o MAE médio no holdout cronológico. Modelos rejeitados continuam versionados para auditoria.

## Compatibilidade

O visualizador da Copa 2026 e os scripts `neural_copa/` foram preservados. A nova engine não altera placares reais nem substitui automaticamente o modelo visual legado. Ela produz uma camada multicampeonato em `models/`, `reports/`, `logs/` e `data/queues/`.
