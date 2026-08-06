
from __future__ import annotations

from .train import run_training
from .inference import run_inference
from .export_frontend import export_frontend
from .knockout import rebuild_knockout_from_neural


def main():
    metrics = run_training()
    run_inference()
    rebuild_knockout_from_neural()
    export_frontend()
    print("Rede neural da Copa criada e exportada para o front.")
    print(metrics)


if __name__ == "__main__":
    main()
