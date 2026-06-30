# Projeção completa do chaveamento

- Resultado real é prioridade e nunca é sobrescrito.
- As probabilidades são recalculadas para todos os jogos a cada execução, inclusive os já finalizados.
- Jogos finalizados preservam o placar real, mas atualizam a leitura do modelo e alimentam o estado de desempenho.
- O classificado real ou projetado alimenta a próxima fase para manter a tabela completa.
- Em mata-mata, placar empatado gera decisão por pênaltis e vencedor projetado.
- Variáveis de desempenho da Copa entram via rating dinâmico, forma ofensiva, forma defensiva, força dos adversários, momentum, memória de desempenho e `data/entrada/desempenho_manual.csv`.

Jogos reais preservados: 76

Jogos projetados: 28

Decisões por pênaltis na projeção: 0
