"""Predicción calibrada, filtros geométricos y suavizado dependiente del tiempo."""
import numpy as np
from config import Config


class EstimadorMirada:
    def __init__(self, calibrador, cfg=Config()):
        self.calibrador, self.cfg = calibrador, cfg
        self.reset()

    def reset(self):
        self.ultimo_t = None
        self.suave = None

    def estimar(self, obs, instante):
        motivo = obs.motivo if not obs.valida else self.calibrador.motivo_fuera_rango(obs)
        if motivo:
            self.reset()
            return None, None, motivo
        raw = self.calibrador.predecir(obs.caracteristicas)
        if not np.isfinite(raw).all() or ((raw < 0) | (raw > 1)).any():
            self.reset()
            return raw, None, 'fuera_publicidad'
        dt = instante-self.ultimo_t if self.ultimo_t is not None else None
        if dt is None or dt <= 0 or dt > self.cfg.hueco_max_s:
            self.suave = raw.copy()
        else:
            alpha = 1-np.exp(-dt/self.cfg.suavizado_tau_s)
            self.suave += alpha*(raw-self.suave)
        self.ultimo_t = instante
        return raw, self.suave.copy(), 'valida'
