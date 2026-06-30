# Patch — modelo mais verídico com peso de adversário

Correção aplicada em 29/06.

## Objetivo

Evitar que o modelo inflasse seleções por saldo simples, momentum ou ruído da rede neural.

## Mudanças principais

1. **Gols marcados e sofridos separados**
   - Gols marcados atualizam `forma_ofensiva`.
   - Gols sofridos atualizam `forma_defensiva`.
   - O saldo não é mais usado como atalho principal para subir rating.

2. **Peso do adversário**
   - Vitória contra adversário forte vale mais.
   - Gol marcado contra adversário forte vale mais.
   - Gol sofrido contra adversário fraco pesa mais negativamente.
   - Foram adicionadas as variáveis:
     - `forca_media_adversarios`
     - `pontos_ajustados_por_adversario`
     - `gols_marcados_ajustados_por_adversario`
     - `gols_sofridos_ajustados_por_adversario`

3. **Rede neural virou calibrador conservador**
   - Peso máximo reduzido para 8%.
   - A rede não pode inverter favorito quando xG/rating/desempenho dão vantagem clara ao outro lado.
   - Em margens muito apertadas, o desempate usa xG/modelo base, não ruído da rede.

4. **Pênaltis continuam suportados**
   - Se o mata-mata terminar empatado na projeção, o sistema decide nos pênaltis.
   - Classificação por pênaltis recebe confiança baixa.

5. **Chaveamento recalculado**
   - Resultados reais foram preservados.
   - Apenas jogos sem resultado real foram recalculados.
   - Costa do Marfim continua com leve vantagem contra Noruega, mas não aparece mais como favorita forte contra o Brasil.

## Arquivos principais alterados

- `scripts/modelo_neural_diario.py`
- `scripts/recalcular_chaveamento_completo.py`
- `data/modelo_diario/previsoes_dia_a_dia.csv`
- `data/modelo_diario/projecao_chaveamento_completa.csv`
- `data/modelo_diario/estado_times_dia_a_dia.csv`
- `data/modelo_diario/validacao_dia_a_dia.csv`
- `data/modelo_diario/metricas_modelo.json`
- `data/matches.csv`
- `data/database/matches.csv`
- `data/matches.json`
- `src/data.js`
- `src/modelo-diario-data.js`

## Como atualizar depois de inserir novos dados

Preencha:

- `data/entrada/novos_resultados.csv`
- `data/entrada/desempenho_manual.csv`

Depois rode:

```bash
python scripts/atualizar_modelo.py
```
