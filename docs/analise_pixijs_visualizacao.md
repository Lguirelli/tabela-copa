# Adaptação visual com PixiJS

O arquivo `pixijs-dev.zip` foi usado como referência de arquitetura visual para criar uma camada interativa em Canvas/WebGL na página `rede-neural.html`.

## Implementado

- `src/pixi-neural-view.js`: visualização interativa do fluxo da rede neural.
- Zoom com scroll, pan com arraste e reset com duplo clique.
- Fallback em Canvas 2D quando o PixiJS externo não estiver disponível.
- Integração com `src/rede-neural-data.js`, `src/modelo-dados.js` e métricas já exportadas pelo PyTorch.

## Por que não copiar o PixiJS inteiro

O repositório enviado é o código-fonte de desenvolvimento do PixiJS. Para manter o projeto leve e estático, o viewer usa o PixiJS por CDN e mantém um fallback local. Assim o repositório não precisa carregar dezenas de megabytes de fonte ou build.
