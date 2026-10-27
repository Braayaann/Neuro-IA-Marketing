"""Entrada del módulo independiente. Ejecutar: python main.py"""
import argparse
from collections import Counter
from pathlib import Path
import queue
import time

RAIZ = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Seguimiento ocular experimental con calibración local')
    parser.add_argument('--camara', type=int, default=0)
    parser.add_argument('--puerto', type=int, default=8765)
    parser.add_argument('--sin-abrir', action='store_true', help='No abrir automáticamente el navegador')
    parser.add_argument('--escritorio', action='store_true', help='Interfaz anterior, conservada para comparación')
    parser.add_argument('--imagen', type=Path)
    parser.add_argument('--modelo', type=Path, default=RAIZ/'modelos'/'face_landmarker.task')
    parser.add_argument('--resultados', type=Path, default=RAIZ/'resultados')
    parser.add_argument('--diagnostico', action='store_true', help='Comprueba dependencias y modelo sin abrir cámara')
    parser.add_argument('--prueba-camara', type=int, metavar='SEGUNDOS', help='Captura acotada, sin guardar imágenes')
    args = parser.parse_args()
    if args.diagnostico:
        import cv2
        import mediapipe as mp
        import numpy as np
        import sklearn
        import tkinter
        from deteccion.detector_ocular import DetectorOcular
        detector = DetectorOcular(args.modelo)
        try:
            obs = detector.detectar(np.zeros((480, 640, 3), np.uint8), time.perf_counter())
            assert obs.motivo == 'sin_rostro'
        finally:
            detector.close()
        print(f'OK: OpenCV {cv2.__version__}, MediaPipe {mp.__version__}, sklearn {sklearn.__version__}, Tk {tkinter.TkVersion}')
        print('Modelo cargado; imagen vacía rechazada. Esto NO valida precisión ocular.')
        return
    if args.prueba_camara is not None:
        from deteccion.detector_ocular import Camara
        camara = Camara(args.camara, args.modelo)
        camara.start()
        motivos = Counter()
        ms = []
        fin = time.perf_counter()+max(1, min(args.prueba_camara, 60))
        try:
            while time.perf_counter() < fin and camara.is_alive():
                try:
                    _, _, obs, deteccion, _ = camara.cola.get(timeout=.2)
                    motivos[obs.motivo] += 1
                    ms.append(deteccion)
                except queue.Empty:
                    pass
        finally:
            camara.detener()
            camara.join(timeout=5)
        print(dict(motivos))
        if camara.error:
            raise SystemExit(camara.error)
        if camara.is_alive():
            raise SystemExit('El controlador de cámara no terminó de cerrar en cinco segundos.')
        if not ms:
            raise SystemExit('No se recibieron imágenes. Prueba otro índice o cierra otras aplicaciones.')
        print(f'{len(ms)} frames; detección media {sum(ms)/len(ms):.1f} ms. Sin fotos guardadas.')
        print('Solo comprueba captura/detección; NO mide precisión de mirada.')
        return
    if not args.escritorio:
        from interfaz.servidor import ejecutar
        ejecutar(args.modelo, args.resultados, args.camara, args.puerto, not args.sin_abrir)
        return
    import tkinter as tk
    from interfaz.app import Aplicacion
    # Coordenadas físicas estables en Windows con escalado DPI.
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    Aplicacion(root, args.modelo, args.resultados, args.camara, args.imagen)
    root.mainloop()


if __name__ == '__main__':
    main()
