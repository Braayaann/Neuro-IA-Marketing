"""Captura de un objetivo de calibración sin suavizado ni cambio de modelo."""
from dataclasses import dataclass

import numpy as np


@dataclass
class ResultadoPunto:
    posicion: np.ndarray | None
    motivo: str


class CapturaPunto:
    """Espera 1,2 s y evalúa 2,4 s de señal binocular relativa.

    Los umbrales de dispersión están en anchos de ojo, no en píxeles de
    pantalla. Son heurísticos; una captura estable no demuestra precisión.
    """

    preparacion = 1.2
    duracion = 2.4
    minimo_muestras = 20
    tolerancia = np.array([.012, .008])

    def __init__(self, inicio, tolerancia=None, duracion=None):
        self.inicio = inicio
        self.tolerancia = np.asarray(self.tolerancia if tolerancia is None else tolerancia, dtype=float).copy()
        self.duracion = self.duracion if duracion is None else float(duracion)
        if self.tolerancia.shape != (2,) or not np.isfinite(self.tolerancia).all() or (self.tolerancia <= 0).any() or not np.isfinite(self.duracion) or self.duracion < 2.4:
            raise ValueError('Tolerancias positivas de dos ejes y duración mínima de 2,4 s requeridas.')
        self.muestras = []
        self.tiempos = []
        self.total = 0
        self.resultado = None

    def estado(self, ahora):
        transcurrido = ahora - self.inicio
        if transcurrido < self.preparacion:
            return 'PREPARATE', max(0., self.preparacion-transcurrido)
        return 'CAPTURANDO', max(0., self.preparacion+self.duracion-transcurrido)

    def actualizar(self, iris, ahora):
        if self.resultado is not None:
            return self.resultado
        t = ahora - self.inicio - self.preparacion
        if t < 0:
            return None
        if t >= self.duracion:
            self.resultado = self._evaluar()
            return self.resultado
        self.total += 1
        if iris is not None:
            muestra = np.asarray(iris, dtype=float)
            if muestra.shape == (2,) and np.isfinite(muestra).all():
                self.muestras.append(muestra.copy())
                self.tiempos.append(t)
        return None

    def _evaluar(self):
        if len(self.muestras) < self.minimo_muestras:
            return ResultadoPunto(None, 'Pocas muestras: mantén ambos ojos visibles.')
        if len(self.muestras) / self.total < .75:
            return ResultadoPunto(None, 'Se perdió demasiado la detección de los ojos.')
        muestras = np.asarray(self.muestras)
        mediana = np.median(muestras, axis=0)
        estables = (np.abs(muestras-mediana) <= self.tolerancia).all(axis=1)
        if estables.mean() < .8 or estables.sum() < self.minimo_muestras:
            return ResultadoPunto(None, 'Señal inestable: fija la mirada y mantén la postura.')
        tiempos = np.asarray(self.tiempos)[estables]
        # Evita aceptar una ráfaga de muestras concentrada en un solo instante.
        intervalos = np.floor(tiempos / (self.duracion/6)).astype(int)
        if np.ptp(tiempos) < 1.4 or len(np.unique(intervalos)) < 5:
            return ResultadoPunto(None, 'Las muestras estables no cubren suficiente tiempo.')
        seleccion = muestras[estables]
        primera = seleccion[tiempos < self.duracion/3]
        ultima = seleccion[tiempos >= 2*self.duracion/3]
        if not len(primera) or not len(ultima) or (
                np.abs(np.median(ultima, axis=0)-np.median(primera, axis=0)) > self.tolerancia).any():
            return ResultadoPunto(None, 'La mirada cambió durante la captura: repite la fijación.')
        return ResultadoPunto(np.median(seleccion, axis=0), 'Captura estable aceptada.')
