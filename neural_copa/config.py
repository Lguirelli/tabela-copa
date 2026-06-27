from dataclasses import dataclass
from pathlib import Path

@dataclass
class NeuralCopaConfig:
    seed: int = 2026
    embedding_dim: int = 8
    hidden_dim_1: int = 96
    hidden_dim_2: int = 64
    hidden_dim_3: int = 32
    dropout: float = 0.12
    learning_rate: float = 0.003
    weight_decay: float = 0.0007
    epochs: int = 260
    patience: int = 35
    max_goals: int = 7

    @property
    def root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def output_dir(self) -> Path:
        return self.root / "data" / "rede_neural"

    @property
    def checkpoint_path(self) -> Path:
        return self.output_dir / "modelo_rede_neural_copa.pt"
