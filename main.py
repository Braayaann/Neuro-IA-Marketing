"""Cámara, MediaPipe Tasks y expresiones RMN, sin almacenar imágenes por defecto."""

import argparse
from collections import deque
from pathlib import Path
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import config
from emociones.rmn_detector import CLASES, ClasificadorRMN
from utilidades.procesamiento_imagen import GuardadorRecortes, preparar_rostros
from utilidades.rendimiento import Mediciones


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
    for nombre in ('HILOS_RMN', 'TAMANO_LOTE_RMN', 'MINIMO_ROSTRO',
                   'MAX_RECORTES', 'INTERVALO_RECORTES'):
        if type(getattr(config, nombre)) is not int or getattr(config, nombre) < 1:
            raise ValueError(f'{nombre} debe ser un entero positivo.')
    if type(config.ANCHO_PROCESAMIENTO) is not int or config.ANCHO_PROCESAMIENTO < 0:
        raise ValueError('ANCHO_PROCESAMIENTO debe ser 0 o un entero positivo.')
    if not 0 <= config.MARGEN_ROSTRO <= 0.5:
        raise ValueError('MARGEN_ROSTRO debe estar entre 0 y 0.5.')
    if not 0 < config.FRACCION_VISIBLE <= 1:
        raise ValueError('FRACCION_VISIBLE debe estar entre 0 (exclusivo) y 1.')


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
    ancho_objetivo = config.ANCHO_PROCESAMIENTO
    alto, ancho = fotograma_bgr.shape[:2]
    if 0 < ancho_objetivo < ancho:
        fotograma_bgr = cv2.resize(fotograma_bgr,
                                  (ancho_objetivo, max(1, round(alto * ancho_objetivo / ancho))),
                                  interpolation=cv2.INTER_AREA)
    # Solo MediaPipe recibe RGB. RMN recorta el BGR original a resolución completa.
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


def dibujar_rostros(imagen, rostros, mostrar_landmarks, etiquetas=None, recortes=None):
    alto, ancho = imagen.shape[:2]
    ocupadas = []
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
        texto = f"{numero}: {etiquetas[numero - 1]}" if etiquetas else f"Rostro {numero}"
        if recortes and recortes[numero - 1].caja and config.MOSTRAR_RECTANGULOS:
            a, b, c, d = recortes[numero - 1].caja
            cv2.rectangle(imagen, (a, b), (c - 1, d - 1), (70, 220, 220), 1)
        ancho_texto = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0][0]
        tx = max(0, min(x1, ancho - ancho_texto - 2))
        candidatos = [max(18, y1 - 8), min(alto - 5, y2 + 22)]
        candidatos.extend(range(18, alto - 4, 22))
        ty = candidatos[0]
        for candidato in candidatos:
            caja = (tx, candidato - 17, tx + ancho_texto, candidato + 4)
            if all(caja[2] < a or caja[0] > c or caja[3] < b or caja[1] > d
                   for a, b, c, d in ocupadas):
                ty = candidato
                break
        ocupadas.append((tx, ty - 17, tx + ancho_texto, ty + 4))
        cv2.line(imagen, (x1, y1), (tx, ty), (255, 180, 40), 1)
        escribir_texto(imagen, texto, (tx, ty), color=(255, 180, 40))


