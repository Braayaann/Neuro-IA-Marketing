"""Resúmenes numéricos copiables. No escribe imágenes ni archivos."""
import json

import numpy as np


def emitir(evento, **datos):
    def convertir(valor):
        if isinstance(valor, np.ndarray):
            return np.round(valor, 6).tolist()
        if isinstance(valor, np.generic):
            return valor.item()
        raise TypeError(type(valor).__name__)
    print('[NEURO] ' + json.dumps(dict(evento=evento, **datos), default=convertir,
                                  ensure_ascii=True, allow_nan=False), flush=True)


class ResumenTerminal:
    def __init__(self, inicio):
        self.inicio = inicio
        self.ultimo = inicio
        self.frames = 0
        self.muestras = []

    def actualizar(self, ahora, iris, **datos):
        self.frames += 1
        if iris is not None:
            self.muestras.append(np.asarray(iris).copy())
        intervalo = ahora-self.ultimo
        if intervalo < 2.:
            return
        emitir('seguimiento', segundos=round(ahora-self.inicio, 2),
               fps=round(self.frames/intervalo, 1),
               validas_pct=round(100*len(self.muestras)/self.frames, 1),
               dispersion_iris=np.std(self.muestras, axis=0) if self.muestras else None,
               iris=iris, **datos)
        self.ultimo = ahora
        self.frames = 0
        self.muestras = []
