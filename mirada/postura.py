"""Indicador aproximado de postura; no compensa ni estima la mirada."""
import cv2
import numpy as np

INDICES = (1, 152, 33, 263, 61, 291)
# Modelo genérico: x derecha, y abajo, z hacia el interior de la cara.
MODELO = np.array([(0, 0, 0), (0, 63, 12), (-43, -32, 26),
                   (43, -32, 26), (-28, 28, 24), (28, 28, 24)], dtype=float)


def obtener_postura(rostros, tamano):
    """Devuelve [pitch, yaw, roll, centro_x, centro_y, ancho_relativo].

    Ángulos en grados, centro y ancho en unidades de imagen. Intrínsecos
    aproximados y rostro genérico: no son mediciones físicas calibradas.
    """
    if len(rostros) != 1 or len(rostros[0].landmark) < 468:
        return None
    ancho, alto = tamano
    if min(ancho, alto) <= 0:
        return None
    puntos = np.array([(p.x, p.y) for p in rostros[0].landmark[:468]])
    if not np.isfinite(puntos).all():
        return None
    imagen = puntos[list(INDICES)] * [ancho, alto]
    if np.linalg.matrix_rank(imagen-imagen.mean(axis=0)) < 2:
        return None
    focal = float(max(ancho, alto))
    camara = np.array([[focal, 0, ancho/2], [0, focal, alto/2], [0, 0, 1.]])
    try:
        ok, rotacion, traslacion = cv2.solvePnP(MODELO, imagen, camara, None, flags=cv2.SOLVEPNP_SQPNP)
        if not ok or not np.isfinite(rotacion).all() or not np.isfinite(traslacion).all() or traslacion[2, 0] <= 0:
            return None
        matriz, _ = cv2.Rodrigues(rotacion)
        reproyectada, _ = cv2.projectPoints(MODELO, rotacion, traslacion, camara, None)
        error = np.linalg.norm(reproyectada.reshape(-1, 2)-imagen, axis=1)
        if np.sqrt(np.mean(error**2)) > .10*np.linalg.norm(imagen[2]-imagen[3]):
            return None
        angulos = np.asarray(cv2.RQDecomp3x3(matriz)[0])
    except cv2.error:
        return None
    minimo, maximo = puntos.min(axis=0), puntos.max(axis=0)
    if maximo[0]-minimo[0] < 1e-6 or not np.isfinite(angulos).all():
        return None
    return np.r_[angulos, (minimo+maximo)/2, maximo[0]-minimo[0]]


def comparar_postura(actual, referencia):
    if actual is None:
        return 'SIN POSTURA', None
    if referencia is None:
        return 'SIN REFERENCIA', None
    angulos = (actual[:3]-referencia[:3]+180) % 360 - 180
    desplazamiento = (actual[3:5]-referencia[3:5]) / referencia[5]
    escala = actual[5]/referencia[5]-1
    cambio = bool((np.abs(angulos) > 8).any() or (np.abs(desplazamiento) > .15).any() or abs(escala) > .15)
    return ('POSTURA CAMBIO' if cambio else 'POSTURA SIMILAR'), np.r_[angulos, desplazamiento, escala]
