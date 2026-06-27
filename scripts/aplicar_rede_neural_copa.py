
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from neural_copa.inference import run_inference
from neural_copa.export_frontend import export_frontend

if __name__ == "__main__":
    run_inference(ROOT)
    export_frontend(ROOT)
    print("Inferência da rede neural aplicada e front atualizado.")
