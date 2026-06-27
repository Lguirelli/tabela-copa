
from __future__ import annotations

from .train import run_training
from .inference import run_inference
from .export_frontend import export_frontend


def main():
    metrics = run_training()
    run_inference()
    export_frontend()
    print("Rede neural da Copa criada e exportada para o front.")
    print(metrics)


if __name__ == "__main__":
    main()
