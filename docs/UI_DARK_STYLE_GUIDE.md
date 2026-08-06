# Guia visual — Dark Intelligence UI

## Leitura das referências fornecidas

As duas pranchas apontam para uma linguagem de produto de dados/IA, não para um dashboard esportivo tradicional. Os elementos recorrentes são:

- fundo quase preto, com variação azul-marinho e iluminação localizada;
- cards escuros delimitados por bordas finas, sem sombras pesadas;
- ciano, verde elétrico e violeta usados como sinal, não como preenchimento dominante;
- números grandes, rótulos curtos em caixa alta e bastante contraste de escala;
- gráficos, redes e mapas tratados como o principal elemento visual;
- navegação compacta, com o item ativo marcado por brilho ou filete colorido;
- grades técnicas, halos e linhas luminosas em baixa opacidade;
- cantos arredondados moderados, entre 11 e 22 pixels.

## Referências complementares pesquisadas

- [Dark analytics dashboards no Dribbble](https://dribbble.com/search/analytics-dashboard-dark): referência para cards, KPIs e densidade de dados.
- [Football dashboards no Dribbble](https://dribbble.com/search/football-dashboard): referência para placares, tabelas e hierarquia esportiva.
- [Match dashboards no Dribbble](https://dribbble.com/search/match-dashboard): referência para interfaces de partida e comparação entre equipes.
- [Galeria de dashboards da Muzli](https://muz.li/inspiration/dashboard-inspiration/): referência para composição modular e visualização analítica.
- [Dark SaaS no SaaSpo](https://saaspo.com/style/dark-mode): referência para fundos, headers e uso controlado de iluminação.

## Sistema aplicado

| Papel | Valor | Uso |
| --- | --- | --- |
| Fundo | `#05070a` | Base da aplicação |
| Superfície | `#0b1017` | Painéis e navegação |
| Superfície elevada | `#101722` | Cards e controles |
| Texto | `#f5f8fc` | Títulos e valores |
| Texto secundário | `#8895a7` | Rótulos e explicações |
| Ciano | `#53b8ff` | Navegação, gráficos e foco |
| Verde | `#6df7a7` | Acertos, validações e progresso |
| Violeta | `#9b8cff` | Séries auxiliares |
| Âmbar | `#ffb454` | Atenção e pendências |
| Vermelho | `#ff6b86` | Erros e risco |

## Decisões de implementação

- O modo escuro é fixo com `color-scheme: dark`.
- A grade de fundo é gerada em CSS; nenhuma imagem ou fonte externa foi adicionada.
- Brilhos são estáticos e localizados para reduzir custo de renderização.
- Componentes interativos possuem foco visível por teclado.
- Movimentos de hover são desativados quando `prefers-reduced-motion` está ativo.
- O layout mantém os breakpoints de desktop, tablet e celular.
- Tabelas continuam horizontalmente navegáveis em telas estreitas.
- O modo de alto contraste do sistema remove ornamentos e preserva contornos.

## Regra de consistência

Novos componentes devem priorizar contraste, leitura e densidade informacional. Neon deve marcar estado, seleção ou dado relevante; nunca deve competir com o conteúdo principal.
