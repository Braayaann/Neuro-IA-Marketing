"""Cámara y landmarks faciales con la API Tasks de MediaPipe."""

import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import config


def validar_configuracion():
    """Detecta errores de configuración antes de abrir la cámara."""
    if not config.RUTA_MODELO.is_file():
        raise FileNotFoundError(
            f"No se encontró el modelo: {config.RUTA_MODELO}\n"
            "Consulta el README para descargar face_landmarker.task."
        )
    for nombre in ("MAX_ROSTROS", "ANCHO_CAPTURA", "ALTO_CAPTURA"):
        valor = getattr(config, nombre)
        if type(valor) is not int or valor < 1:
            raise ValueError(f"{nombre} debe ser un entero mayor que cero.")
    if type(config.INDICE_CAMARA) is not int or config.INDICE_CAMARA < 0:
        raise ValueError("INDICE_CAMARA debe ser un entero mayor o igual que cero.")
    for nombre in (
        "CONFIANZA_DETECCION", "CONFIANZA_PRESENCIA", "CONFIANZA_SEGUIMIENTO"
    ):
        valor = getattr(config, nombre)
        if not isinstance(valor, (int, float)) or not 0 <= valor <= 1:
            raise ValueError(f"{nombre} debe estar entre 0 y 1.")


def crear_detector():
    """Carga el modelo en CPU; VIDEO permite aprovechar el seguimiento interno."""
    opciones = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(config.RUTA_MODELO)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=config.MAX_ROSTROS,
        min_face_detection_confidence=config.CONFIANZA_DETECCION,
        min_face_presence_confidence=config.CONFIANZA_PRESENCIA,
        min_tracking_confidence=config.CONFIANZA_SEGUIMIENTO,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )
    return vision.FaceLandmarker.create_from_options(opciones)


def abrir_camara():
    camara = cv2.VideoCapture(config.INDICE_CAMARA)
    if not camara.isOpened():
        camara.release()
        raise RuntimeError(
            f"No se pudo abrir la cámara {config.INDICE_CAMARA}. "
            "Revisa los permisos de Windows, cierra otras aplicaciones que la usen "
            "o cambia INDICE_CAMARA en config.py."
        )
    try:
        # La cámara puede entregar otra resolución si no admite la solicitada.
        camara.set(cv2.CAP_PROP_FRAME_WIDTH, config.ANCHO_CAPTURA)
        camara.set(cv2.CAP_PROP_FRAME_HEIGHT, config.ALTO_CAPTURA)
    except cv2.error:
        camara.release()
        raise
    return camara


def detectar_rostros(detector, fotograma_bgr, timestamp_ms):
    """Devuelve el resultado completo, incluidos los landmarks normalizados."""
    fotograma_rgb = cv2.cvtColor(fotograma_bgr, cv2.COLOR_BGR2RGB)
    imagen = mp.Image(image_format=mp.ImageFormat.SRGB, data=fotograma_rgb)
    return detector.detect_for_video(imagen, timestamp_ms)


def obtener_puntos_y_limites(landmarks, ancho, alto):
    """Convierte x/y a píxeles y devuelve puntos y límites (x1, y1, x2, y2)."""
    coordenadas = np.array([(p.x * ancho, p.y * alto) for p in landmarks])
    coordenadas[:, 0] = np.clip(coordenadas[:, 0], 0, ancho - 1)
    coordenadas[:, 1] = np.clip(coordenadas[:, 1], 0, alto - 1)
    puntos = coordenadas.astype(np.int32)
    x1, y1 = puntos.min(axis=0)
    x2, y2 = puntos.max(axis=0)
    return puntos, (int(x1), int(y1), int(x2), int(y2))


