# Análise do repositório DeepLearningExamples usado como referência

O arquivo enviado é o repositório **NVIDIA DeepLearningExamples**, uma coleção grande de exemplos otimizados para GPU/Tensor Cores, com modelos de classificação, recomendação, forecasting, tradução, NLP, visão computacional e inferência via Triton.

Para a Copa 2026, o exemplo mais próximo conceitualmente é o bloco de **PyTorch/Forecasting/TFT**, porque trabalha previsão temporal. Porém, usar o TFT completo seria excessivo para a base atual, que ainda tem poucas partidas reais.

A adaptação feita neste repositório segue o padrão de engenharia do DeepLearningExamples, mas em escala adequada:

- `config.py`: hiperparâmetros e caminhos;
- `data_utils.py`: leitura de CSVs, normalização e engenharia de features;
- `modeling.py`: arquitetura PyTorch;
- `train.py`: treino, validação cronológica e exportação de métricas;
- `inference.py`: inferência para todos os jogos;
- `export_frontend.py`: geração de dados para o visualizador.

A rede criada é uma **MLP PyTorch com embeddings de seleção**, e não uma cópia dos modelos pesados do repositório NVIDIA. Essa decisão evita dependência de Docker, GPU, Triton e bases grandes, mantendo a rede executável localmente no projeto.
