"""Adaptador web para la señal binocular de MediaPipe y el clasificador RMN.

No abre cámaras en el servidor ni mueve el mouse. El navegador entrega un JPEG
efímero; únicamente se guardan los resultados numéricos.
"""
import threading
import numpy as np

from mirada.iris import obtener_iris


class Vision:
    def __init__(self, weights):
        self.weights = weights
        self.lock = threading.Lock()
        self.detector = None
        self.model = None

    def analyze(self, jpeg, emotions=False):
        import cv2
        import mediapipe as mp
        with self.lock:
            if self.detector is None:
                # Independiente por imagen: no comparte tracking entre personas/sesiones.
                self.detector = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True, refine_landmarks=True, max_num_faces=2)
            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is None or max(frame.shape[:2]) > 1280:
                raise ValueError('Imagen de cámara inválida o demasiado grande.')
            frame = cv2.flip(frame, 1)  # misma orientación que main.py
            faces = self.detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).multi_face_landmarks or []
            result = dict(iris=None, emotion=None, confidence=None, reason='')
            if len(faces) != 1:
                result['reason'] = 'sin_rostro' if not faces else 'varios_rostros'
                return result
            p = faces[0].landmark
            h, w = frame.shape[:2]
            iris = obtener_iris(faces, (w, h))
            if iris is None:
                result['reason'] = 'iris_invalido'
            else:
                result['iris'] = iris.tolist()
            if emotions:
                from emociones.rmn_detector import ClasificadorRMN, CLASES
                if self.model is None:
                    self.model = ClasificadorRMN(self.weights)
                points = np.array([(v.x*w, v.y*h) for v in p[:468]])
                lo, hi = points.min(0), points.max(0)
                margin = .1 * max(hi-lo)
                x1, y1 = np.maximum(0, lo-margin).astype(int)
                x2, y2 = np.minimum([w, h], hi+margin).astype(int)
                if min(x2-x1, y2-y1) >= 60:
                    scores = self.model.predecir(frame[y1:y2, x1:x2])
                    i = int(scores.argmax())
                    result.update(emotion=CLASES[i], confidence=float(scores[i]))
            return result
