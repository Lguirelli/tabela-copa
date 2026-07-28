# Implementação legada da Copa 2026

Esta pasta contém a rede neural PyTorch e o modelo diário anteriores à arquitetura atual.
Eles permanecem disponíveis para reprodução histórica, mas **não participam dos workflows padrão**,
não alimentam automaticamente o `sports_engine` e não são necessários para o GitHub Pages.

## Execução manual

```bash
python -m pip install -r requirements-legacy-ml.txt
python legacy/scripts/treinar_rede_neural_copa.py
python legacy/scripts/modelo_neural_diario.py
python legacy/scripts/recalcular_chaveamento_completo.py
```

O pipeline canônico é executado por `scripts/run_repository_pipeline.py` e pelos módulos
`sports_engine/` e `worldcup_brain/`.
