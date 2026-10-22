"""Recorte cuadrado sobre el fotograma original, nunca sobre el video dibujado."""

from dataclasses import dataclass
import math
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np


@dataclass
class RecorteFacial:
    imagen: object = None
    caja: tuple = None  # x1, y1, x2, y2; extremos superiores exclusivos.
    motivo: str = ''


def extraer_rostro(imagen, landmarks, margen=0.10, minimo=60, fraccion_visible=0.85):
    alto, ancho = imagen.shape[:2]
    if len(landmarks) < 468:
        return RecorteFacial(motivo='landmarks incompletos')
    # x/y normalizadas se multiplican por la resolución ORIGINAL, aunque MediaPipe
    # haya recibido una versión reducida. No recortar coordenadas antes de validarlas.
    puntos = np.array([(p.x * ancho, p.y * alto) for p in landmarks], dtype=np.float64)
    if not np.isfinite(puntos).all():
        return RecorteFacial(motivo='coordenadas invalidas')
    esenciales = puntos[[33, 263, 1, 61, 291]]  # ojos, nariz y extremos de la boca
    if np.any(esenciales < 0) or np.any(esenciales >= [ancho, alto]):
        return RecorteFacial(motivo='rostro parcial')
    inferior = puntos.min(axis=0)
    superior = puntos.max(axis=0)
    extension = superior - inferior
    if min(extension) < minimo:
        return RecorteFacial(motivo='rostro pequeno')
    visible = np.maximum(0, np.minimum(superior, [ancho, alto]) - np.maximum(inferior, 0))
    if np.prod(visible) / np.prod(extension) < fraccion_visible:
        return RecorteFacial(motivo='rostro parcial')
    lado = math.ceil(max(extension) * (1 + 2 * margen))
    if lado > min(ancho, alto):
        return RecorteFacial(motivo='sin espacio para recorte')
    centro = (inferior + superior) / 2
    origen = np.floor(centro - lado / 2).astype(int)
    # Desplazar el cuadrado en los bordes evita estirar la cara o añadir píxeles
    # artificiales. Allí el margen puede ser asimétrico; no reconstruye partes ocultas.
    x1 = int(np.clip(origen[0], 0, ancho - lado))
    y1 = int(np.clip(origen[1], 0, alto - lado))
    caja = (x1, y1, x1 + lado, y1 + lado)
    return RecorteFacial(imagen=imagen[y1:y1 + lado, x1:x1 + lado], caja=caja)


def preparar_rostros(imagen, rostros, **opciones):
    resultados = [extraer_rostro(imagen, puntos, **opciones) for puntos in rostros]
    indices = [i for i, resultado in enumerate(resultados) if resultado.imagen is not None]
    # Mantener los índices evita desplazar etiquetas al descartar un rostro inválido.
    return resultados, indices, [resultados[i].imagen for i in indices]


class GuardadorRecortes:
    def __init__(self, activo, carpeta, maximo=20, intervalo=60):
        self.activo = activo
        self.carpeta = Path(carpeta) / uuid4().hex[:12]
        self.maximo = maximo
        self.intervalo = intervalo
        self.guardados = 0

    def guardar(self, fotograma, recortes, indices):
        if not self.activo or fotograma % self.intervalo or self.guardados >= self.maximo:
            return
        from emociones.rmn_detector import preprocesar
        self.carpeta.mkdir(parents=True, exist_ok=True)
        for indice in indices:
            if self.guardados >= self.maximo:
                break
            rostro = recortes[indice].imagen
            prefijo = self.carpeta / f'frame_{fotograma:06d}_rostro_{indice + 1}'
            # PNG conserva el BGR recortado; NPY conserva exactamente la entrada NCHW.
            if not cv2.imwrite(str(prefijo) + '.png', rostro):
                raise OSError(f'No se pudo guardar el recorte: {prefijo}')
            np.save(str(prefijo) + '_tensor.npy', preprocesar(rostro))
            self.guardados += 1
