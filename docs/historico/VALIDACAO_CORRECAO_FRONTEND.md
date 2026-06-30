# Correção do carregamento dos últimos jogos

## Problema identificado

O CSV `data/resultados_reais.csv` já tinha os 72 jogos finalizados da fase de grupos, mas o visualizador estava lendo os dados compilados em JavaScript, principalmente:

- `src/rede-neural-data.js`
- `src/data.js`

Esses arquivos ainda estavam com parte dos jogos finais como `possui_real = Não`, então a interface continuava exibindo alguns jogos como previsão/rede neural em vez de resultado real.

## Correção aplicada

- Reprocessei a rede neural com os 72 resultados reais.
- Atualizei `data/rede_neural/previsoes_rede_neural.csv`.
- Atualizei `src/rede-neural-data.js` para marcar os jogos 63 a 72 como reais.
- Atualizei `src/data.js` para incluir `placar_real`, `vencedor_real`, `gols1_real`, `gols2_real` e `status = Finalizado` nos jogos que já têm resultado real.
- Ajustei `src/dashboard.js` para usar o resultado real vindo de `src/data.js` como fallback, caso a previsão neural ainda esteja desatualizada.
- Ajustei `neural_copa/knockout.py` para incorporar `data/resultados_reais.csv` no export do frontend.
- Ajustei `scripts/atualizar_modelo.py` para aceitar entrada manual em CSV com vírgula ou ponto e vírgula e validar se o frontend ficou sincronizado.
- Limpei `data/entrada/novos_resultados.csv`, deixando apenas o cabeçalho para próximas entradas manuais.

## Validação

Resultado esperado após a correção:

- `data/resultados_reais.csv`: 72 jogos reais.
- `src/rede-neural-data.js`: 72 jogos com `possui_real = Sim`.
- `src/data.js`: `summary.resultadosReais = 72`.
- Jogos 63 a 72 aparecem como finalizados no visualizador.

Jogos finais verificados:

| Jogo | Resultado |
|---:|---|
| 63 | Egito 1-1 Irã |
| 64 | Nova Zelândia 1-5 Bélgica |
| 65 | Cabo Verde 0-0 Arábia Saudita |
| 66 | Uruguai 0-1 Espanha |
| 67 | Panamá 0-2 Inglaterra |
| 68 | Croácia 2-1 Gana |
| 69 | Argélia 3-3 Áustria |
| 70 | Jordânia 1-3 Argentina |
| 71 | Colômbia 0-0 Portugal |
| 72 | RD Congo 3-1 Uzbequistão |

## Como atualizar manualmente daqui para frente

1. Preencha `data/entrada/novos_resultados.csv`.
2. Rode:

```bash
python scripts/atualizar_modelo.py
```

O script atualiza `data/resultados_reais.csv`, limpa a entrada, retreina/reexporta a rede neural e valida se o frontend recebeu todos os resultados reais.
