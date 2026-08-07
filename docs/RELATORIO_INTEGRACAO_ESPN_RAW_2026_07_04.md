# Integração ESPN/FIFA raw extract — 2026-07-04

Base integrada: `wc2026_raw_extract_20260704T010732Z.zip`.

## Saídas normalizadas

- `data/normalized/espn_matches.csv`: calendário/resultados/status a partir do scoreboard ESPN.
- `data/normalized/espn_team_match_stats.csv`: estatísticas por seleção e partida.
- `data/normalized/espn_match_events.csv`: eventos e comentários estruturados.
- `data/normalized/espn_penalty_shootouts.csv`: eventos relacionados a pênaltis/disputa por pênaltis quando disponíveis.
- `data/normalized/espn_desempenho_manual_integrado.csv`: linhas ESPN transformadas no schema de desempenho auditável usado pelo modelo diário.
- `data/normalized/source_manifest_20260704T010732Z.csv` e `data/raw_manifest_20260704T010732Z.jsonl`: rastreabilidade da coleta.

## Atualização do modelo

A base ESPN foi usada como entrada de desempenho em `data/entrada/desempenho_manual.csv`, com fonte explícita por `event_id`. O modelo diário foi recalculado depois da integração para atualizar momentum, forma ofensiva/defensiva, probabilidades e chance de decisão por pênaltis.

## Contagem

- Eventos ESPN no scoreboard: 104.
- Eventos mapeados para jogos do repositório: 92.
- Jogos completos no scoreboard ESPN: 87.
- Linhas de estatística por time normalizadas: 208.
- Eventos normalizados: 11274.
- Linhas de desempenho ESPN adicionadas ao modelo: 168.
- Resultados preenchidos que estavam ausentes/não finalizados: 0.
- Resultados já existentes validados com ESPN: 84.
- Conflitos preservados em arquivo: 0.

## Observação

A integração não rebaixa resultados mais recentes já finalizados no repositório quando o raw extract ainda traz o jogo como agendado. Nesses casos, o dado novo fica como camada auditável, sem sobrescrever o consolidado.
