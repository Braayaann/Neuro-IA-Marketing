"""Ajuste de nueve objetivos a partir del iris de MediaPipe, sin modelo de cabeza."""
import numpy as np

OBJETIVOS = [(x, y) for y in (.12, .5, .88) for x in (.12, .5, .88)]


class Calibracion:
    def ajustar(self, iris, objetivos=OBJETIVOS):
        x = np.asarray(iris, dtype=float)
        y = np.asarray(objetivos, dtype=float)
        if x.shape != (9, 2) or y.shape != (9, 2) or not np.isfinite([x, y]).all():
            raise ValueError('Se necesitan nueve posiciones válidas.')
        self.media = x.mean(0)
        self.escala = x.std(0)
        if min(self.escala) < 1e-5:
            raise ValueError('El iris casi no varió: repite la calibración.')
        matriz = np.column_stack((np.ones(9), (x-self.media)/self.escala))
        if np.linalg.matrix_rank(matriz) < 3:
            raise ValueError('La calibración no cubre ambas direcciones.')
        self.coeficientes = np.linalg.lstsq(matriz, y, rcond=None)[0]
        return self

    def predecir(self, iris):
        return np.r_[1., (np.asarray(iris)-self.media)/self.escala] @ self.coeficientes
