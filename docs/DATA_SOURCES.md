# Fontes de dados e segurança temporal

## Regra central

Todo registro capaz de influenciar uma previsão precisa ter `available_at` ou `published_at`. Em uma reconstrução histórica, o registro só pode ser usado quando esse timestamp é anterior ou igual ao corte da previsão.

## Fontes configuradas

| Fonte | Uso | Autenticação | Regra temporal |
| --- | --- | --- | --- |
| FIFA World Ranking | força oficial da seleção | snapshot curado | publicação deve anteceder o corte |
| football-data.org v4 | confirmação independente, partidas e histórico | `FOOTBALL_DATA_API_TOKEN` | `published_at` deve anteceder o corte |
| Hudl StatsBomb Open Data | eventos históricos para pesquisa de features | pública | cobertura e temporada precisam ser declaradas |
| Open-Meteo Previous Runs | temperatura, umidade, chuva e vento previstos | pública | somente execução meteorológica arquivada anterior ao jogo |
| ESPN | eventos, estatísticas e escalações | pública | coleta pós-jogo não pode voltar ao snapshot pré-jogo |

## Critério de entrada no modelo

Uma nova variável não ganha peso apenas por estar disponível. Ela precisa:

1. ter amostra mínima;
2. manter direção consistente nas divisões cronológicas;
3. apresentar evidência estatística no processo de descoberta;
4. reduzir o log-loss em holdout cronológico;
5. respeitar a margem mínima de melhoria definida no modelo.

No cérebro temporal, apenas um coeficiente é avaliado por checkpoint. A busca roda em modo sombra por padrão: registra a candidata, mas não altera previsões. A ativação exige validação externa em outra competição ou temporada.

## Dados ainda não disponíveis

Lesões pré-jogo, condição física e carga recente de atletas continuam `NA` quando não existe arquivo histórico publicado antes do jogo. Escalações e minutos obtidos depois da partida são úteis para aprendizagem pós-jogo, mas não são retroativamente usados na previsão original.
