# Projeção completa do chaveamento

- Resultado real é prioridade e nunca é sobrescrito.
- Jogos sem resultado real são recalculados pelo modelo diário incremental.
- O classificado projetado alimenta a próxima fase para manter a tabela completa.
- Em mata-mata, placar empatado gera decisão por pênaltis e vencedor projetado.
- Variáveis de desempenho da Copa entram via rating dinâmico, forma ofensiva, forma defensiva, força dos adversários, momentum, memória de desempenho e `data/entrada/desempenho_manual.csv`.

Jogos reais preservados: 77

Jogos projetados: 27

Decisões por pênaltis na projeção: 0
