"""Prueba real sin webcam: fondo vacío y 1/2/3 copias de un retrato local."""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

import config
from emociones.rmn_detector import preprocesar
from main import crear_detector, detectar_rostros, dibujar_rostros, mostrar_informacion
from utilidades.procesamiento_imagen import preparar_rostros


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('retrato', type=Path, help='Foto que contenga exactamente un rostro frontal.')
    parser.add_argument('--salida', type=Path)
    parser.add_argument('--vista', type=Path, help='Guardar explícitamente una vista de prueba, sin predicciones.')
    args = parser.parse_args()
    retrato = cv2.imread(str(args.retrato))
    if retrato is None:
        parser.error('No se pudo leer el retrato.')
    retrato = cv2.resize(retrato, (round(retrato.shape[1] * 400 / retrato.shape[0]), 400))
    filas = []
    for cantidad in range(4):
        # Resolución fija en los cuatro casos para no confundir tamaño con número de caras.
        imagen = np.zeros((400, 3 * retrato.shape[1], 3), np.uint8)
        for i in range(cantidad):
            imagen[:, i * retrato.shape[1]:(i + 1) * retrato.shape[1]] = retrato
        # Cada caso crea un detector independiente; no arrastra seguimiento de otra foto.
        with crear_detector() as detector:
            detectar_rostros(detector, imagen, 0)
            tiempos = []
            for numero in range(1, 11):
                inicio = time.perf_counter()
                resultado = detectar_rostros(detector, imagen, numero)
                tiempos.append((time.perf_counter() - inicio) * 1000)
        recortes, indices, crops = preparar_rostros(imagen, resultado.face_landmarks,
                                                   margen=config.MARGEN_ROSTRO, minimo=config.MINIMO_ROSTRO,
                                                   fraccion_visible=config.FRACCION_VISIBLE)
        fila = dict(esperados=cantidad, detectados=len(resultado.face_landmarks),
                    landmarks=[len(p) for p in resultado.face_landmarks], recortes_validos=len(indices),
                    tensor_shapes=[list(preprocesar(crop).shape) for crop in crops],
                    resolucion=list(imagen.shape[:2]), mediana_mediapipe_ms=float(np.median(tiempos)))
        filas.append(fila)
        if cantidad == 3 and args.vista:
            vista = imagen.copy()
            dibujar_rostros(vista, resultado.face_landmarks, True,
                            ['Sin pesos RMN'] * len(recortes), recortes)
            vista = mostrar_informacion(vista, len(recortes), 0, True, False, {})
            args.vista.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(args.vista), vista):
                raise OSError(f'No se pudo guardar {args.vista}')
    texto = json.dumps(dict(nota='Retrato repetido artificialmente. Sin inferencia RMN. '
                                'Diez repeticiones tras calentamiento; no son FPS de cámara.',
                            ancho_procesamiento=config.ANCHO_PROCESAMIENTO,
                            casos=filas), indent=2)
    print(texto)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding='utf-8')
    if any(f['detectados'] != f['esperados'] or f['recortes_validos'] != f['esperados'] for f in filas):
        print('Algún caso no detectó/recortó la cantidad esperada; inspecciona la foto y los umbrales.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
