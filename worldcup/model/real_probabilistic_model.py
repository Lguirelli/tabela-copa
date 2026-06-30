
import numpy as np

def sigmoid(x):
    return 1/(1+np.exp(-x))

class RealModel:
    def __init__(self, df):
        self.df = df

    def get(self, team):
        row = self.df[self.df["selecao"]==team].iloc[0]
        return row

    def predict(self,a,b):
        A=self.get(a)
        B=self.get(b)

        score = (
            (A.forca_modelo_0_100 - B.forca_modelo_0_100)*0.35 +
            (A.ataque_score - B.defesa_score)*0.25 +
            (A.intensidade_valor - B.intensidade_valor)*0.15 +
            (A.pressao_valor - B.posse_valor)*0.10 +
            (A.experiencia_score - B.experiencia_score)*0.15
        )

        pa = sigmoid(score/10)
        return {"a":a,"b":b,"p_a":float(pa),"p_b":float(1-pa)}
