"""Proyeccion aproximada del rayo a pantalla; no se ajusta a cada espectador."""
from math import cos, sin, tan, radians, isfinite


def proyectar(horizontal, vertical, ojo_px, captura_px, config):
    valores = [horizontal, vertical, *ojo_px, *captura_px, *config['pantalla_cm'],
               config['distancia_cm'], config['fov_horizontal_grados'], config['camara_sobre_pantalla_cm']]
    if not all(isfinite(v) for v in valores):
        return None
    ancho_px, alto_px = captura_px
    ancho_cm, alto_cm = config['pantalla_cm']
    distancia = config['distancia_cm']
    fov = config['fov_horizontal_grados']
    if min(ancho_px, alto_px, ancho_cm, alto_cm, distancia) <= 0 or not 1 < fov < 179:
        return None
    focal = ancho_px / (2 * tan(radians(fov) / 2))
    origen_x = (ojo_px[0] - ancho_px / 2) * distancia / focal
    origen_y = (ojo_px[1] - alto_px / 2) * distancia / focal
    # Convencion de la flecha oficial: primer angulo horizontal, segundo vertical.
    dx = -sin(horizontal) * cos(vertical)
    dy = -sin(vertical)
    dz = -cos(horizontal) * cos(vertical)
    if dz >= -1e-6:
        return None
    recorrido = distancia / -dz
    x = origen_x + recorrido * dx
    y = origen_y + recorrido * dy
    return x / ancho_cm + 0.5, (y - config['camara_sobre_pantalla_cm']) / alto_cm


def region(punto, banda=0.04):
    if punto is None or not all(isfinite(v) for v in punto):
        return 'INDETERMINADA'
    x, y = punto
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return 'FUERA'
    if abs(x - 0.5) <= banda:
        return 'INDETERMINADA'
    return 'A' if x < 0.5 else 'B'
