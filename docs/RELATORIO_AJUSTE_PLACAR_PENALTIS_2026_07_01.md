# Ajuste do modelo — placares 1-0 e probabilidade de pênaltis

## Problema identificado

O modelo estava exibindo repetidamente placares como `1-0` e `0-1` porque o placar principal vinha do **placar modal bruto** da distribuição Poisson/Monte Carlo.

Em futebol, quando os xG ficam próximos de 1 gol por equipe, o placar individual mais provável costuma ser `1-0`, `0-1`, `1-1` ou `0-0`, mesmo que a soma de todos os cenários de `2-1`, `2-0`, `1-2`, `2-2` etc. também seja relevante. Isso gerava uma tela com pouca variação e deixava o modelo conservador demais.

## Correção aplicada

### 1. Placar representativo

O campo `placar_previsto` agora deixa de ser apenas o placar modal bruto. O modelo calcula um **placar representativo condicional ao resultado mais provável**, considerando:

- probabilidade do placar;
- aderência ao xG total;
- aderência à margem esperada;
- penalização leve de `1-0`/`0-1` quando o jogo tem volume para 2+ gols;
- variação determinística por jogo para evitar repetição artificial.

O placar modal antigo continua preservado no campo:

- `placar_modal_bruto`

E o critério usado aparece em:

- `metodo_placar`
- `criterio_resultado_modelado`

### 2. Probabilidade de pênaltis

Em jogos de mata-mata, o modelo agora calcula:

- `prob_decisao_penaltis`

A aproximação usada é:

```text
P(pênaltis) = P(empate em 90 min) × P(empate na prorrogação)
```

A prorrogação é aproximada com `xG / 3`, equivalente ao volume de 30 minutos em relação aos 90 minutos.

### 3. Pênaltis como critério de classificação

Quando o jogo é de mata-mata e o risco de empate/pênaltis está próximo da maior probabilidade de vitória, o modelo permite que o placar base seja empate e aciona a decisão por pênaltis.

Campos gerados:

- `decisao_penaltis`
- `placar_penaltis`
- `prob_penaltis_equipe1`
- `vencedor_pos_penaltis`
- `criterio_vencedor`

## Resultado prático

O modelo deixa de forçar tantos `1-0` como placar principal e passa a exibir tanto o placar representativo quanto o risco de pênaltis no mata-mata.
