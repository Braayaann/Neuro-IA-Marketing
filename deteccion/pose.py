"""Orientación geométrica de la matriz facial de MediaPipe; no es otro modelo IA.

Convención algebraica: R = Rz(roll) @ Ry(yaw) @ Rx(pitch), en grados.
Los signos se refieren al marco de la matriz, no a la izquierda anatómica.
La cámara se procesa en espejo. Se requiere comprobar los gestos con el usuario.
"""
import cv2
import numpy as np


def rotacion_desde_angulos(yaw, pitch, roll):
    """Utilidad geométrica para comprobaciones con rotaciones conocidas."""
    y, p, r = np.radians([yaw, pitch, roll])
    rx = cv2.Rodrigues(np.array([p, 0., 0.]))[0]
    ry = cv2.Rodrigues(np.array([0., y, 0.]))[0]
    rz = cv2.Rodrigues(np.array([0., 0., r]))[0]
    return rz @ ry @ rx


def orientacion(matriz):
    """Elimina escala de la transformación y devuelve yaw, pitch, roll.

    Se mantiene la descomposición de la versión anterior. No se añade solvePnP
    con una focal inventada: la matriz facial ya ofrece una orientación aproximada.
    """
    if matriz is None or np.asarray(matriz).shape != (4, 4):
        raise ValueError('No hay transformación facial válida')
    r = np.asarray(matriz, dtype=float)[:3, :3]
    if not np.isfinite(r).all():
        raise ValueError('Transformación no finita')
    u, valores, vt = np.linalg.svd(r)
    if valores.min() < 1e-8 or np.linalg.det(r) <= 0:
        raise ValueError('Transformación degenerada o reflejada')
    r = u @ vt
    # Comprobación independiente del eje de rotación mediante OpenCV.
    rv = cv2.Rodrigues(r)[0]
    if not np.isfinite(rv).all():
        raise ValueError('Rotación no válida')
    pitch = np.arctan2(r[2, 1], r[2, 2])
    yaw = np.arctan2(-r[2, 0], np.hypot(r[0, 0], r[1, 0]))
    roll = np.arctan2(r[1, 0], r[0, 0])
    return np.degrees([yaw, pitch, roll])
