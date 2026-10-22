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

# RMN se carga una vez. Si faltan pesos, usa --solo-mediapipe para probar la base.
BASE = Path(__file__).resolve().parent
RMN_ACTIVO = True
RUTA_RMN = BASE / 'modelos' / 'rmn_benchmark' / 'resmasking_net.pth'
DISPOSITIVO_RMN = 'auto'  # auto, cpu o cuda; CUDA requiere una instalación compatible.
HILOS_RMN = 4
TAMANO_LOTE_RMN = 1  # 1 reproduce la ejecución original; compara 2/3 antes de cambiar.

MARGEN_ROSTRO = 0.10  # Por lado, respecto al mayor tamaño de los landmarks.
MINIMO_ROSTRO = 60  # Píxeles en la menor dimensión de landmarks, antes del margen.
FRACCION_VISIBLE = 0.85
ANCHO_PROCESAMIENTO = 0  # 0: original. Otro valor reduce solo la entrada MediaPipe.

GUARDAR_RECORTES = False  # Solo depuración explícita; no se guarda video.
CARPETA_RECORTES = BASE / 'depuracion'
MAX_RECORTES = 20  # Máximo por ejecución; archivos permanecen hasta borrarlos.
INTERVALO_RECORTES = 60  # Cada cuántos fotogramas se permite guardar.
