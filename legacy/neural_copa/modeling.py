
from __future__ import annotations

import torch
from torch import nn

class CopaMatchNet(nn.Module):
    """MLP com embeddings de seleção para prever saldo e total de gols.

    O desenho segue a lógica modular dos exemplos de deep learning: embeddings para
    entidades categóricas, bloco MLP para variáveis numéricas e cabeça de regressão.
    """

    def __init__(self, num_teams: int, num_numeric_features: int, embedding_dim: int = 8,
                 hidden_dim_1: int = 96, hidden_dim_2: int = 64, hidden_dim_3: int = 32,
                 dropout: float = 0.12):
        super().__init__()
        self.team_embedding = nn.Embedding(max(1, num_teams), embedding_dim)
        input_dim = num_numeric_features + embedding_dim * 2
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim_1),
            nn.LayerNorm(hidden_dim_1),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim_1, hidden_dim_2),
            nn.LayerNorm(hidden_dim_2),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim_2, hidden_dim_3),
            nn.SiLU(),
            nn.Linear(hidden_dim_3, 2),
        )

    def forward(self, team1_id: torch.Tensor, team2_id: torch.Tensor, numeric_features: torch.Tensor) -> torch.Tensor:
        t1 = self.team_embedding(team1_id)
        t2 = self.team_embedding(team2_id)
        x = torch.cat([numeric_features, t1, t2], dim=1)
        return self.net(x)
