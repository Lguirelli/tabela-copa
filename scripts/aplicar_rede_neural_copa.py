
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from neural_copa.inference import run_inference
from neural_copa.export_frontend import export_frontend
from neural_copa.knockout import rebuild_knockout_from_neural

if __name__ == "__main__":
    run_inference(ROOT)
    rebuild_knockout_from_neural(ROOT)
    export_frontend(ROOT)
    print("Inferência da rede neural aplicada e front atualizado.")
