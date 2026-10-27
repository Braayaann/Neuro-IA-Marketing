"""MediaPipe entrega geometría facial; aquí todavía NO se calcula la mirada."""
from dataclasses import dataclass
import queue
import threading
import time

import cv2
import mediapipe as mp
import numpy as np

from config import Config
from deteccion.pose import orientacion

# Centros 468/473; los otros cuatro puntos de cada iris son su contorno.
OJOS = ((33, 133, 159, 145, 468), (362, 263, 386, 374, 473))
CONTORNOS = ((33, 160, 158, 133, 153, 144), (362, 385, 387, 263, 373, 380))


@dataclass
class Observacion:
    valida: bool
    motivo: str
    caracteristicas: np.ndarray | None = None
    contexto: np.ndarray | None = None  # centro x/y, escala facial, yaw/pitch/roll.
    aperturas: tuple = ()
    puntos: np.ndarray | None = None


def extraer(puntos, ancho, alto, matriz, cfg=Config()):
    """Proyecta cada iris en ejes del ojo y normaliza por su ancho.

    Esto reduce dependencia de posición, escala y giro en el plano de la cámara.
    La coordenada vertical NO se divide por la apertura, que cambia al parpadear.
    """
    p = np.asarray(puntos, dtype=float)
    if p.shape != (478, 2) or not np.isfinite(p).all():
        return Observacion(False, 'landmarks_incompletos')
    indices = sorted({i for ojo in OJOS for i in ojo})
    if ((p[indices] < 0) | (p[indices] > 1)).any():
        return Observacion(False, 'ojos_fuera_camara')
    px = p * [ancho, alto]
    features, aperturas, parpados = [], [], []
    for a, b, sup, inf, iris in OJOS:
        eje = px[b] - px[a]
        ancho_ojo = np.linalg.norm(eje)
        if ancho_ojo < cfg.ancho_min_ojo_px:
            return Observacion(False, 'rostro_lejano')
        eje /= ancho_ojo
        vertical = np.array([-eje[1], eje[0]])
        apertura = abs(np.dot(px[inf] - px[sup], vertical)) / ancho_ojo
        aperturas.append(float(apertura))
        relativo = (px[iris] - (px[a] + px[b]) / 2) / ancho_ojo
        features.extend([np.dot(relativo, eje), np.dot(relativo, vertical)])
        # Otra referencia vertical: centro de párpados; no dividir por apertura.
        parpados.append(float(np.dot(px[iris]-(px[sup]+px[inf])/2, vertical)/ancho_ojo))
    try:
        pose = orientacion(matriz)
    except (ValueError, np.linalg.LinAlgError):
        return Observacion(False, 'pose_no_disponible')
    centro = (p[33] + p[263]) / 2
    escala = np.linalg.norm(px[263] - px[33]) / ancho
    # La selección de variables se evalúa por grupos; la pose no se añade a ciegas.
    features.extend(parpados + aperturas + (pose/35).tolist())
    motivo = ('parpadeo_ojo_cerrado' if min(aperturas) < cfg.apertura_min else
              'cabeza_muy_girada' if np.abs(pose).max() > cfg.angulo_max else 'valida')
    # Conservar geometría de rechazos para diagnóstico; nunca usarlos para ajustar.
    return Observacion(motivo == 'valida', motivo, np.asarray(features),
                       np.r_[centro, escala, pose], tuple(aperturas), p)


class DetectorOcular:
    def __init__(self, modelo, cfg=Config()):
        self.cfg = cfg
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(modelo)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=2,  # Solo para rechazar escenas con más de una persona.
            min_face_detection_confidence=cfg.confianza_deteccion,
            min_face_presence_confidence=cfg.confianza_presencia,
            min_tracking_confidence=cfg.confianza_seguimiento,
            output_facial_transformation_matrixes=True)
        self.detector = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self.ultimo_ms = -1

    def detectar(self, frame, instante):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ms = max(self.ultimo_ms + 1, int(instante * 1000))
        self.ultimo_ms = ms
        resultado = self.detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)
        if len(resultado.face_landmarks) != 1:
            return Observacion(False, 'sin_rostro' if not resultado.face_landmarks else 'varias_personas')
        puntos = np.array([(p.x, p.y) for p in resultado.face_landmarks[0]])
        matriz = resultado.facial_transformation_matrixes[0] if resultado.facial_transformation_matrixes else None
        return extraer(puntos, frame.shape[1], frame.shape[0], matriz, self.cfg)

    def close(self):
        self.detector.close()


def dibujar_ojos(frame, observacion):
    salida = frame.copy()
    if observacion.puntos is None:
        return salida
    p = (observacion.puntos * [frame.shape[1], frame.shape[0]]).astype(int)
    for contorno in CONTORNOS:
        cv2.polylines(salida, [p[list(contorno)]], True, (0, 220, 0), 1)
    for centro in (468, 473):
        cv2.polylines(salida, [p[list(range(centro + 1, centro + 5))]], True, (0, 200, 255), 1)
        cv2.circle(salida, tuple(p[centro]), 2, (0, 0, 255), -1)
    return salida


class Camara(threading.Thread):
    """Un único detector por apertura. Cola de un frame: no acumula retraso."""
    def __init__(self, indice, modelo, cfg=Config()):
        super().__init__(daemon=True)
        self.indice, self.modelo, self.cfg = indice, modelo, cfg
        self.stop_event = threading.Event()
        self.cola = queue.Queue(maxsize=1)
        self.error = None

    def run(self):
        camara = detector = None
        try:
            camara = cv2.VideoCapture(self.indice, cv2.CAP_DSHOW)
            if not camara.isOpened():
                camara.release()
                camara = cv2.VideoCapture(self.indice)
            if not camara.isOpened():
                raise RuntimeError(f'No se pudo abrir la cámara {self.indice}')
            camara.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.ancho_camara)
            camara.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.alto_camara)
            detector = DetectorOcular(self.modelo, self.cfg)
            anterior = time.perf_counter()
            while not self.stop_event.is_set():
                ok, frame = camara.read()
                instante = time.perf_counter()
                if not ok:
                    raise RuntimeError('La cámara dejó de entregar imágenes')
                frame = cv2.flip(frame, 1)
                inicio = time.perf_counter()
                obs = detector.detectar(frame, instante)
                paquete = (instante, frame, obs, (time.perf_counter()-inicio)*1000,
                           1/max(instante-anterior, 1e-6))
                anterior = instante
                if self.cola.full():
                    try:
                        self.cola.get_nowait()
                    except queue.Empty:
                        pass
                self.cola.put_nowait(paquete)
        except Exception as exc:
            self.error = str(exc)
        finally:
            if detector is not None:
                detector.close()
            if camara is not None:
                camara.release()

    def detener(self):
        self.stop_event.set()
