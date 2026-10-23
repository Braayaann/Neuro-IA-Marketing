"""MediaPipe y RMN sobre frames compartidos; no abre ni modifica la camara."""
import numpy as np
import config
from . import aplicacion
from .rmn_detector import ClasificadorRMN, CLASES
from utilidades.procesamiento_imagen import preparar_rostros


class SesionEmociones:
    def __init__(self):
        self.detector = None
        self.clasificador = None
        self.rostros = []
        self.etiquetas = []
        self.recortes = []
        self.ultimo_timestamp = -1
        self.etiqueta = 'Sin rostro'

    def abrir(self):
        aplicacion.validar_configuracion()
        self.clasificador = ClasificadorRMN(config.RUTA_RMN, config.DISPOSITIVO_RMN,
                                           config.HILOS_RMN, config.TAMANO_LOTE_RMN)
        self.detector = aplicacion.crear_detector()
        return self

    def procesar(self, frame, timestamp_ms):
        timestamp_ms = max(int(timestamp_ms), self.ultimo_timestamp + 1)
        self.ultimo_timestamp = timestamp_ms
        resultado = aplicacion.detectar_rostros(self.detector, frame, timestamp_ms)
        self.rostros = resultado.face_landmarks
        self.etiquetas, self.recortes = [], []
        # La comparacion A/B inicial corresponde a una sola persona.
        if len(self.rostros) != 1:
            self.etiqueta = 'Sin rostro' if not self.rostros else 'Varias personas'
            return self.etiqueta
        self.recortes, indices, imagenes = preparar_rostros(
            frame, self.rostros, margen=config.MARGEN_ROSTRO,
            minimo=config.MINIMO_ROSTRO, fraccion_visible=config.FRACCION_VISIBLE)
        self.etiquetas = ['Rostro no clasificable']
        if imagenes:
            scores = self.clasificador.inferir(self.clasificador.preparar(imagenes))
            for indice, probabilidades in zip(indices, scores):
                clase = int(np.argmax(probabilidades))
                self.etiquetas[indice] = f'{CLASES[clase]} {probabilidades[clase]:.0%}'
        self.etiqueta = self.etiquetas[0]
        return self.etiqueta

    def vista(self, frame):
        imagen = frame.copy()
        if len(self.rostros) == 1:
            aplicacion.dibujar_rostros(imagen, self.rostros, config.MOSTRAR_LANDMARKS,
                                      self.etiquetas, self.recortes)
        return imagen

    def cerrar(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None
