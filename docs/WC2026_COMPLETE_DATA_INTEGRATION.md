# Integração do pacote completo de dados da Copa 2026

## Política de integração

A fonte recebida possui 104 partidas e manifesto SHA-256 com 783 arquivos. Todos os hashes foram verificados antes da importação.

O campo `jogo` do pacote não é usado diretamente como chave. O integrador compara a dupla não ordenada de seleções com `data/resultados_reais.csv` e produz uma bijeção de 104 partidas. Essa regra detectou:

- jogo 89 da fonte → jogo 90 canônico;
- jogo 90 da fonte → jogo 89 canônico;
- cinco diferenças de data causadas pela separação entre data do calendário e data UTC da fonte.

Os resultados canônicos não foram alterados. `data/normalized/results_validated.csv` preserva a validação ESPN e alinha orientação, equipes e placar ao repositório.

## Dados incorporados

| Domínio | Arquivo canônico | Registros | Cobertura |
|---|---|---:|---:|
| Eventos | `data/normalized/espn_match_events.csv` | 4.248 | 104 jogos |
| Narração | `data/normalized/espn_match_commentary.csv` | 11.815 | 104 jogos |
| Estatísticas de equipe | `data/normalized/espn_team_match_stats.csv` | 208 | 104 jogos |
| Jogadores | `data/platform/player_match_stats.csv` | 5.323 | 104 jogos |
| Escalações observadas | `data/platform/lineups.csv` | 5.323 | 104 jogos |
| Árbitros principais | `data/platform/match_officials.csv` | 104 | 104 jogos |
| Pênaltis individuais | `data/normalized/espn_penalty_shootouts.csv` | 40 | 4 jogos |

## Controle temporal

Os dados foram coletados em 20/07/2026. Eles são classificados como `POST_MATCH_BACKFILLED_FACT`.

- Não são retrodatados.
- Escalações e árbitros usam `available_at = source_collected_at`.
- O replay pré-jogo continua considerando esses campos indisponíveis nos cutoffs históricos.
- As análises pós-jogo podem utilizar eventos, estatísticas de equipe e evidências individuais.

## Ausências preservadas

Os seguintes campos continuam `NA` porque não existem na fonte:

- minutos individuais;
- xG e xA individuais;
- rating de jogador;
- disponibilidade/lesões com timestamp histórico;
- assistentes e VAR completos;
- confirmação FIFA renderizada para os 104 placares.

## Rastreabilidade

- `data/audit/wc2026_complete_20260720/MANIFEST_SHA256.csv`
- `data/audit/wc2026_complete_20260720/integration_manifest.csv`
- `data/audit/wc2026_complete_20260720/raw_manifest.jsonl`
- `data/raw/wc2026_complete_20260720/`
- `reports/wc2026_complete_data_integration.json`
- `data/mappings/incoming_game_id_mapping_20260720.csv`
