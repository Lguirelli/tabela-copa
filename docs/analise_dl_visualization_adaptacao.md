# Adaptação visual inspirada em `dl-visualization-master`

O repositório `dl-visualization-master` usa uma lógica didática de visualização de redes: curvas de treino, separação entre dados de entrada, camadas, ativação e resultado final. A adaptação para este projeto não copia as animações Manim; ela converte a ideia para um dashboard estático/HTML que ajuda a interpretar a rede neural da Copa.

## Elementos adaptados

- Curva de treino e validação: mostra `train_loss` e `val_loss` por época.
- Validação temporal: mostra acurácia de vencedor e placar exato por data.
- Mapa dos times: projeta seleções por competitividade de liga e desempenho de jogadores, usando força contextual como intensidade visual.
- Importância operacional: apresenta os pesos das variáveis usadas no modelo contextual.
- Erro da rede: compara previsão da rede neural com resultado real e lista os maiores erros.

## Objetivo

A página `rede-neural.html` passa a servir não apenas como diagrama de arquitetura, mas como painel de diagnóstico: entender onde a rede melhora, onde erra, quais variáveis estão influenciando e quais seleções estão sendo superestimadas ou subestimadas.
