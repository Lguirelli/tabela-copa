# Como adicionar um campeonato

1. Copie `generic_competition_template` em `config/competitions.yaml` e escolha um ID estável, por exemplo `brasileirao_2027`.
2. Defina nome, temporada, país, formato e caminhos dos datasets.
3. Crie ao menos `matches.csv` e `results.csv` com um identificador de partida, data, duas equipes, status e placar real quando disponível.
4. Configure fontes que forneçam os campos ausentes. Desative endpoints ainda não validados.
5. Execute:

```bash
python -m sports_engine.cli completeness --competition brasileirao_2027
python -m sports_engine.cli run-all --competition brasileirao_2027
# para processar todos os campeonatos não-template:
python -m sports_engine.cli run-registry
```

6. Revise `reports/validation_report.json` antes de aceitar modelos ou simulações.

Nenhuma alteração de código é necessária quando os datasets usam os nomes de campos reconhecidos ou quando os aliases principais estão configurados conforme o template.

## Isolamento dos artefatos

Cada campeonato mantém relatórios, logs, padrões, feedback, features e simulações em diretórios com o seu `competition_id`. Os arquivos globais exigidos pela arquitetura original são atualizados como aliases do último campeonato processado, sem apagar o histórico isolado dos demais. Modelos promovidos nunca são compartilhados entre competições.
