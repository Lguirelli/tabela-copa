# Validação — gols sofridos ajustados

Validação executada após recalcular o modelo:

- `python -m py_compile scripts/modelo_neural_diario.py scripts/recalcular_chaveamento_completo.py`
- `python scripts/atualizar_modelo.py`
- Busca por marcadores de conflito marcadores padrão de conflito do Git

## Resultado

- Scripts Python compilando.
- 75 resultados reais preservados.
- 29 jogos projetados recalculados.
- Saídas do modelo diário regeneradas.
- `estado_times_dia_a_dia.csv` inclui gols sofridos ajustados por jogo.
- `validacao_dia_a_dia.csv` inclui peso específico para gols sofridos.

## Exemplo da lógica

No jogo Alemanha x Paraguai, a Alemanha sofreu gol contra adversário de qualidade menor relativa, então o dano defensivo entra com peso maior para a Alemanha. O Paraguai sofreu gol de uma Alemanha mais forte, então o dano defensivo é amortecido.

No jogo Brasil x Japão, ambos sofreram contra adversários fortes, mas o Japão recebe ajuste defensivo mais negativo porque o volume/xG brasileiro foi superior.
