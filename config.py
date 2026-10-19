"""Parámetros de esta primera versión. Reinicia el programa al modificarlos."""

from pathlib import Path

RUTA_MODELO = Path(__file__).resolve().parent / "modelos" / "face_landmarker.task"

INDICE_CAMARA = 0
ANCHO_CAPTURA = 640
ALTO_CAPTURA = 480
MAX_ROSTROS = 5

CONFIANZA_DETECCION = 0.5
CONFIANZA_PRESENCIA = 0.5
CONFIANZA_SEGUIMIENTO = 0.5

MOSTRAR_LANDMARKS = True  # También se cambia con M durante la ejecución.
MOSTRAR_RECTANGULOS = True
NOMBRE_VENTANA = "Neuro IA Marketing - Prototipo facial"
