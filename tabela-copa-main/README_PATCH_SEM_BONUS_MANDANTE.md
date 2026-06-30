# Patch - Remoção do bônus de mandante/sede

Este patch remove o bônus de mandante/sede do modelo diário e do desempate por pênaltis.

Regra atual:

- país-sede não adiciona vantagem automática;
- `feature_host_diff` foi mantida por compatibilidade histórica, mas sempre fica `0.0`;
- pênaltis não usam mais país/sede como fator;
- gols marcados, gols sofridos, força do adversário, descanso, rating, forma ofensiva/defensiva e desempenho continuam ativos.

Arquivos de `git remove` não foram recriados neste patch.

Após aplicar, rode:

```bash
python scripts/atualizar_modelo.py
```