def mostrar_informacion(imagen, cantidad, fps, mostrar_landmarks, activo, tiempos):
    alto, ancho = imagen.shape[:2]
    # Panel fuera del video para no cubrir los rostros con las métricas.
    imagen = cv2.copyMakeBorder(imagen, 0, 120, 0, max(0, 680 - ancho),
                                cv2.BORDER_CONSTANT, value=(25, 25, 25))
    escribir_texto(imagen, f"Rostros: {cantidad} | FPS: {fps:.1f} | {ancho} x {alto}", (10, alto + 22))
    estado = "ON" if mostrar_landmarks else "OFF"
    escribir_texto(imagen, f"Q: salir | M: puntos {estado} | R: RMN {'ON' if activo else 'OFF'}",
                   (10, alto + 44))
    escribir_texto(imagen, 'ms previos: ' + ' | '.join(
        f'{nombre} {tiempos.get(clave, 0):.1f}' for nombre, clave in
        [('Capt', 'captura'), ('MP', 'mediapipe'), ('Prep', 'preparacion'), ('RMN', 'rmn')]),
        (10, alto + 66))
    escribir_texto(imagen, f"Visual {tiempos.get('visualizacion', 0):.1f} | "
                   f"Ciclo {tiempos.get('ciclo', 0):.1f} | Expresion estimada, no emocion real",
                   (10, alto + 88))
    escribir_texto(imagen, 'Rectangulo azul: landmarks | amarillo: recorte RMN', (10, alto + 110))
    return imagen


