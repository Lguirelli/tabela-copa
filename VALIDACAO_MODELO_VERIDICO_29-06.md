# Validação — modelo verídico 29/06

Validações executadas:

- Scripts Python compilando sem erro.
- JS do frontend validado com `node --check`.
- Resultado real nunca sobrescrito.
- 75 jogos reais preservados.
- 29 jogos ainda projetados.
- `data/entrada/desempenho_manual.csv` segue como entrada manual ativa.
- `data/entrada/desempenho_times_fase_grupos.csv` segue como base manual de estudo da fase de grupos.
- Chaveamento recalculado após Alemanha 1 (3) x 1 (4) Paraguai.

## Correção específica Costa do Marfim

Antes, o modelo carregava momentum/defesa e ruído neural de forma excessiva.
Agora:

- Costa do Marfim x Noruega: favoritismo leve/baixa confiança.
- Brasil x Costa do Marfim: Brasil volta a ser favorito no modelo.
- Gols sofridos e gols marcados são avaliados separadamente.
- Força dos adversários enfrentados entra no cálculo.

## Métricas novas no estado dos times

- `forma_ofensiva`
- `forma_defensiva`
- `forca_media_adversarios`
- `pontos_ajustados_por_adversario`
- `gols_marcados_ajustados_por_adversario`
- `gols_sofridos_ajustados_por_adversario`
