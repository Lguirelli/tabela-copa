# Relatório diário de atualização sem API key

Executado em: 2026-06-28T11:19:44+00:00
Datas verificadas: 2026-06-23, 2026-06-24, 2026-06-25, 2026-06-26, 2026-06-27, 2026-06-28
Offline: False

## Regra
Sem proxy, sem estimativa e sem API key. Apenas dados diretos de endpoint público sem chave ou dados existentes do repositório.

## Resultados
- Jogos finalizados mantidos em finished_matches_espn.csv: 92
- Linhas de estatísticas diretas ESPN: 1568
- Linhas de eventos diretos ESPN: 0
- Jogos atualizados em resultados_reais.csv/matches.csv: 86

## Limitações
ESPN é endpoint público não oficial/sem key. Se indisponível, o script não força scraping e não inventa dados.
Campos não retornados pela fonte ficam NA.