def ejecutar_video(detector, camara, clasificador=None, max_fotogramas=0,
                   sin_ventana=False, mediciones=None):
    mostrar_landmarks = config.MOSTRAR_LANDMARKS
    activo = clasificador is not None
    mediciones = mediciones if mediciones is not None else Mediciones()
    guardador = GuardadorRecortes(config.GUARDAR_RECORTES, config.CARPETA_RECORTES,
                                 config.MAX_RECORTES, config.INTERVALO_RECORTES)
    inicio_ns = time.monotonic_ns()
    timestamp_anterior = -1
    ciclos = deque(maxlen=30)
    tiempos_anteriores = {}
    numero_frame = 0
    if not sin_ventana:
        cv2.namedWindow(config.NOMBRE_VENTANA, cv2.WINDOW_NORMAL)
    print('Cámara iniciada. Q: salir, M: puntos, R: alternar RMN si está cargado.')
    while True:
        inicio = time.perf_counter()
        recibido, fotograma = camara.read()
        if not recibido or fotograma is None or fotograma.size == 0:
            raise RuntimeError("No se pudo leer un fotograma. Comprueba la conexión de la cámara.")
        fin_captura = time.perf_counter()

        # VIDEO exige milisegundos estrictamente crecientes, incluso entre frames rápidos.
        transcurrido_ms = (time.monotonic_ns() - inicio_ns) // 1_000_000
        timestamp_ms = max(transcurrido_ms, timestamp_anterior + 1)
        timestamp_anterior = timestamp_ms
        resultado = detectar_rostros(detector, fotograma, timestamp_ms)
        fin_deteccion = time.perf_counter()
        etiquetas = ['RMN OFF'] * len(resultado.face_landmarks)
        recortes, indices, tensor = [], [], None
        if activo:
            recortes, indices, imagenes = preparar_rostros(
                fotograma, resultado.face_landmarks, margen=config.MARGEN_ROSTRO,
                minimo=config.MINIMO_ROSTRO, fraccion_visible=config.FRACCION_VISIBLE)
            etiquetas = [r.motivo or 'sin clasificar' for r in recortes]
            tensor = clasificador.preparar(imagenes)
            # Incluir transferencia CPU→GPU en preparación; delimitar CUDA realmente.
            clasificador.sincronizar()
        fin_preparacion = time.perf_counter()
        if activo and indices:
            scores = clasificador.inferir(tensor)
            clasificador.sincronizar()
            for indice, probabilidades in zip(indices, scores):
                clase = int(probabilidades.argmax())
                etiquetas[indice] = f'{CLASES[clase]} {probabilidades[clase]:.1%}'
        fin_rmn = time.perf_counter()
        guardador.guardar(numero_frame, recortes, indices)
        fin_depuracion = time.perf_counter()
        tecla = -1
        cerrada = False
        if not sin_ventana:
            # Dibujar después de inferir: ni landmarks ni textos entran a la red.
            visualizacion = fotograma.copy()
            dibujar_rostros(visualizacion, resultado.face_landmarks, mostrar_landmarks,
                            etiquetas, recortes)
            fps = 1000 * len(ciclos) / sum(ciclos) if ciclos else 0
            visualizacion = mostrar_informacion(visualizacion, len(resultado.face_landmarks),
                                                fps, mostrar_landmarks, activo, tiempos_anteriores)
            cv2.imshow(config.NOMBRE_VENTANA, visualizacion)
            tecla = cv2.waitKey(1) & 0xFF
            cerrada = cv2.getWindowProperty(config.NOMBRE_VENTANA, cv2.WND_PROP_VISIBLE) < 1
        fin = time.perf_counter()
        tiempos = dict(captura=(fin_captura - inicio) * 1000,
                       mediapipe=(fin_deteccion - fin_captura) * 1000,
                       preparacion=(fin_preparacion - fin_deteccion) * 1000,
                       rmn=(fin_rmn - fin_preparacion) * 1000,
                       depuracion=(fin_depuracion - fin_rmn) * 1000,
                       visualizacion=(fin - fin_depuracion) * 1000,
                       ciclo=(fin - inicio) * 1000)
        mediciones.agregar('integrado' if activo else 'mediapipe', len(etiquetas), len(indices), tiempos)
        ciclos.append(tiempos['ciclo'])
        tiempos_anteriores = tiempos
        numero_frame += 1
        if tecla in (ord("q"), ord("Q")):
            break
        if tecla in (ord("m"), ord("M")):
            mostrar_landmarks = not mostrar_landmarks
        if tecla in (ord('r'), ord('R')):
            if clasificador is not None:
                activo = not activo
            else:
                print('RMN no está cargado. Reinicia sin --solo-mediapipe y con los pesos originales.')
        if cerrada or (max_fotogramas and numero_frame >= max_fotogramas):
            break
    return mediciones


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solo-mediapipe', action='store_true')
    parser.add_argument('--max-fotogramas', type=int, default=0, help='0: hasta pulsar Q.')
    parser.add_argument('--sin-ventana', action='store_true', help='Prueba acotada sin dibujar.')
    parser.add_argument('--mediciones', type=Path, help='Guardar resumen numérico JSON, sin imágenes.')
    args = parser.parse_args(argv)
    if args.max_fotogramas < 0 or (args.sin_ventana and args.max_fotogramas == 0):
        parser.error('--sin-ventana requiere --max-fotogramas positivo.')
    camara = None
    mediciones = Mediciones()
    clasificador = None
    try:
        validar_configuracion()
        if config.RMN_ACTIVO and not args.solo_mediapipe:
            clasificador = ClasificadorRMN(config.RUTA_RMN, config.DISPOSITIVO_RMN,
                                           config.HILOS_RMN, config.TAMANO_LOTE_RMN)
            print(f'RMN cargado en {clasificador.dispositivo}; lote {clasificador.lote}.')
        # El contexto libera los recursos de MediaPipe también ante un error.
        with crear_detector() as detector:
            camara = abrir_camara()
            ejecutar_video(detector, camara, clasificador, args.max_fotogramas,
                           args.sin_ventana, mediciones)
        return 0
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, cv2.error) as error:
        print(f"\nNo se pudo continuar: {error}")
        return 1
    finally:
        if camara is not None:
            camara.release()
        cv2.destroyAllWindows()
        for fila in mediciones.resumen():
            print(f"{fila['modo']}: {fila['rostros']} rostros, {fila['clasificados']} clasificados, "
                  f"{fila['fotogramas']} frames, {fila['fps']:.2f} FPS; "
                  f"medias ms: {fila['media_ms']}")
        if args.mediciones:
            try:
                mediciones.guardar(args.mediciones, dict(
                    sin_ventana=args.sin_ventana, dispositivo=str(clasificador.dispositivo)
                    if clasificador else None, lote=config.TAMANO_LOTE_RMN,
                    ancho_mediapipe=config.ANCHO_PROCESAMIENTO,
                    nota='Incluye primer frame; excluye carga de modelos. No mide exactitud.'))
            except OSError as error:
                print(f'No se pudo guardar el resumen: {error}')


if __name__ == "__main__":
    raise SystemExit(main())
