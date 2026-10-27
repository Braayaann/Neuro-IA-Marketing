"""Parámetros del prototipo. Son criterios prácticos, no precisión certificada."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    ancho_camara: int = 640
    alto_camara: int = 480
    confianza_deteccion: float = 0.5
    confianza_presencia: float = 0.5
    confianza_seguimiento: float = 0.5
    ancho_min_ojo_px: float = 16.0
    apertura_min: float = 0.12  # Distancia párpados / ancho del ojo.
    angulo_max: float = 35.0
    espera_punto_s: float = 0.8
    captura_punto_s: float = 2.5
    muestras_min_punto: int = 15
    cobertura_min_punto_s: float = 1.2
    suavizado_tau_s: float = 0.09
    hueco_max_s: float = 0.25  # No atribuir tiempo a intervalos sin observaciones.
    sigma_calor_rel: float = 0.025
    resolucion_calor_max: int = 640
    error_validacion_max: float = 0.10  # Fracción de la diagonal original.
    acierto_region_min: float = 0.60
    cobertura_validacion_min: float = 0.60


CALIBRACION = [(x, y) for y in (0.06, 0.5, 0.94) for x in (0.06, 0.5, 0.94)]
VALIDACION = [(0.25, 0.25), (0.75, 0.25), (0.55, 0.55), (0.25, 0.75), (0.75, 0.75)]
VALIDACION_WEB = [(x, y) for y in (0.16, 0.55, 0.86) for x in (0.22, 0.52, 0.78)]
