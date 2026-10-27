"""Conversión de coordenadas del anuncio, independiente del dispositivo de mirada."""


def encajar(ancho, alto, disponible_w, disponible_h):
    escala = min(max(1, disponible_w)/ancho, max(1, disponible_h)/alto)
    w, h = max(1, round(ancho*escala)), max(1, round(alto*escala))
    return ((disponible_w-w)//2, (disponible_h-h)//2, w, h)


def a_canvas(punto, rectangulo):
    x, y, w, h = rectangulo
    return x+punto[0]*(w-1), y+punto[1]*(h-1)


def cambio_geometria(antes, despues, tolerancia=2):
    return antes is not None and any(abs(a-b) > tolerancia for a, b in zip(antes, despues))
