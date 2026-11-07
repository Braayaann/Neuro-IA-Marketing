"""Filtro One Euro para la señal binocular antes de convertirla a pantalla.

Algoritmo: Casiez, Roussel y Vogel (2012), https://gery.casiez.net/1euro/.
"""
import numpy as np


class SuavizadoMirada:
    """Atenúa el ruido lento y aumenta la respuesta al crecer la velocidad.

    Los tiempos se expresan en segundos y los cortes en Hz. beta depende de
    las unidades: aquí se utilizan posiciones del iris relativas al ojo.
    No rechaza saltos aislados ni corrige el error de calibración.
    """

    def __init__(self, corte_minimo=1., beta=10., corte_velocidad=1., pausa_maxima=.5):
        parametros = np.array([corte_minimo, beta, corte_velocidad, pausa_maxima])
        if not np.isfinite(parametros).all() or min(corte_minimo, corte_velocidad, pausa_maxima) <= 0 or beta < 0:
            raise ValueError('Los cortes y la pausa deben ser positivos; beta no puede ser negativo.')
        self.corte_minimo = corte_minimo
        self.beta = beta
        self.corte_velocidad = corte_velocidad
        self.pausa_maxima = pausa_maxima
        self.reiniciar()

    def reiniciar(self):
        self.tiempo = None
        self.anterior = None
        self.filtrada = None
        self.velocidad = np.zeros(2)

    @staticmethod
    def _alpha(corte, dt):
        return 1. / (1. + 1. / (2. * np.pi * corte * dt))

    def actualizar(self, muestra, tiempo):
        if muestra is None:
            self.reiniciar()
            return None
        muestra = np.asarray(muestra, dtype=float)
        if muestra.shape != (2,) or not np.isfinite(muestra).all() or not np.isfinite(tiempo):
            self.reiniciar()
            return None
        dt = None if self.tiempo is None else tiempo - self.tiempo
        if dt is None or dt <= 0 or dt > self.pausa_maxima:
            self.reiniciar()
            self.filtrada = muestra.copy()
        else:
            velocidad = (muestra - self.anterior) / dt
            alpha_velocidad = self._alpha(self.corte_velocidad, dt)
            self.velocidad += alpha_velocidad * (velocidad - self.velocidad)
            corte = self.corte_minimo + self.beta * np.abs(self.velocidad)
            alpha = self._alpha(corte, dt)
            self.filtrada += alpha * (muestra - self.filtrada)
        self.anterior = muestra.copy()
        self.tiempo = tiempo
        return self.filtrada.copy()