def escribir_texto(imagen, texto, posicion, color=(255, 255, 255)):
    # Un borde oscuro mantiene el texto legible sobre el video.
    cv2.putText(imagen, texto, posicion, cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(imagen, texto, posicion, cv2.FONT_HERSHEY_SIMPLEX,
                0.55, color, 1, cv2.LINE_AA)


def dibujar_rostros(imagen, rostros, mostrar_landmarks):
    alto, ancho = imagen.shape[:2]
    for numero, landmarks in enumerate(rostros, start=1):
        puntos, (x1, y1, x2, y2) = obtener_puntos_y_limites(landmarks, ancho, alto)
        if mostrar_landmarks:
            for indice, (x, y) in enumerate(puntos):
                # En este modelo, 468..477 corresponden a los iris.
                es_iris = indice >= 468
                color = (0, 200, 255) if es_iris else (80, 230, 80)
                cv2.circle(imagen, (int(x), int(y)), 2 if es_iris else 1, color, -1)
        if config.MOSTRAR_RECTANGULOS:
            cv2.rectangle(imagen, (x1, y1), (x2, y2), (255, 180, 40), 1)
        # Este número solo identifica la posición del rostro en el fotograma.
        escribir_texto(imagen, f"Rostro {numero}", (x1, max(18, y1 - 8)),
                       color=(255, 180, 40))


def mostrar_informacion(imagen, cantidad, fps, mostrar_landmarks):
    alto, ancho = imagen.shape[:2]
    escribir_texto(imagen, f"Rostros: {cantidad} | FPS: {fps:.1f}", (10, 24))
    escribir_texto(imagen, f"Resolucion: {ancho} x {alto}", (10, 48))
    estado = "ON" if mostrar_landmarks else "OFF"
    escribir_texto(imagen, f"Q: salir | M: landmarks {estado}", (10, 72))


def ejecutar_video(detector, camara):
    mostrar_landmarks = config.MOSTRAR_LANDMARKS
    inicio_ns = time.monotonic_ns()
    timestamp_anterior = -1
    inicio_medicion = time.perf_counter()
    fotogramas_medidos = 0
    fps = 0.0

    cv2.namedWindow(config.NOMBRE_VENTANA, cv2.WINDOW_NORMAL)
    print("Cámara iniciada. Enfoca la ventana de video: Q para salir, M para los puntos.")
    while True:
        recibido, fotograma = camara.read()
        if not recibido or fotograma is None or fotograma.size == 0:
            raise RuntimeError("No se pudo leer un fotograma. Comprueba la conexión de la cámara.")

        # VIDEO exige milisegundos estrictamente crecientes, incluso entre frames rápidos.
        transcurrido_ms = (time.monotonic_ns() - inicio_ns) // 1_000_000
        timestamp_ms = max(transcurrido_ms, timestamp_anterior + 1)
        timestamp_anterior = timestamp_ms
        resultado = detectar_rostros(detector, fotograma, timestamp_ms)

        # El original y los landmarks siguen disponibles para futuras etapas.
        visualizacion = fotograma.copy()
        dibujar_rostros(visualizacion, resultado.face_landmarks, mostrar_landmarks)

        fotogramas_medidos += 1
        ahora = time.perf_counter()
        intervalo = ahora - inicio_medicion
        if intervalo >= 0.5:
            fps = fotogramas_medidos / intervalo
            fotogramas_medidos = 0
            inicio_medicion = ahora
        mostrar_informacion(visualizacion, len(resultado.face_landmarks), fps,
                            mostrar_landmarks)
        cv2.imshow(config.NOMBRE_VENTANA, visualizacion)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), ord("Q")):
            break
        if tecla in (ord("m"), ord("M")):
            mostrar_landmarks = not mostrar_landmarks
        if cv2.getWindowProperty(config.NOMBRE_VENTANA, cv2.WND_PROP_VISIBLE) < 1:
            break


def main():
    camara = None
    try:
        validar_configuracion()
        # El contexto libera los recursos de MediaPipe también ante un error.
        with crear_detector() as detector:
            camara = abrir_camara()
            ejecutar_video(detector, camara)
        return 0
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")
        return 0
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        print(f"\nNo se pudo continuar: {error}")
        return 1
    finally:
        if camara is not None:
            camara.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
