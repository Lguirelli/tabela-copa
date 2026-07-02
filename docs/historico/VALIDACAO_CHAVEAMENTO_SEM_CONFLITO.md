# Validação — chaveamento sem conflito

Correção aplicada em `src/dashboard.js` para impedir que o chaveamento misture:

1. placar real;
2. vencedor previsto do modelo diário;
3. confronto antigo salvo em `matches.csv` ou arquivos gerados anteriores.

## Regra atual

- Jogos finalizados continuam usando o placar real.
- Jogos ainda não finalizados da primeira rodada de mata-mata usam o modelo diário quando o confronto bate com o arquivo de previsão.
- Jogos de fases seguintes são derivados dos vencedores reais ou previstos dos jogos anteriores.
- Quando o confronto derivado não bate com a previsão já salva, o card não exibe placar antigo. Ele mostra `Aguardando recálculo`.

## Exemplo corrigido

Antes, o chaveamento podia exibir:

```txt
Jogo 78: Costa do Marfim 1-0 Noruega
Jogo 91: Brasil 1-2 Noruega
```

Agora fica coerente:

```txt
Jogo 78: Costa do Marfim 1-0 Noruega
Jogo 91: Brasil x Costa do Marfim — aguardando recálculo
```

Isso evita que um time eliminado/projetado como perdedor avance por causa de dados antigos.

## Validação local

- `node --check src/dashboard.js`
- Não há vencedor previsto fora das duas equipes exibidas no card.
- Jogos derivados sem previsão compatível ficam marcados como `Aguardando recálculo`.
