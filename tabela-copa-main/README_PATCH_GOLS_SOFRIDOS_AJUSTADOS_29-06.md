# Patch — gols sofridos ajustados pela força do adversário

Este patch corrige o modelo para tratar gols sofridos com ajuste de qualidade do adversário.

## Nova lógica

- Gol marcado contra adversário forte vale mais para a forma ofensiva.
- Gol sofrido contra adversário forte gera punição menor.
- Gol sofrido contra adversário fraco gera punição maior.
- Segurar adversário forte abaixo do xG gera recompensa defensiva maior.
- Gols marcados e gols sofridos continuam separados; saldo não vira atalho principal.

## Funções adicionadas

Em `scripts/modelo_neural_diario.py`:

- `opponent_quality_factor()`
- `goal_scored_multiplier()`
- `goal_conceded_damage_multiplier()`
- `defensive_gap_adjusted_signal()`

O script `scripts/recalcular_chaveamento_completo.py` usa as mesmas funções para manter o chaveamento projetado coerente com o modelo diário.

## Novas colunas

Em `data/modelo_diario/validacao_dia_a_dia.csv`:

- `peso_adversario_ofensivo_equipe1`
- `peso_adversario_ofensivo_equipe2`
- `peso_gol_sofrido_equipe1`
- `peso_gol_sofrido_equipe2`
- `qualidade_adversario_equipe1`
- `qualidade_adversario_equipe2`

Em `data/modelo_diario/estado_times_dia_a_dia.csv`:

- `gols_marcados_ajustados_por_jogo`
- `gols_sofridos_ajustados_por_jogo`

## Como aplicar

Substitua os arquivos do patch e rode:

```bash
python scripts/atualizar_modelo.py
```

