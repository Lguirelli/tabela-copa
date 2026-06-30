
from fastapi import FastAPI
from model.predictor import run_predictions

app = FastAPI()

@app.get("/predictions")
def predictions():
    return run_predictions()

@app.get("/health")
def health():
    return {"status": "ok"}
