"""Verificación con pesos originales: cargadores independientes, lotes y flujo completo."""

import argparse
import gc
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
import torch

import config
import main as aplicacion
from emociones.rmn_detector import CLASES, ClasificadorRMN, SHA256_ORIGINAL
from utilidades.procesamiento_imagen import preparar_rostros
from validar_integracion import cargar_original, evaluar_imagen


class CapturaDeImagen:
    """Sustituye solo la cámara física por una imagen en memoria, sin guardar video."""
    def __init__(self, imagen):
        self.imagen = imagen

    def read(self):
        return True, self.imagen.copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('retrato', type=Path, help='Foto con un rostro frontal.')
    parser.add_argument('--repeticiones', type=int, default=5)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--vista', type=Path, help='Guardar voluntariamente una vista con predicciones reales.')
    args = parser.parse_args()
    if args.repeticiones < 1:
        parser.error('Las repeticiones deben ser positivas.')
    imagen = cv2.imread(str(args.retrato))
    if imagen is None:
        parser.error('No se pudo leer el retrato.')

    original_modulo = cargar_original()
    # Solo redirigir en memoria la ubicación del checkpoint; fuentes originales intactas.
    original_modulo.BASE = config.BASE
    sys.path.insert(0, str(config.BASE / 'referencias' / 'rmn_original'))
    original = original_modulo.ClasificadorRMN()
    regiones = original_modulo.detectar(original_modulo.crear_detector(), imagen)
    if len(regiones) != 1:
        raise AssertionError('La prueba requiere una imagen de referencia con un rostro Haar.')
    recortes_haar = [imagen[y:y+h, x:x+w] for x, y, w, h in regiones]
    esperado = np.array([original.predecir(crop) for crop in recortes_haar])
    arquitectura_original = type(original.modelo).__name__
    del original
    gc.collect()

    # Cargar de nuevo con el adaptador verifica el cargador, no solo el preprocesamiento.
    clasificador = ClasificadorRMN(config.RUTA_RMN, 'cpu', config.HILOS_RMN, 1)
    actual = np.array([clasificador.predecir(crop) for crop in recortes_haar])
    np.testing.assert_allclose(actual, esperado, rtol=1e-5, atol=1e-6)
    assert tuple(original_modulo.CLASES) == CLASES
    assert not clasificador.modelo.training

    informe = dict(checkpoint_sha256=SHA256_ORIGINAL, torch=torch.__version__,
                   cuda_disponible=torch.cuda.is_available(), dispositivo='cpu',
                   hilos=config.HILOS_RMN, arquitectura=arquitectura_original,
                   carga_independiente=dict(original=esperado.tolist(), integrado=actual.tolist(),
                                            diferencia_maxima=float(np.abs(esperado-actual).max())),
                   nota='Composiciones estáticas del mismo retrato. No mide exactitud ni FPS de webcam. '
                        'Los tiempos del flujo usan captura de memoria, sin ventana. '
                        'La comparación de cargadores carga y libera el original antes del adaptador.',
                   casos=[])
    retrato = cv2.resize(imagen, (round(imagen.shape[1] * 400 / imagen.shape[0]), 400))
    with tempfile.TemporaryDirectory(prefix='validacion_rmn_') as temporal:
        for cantidad in range(4):
            frame = np.zeros((400, 3 * retrato.shape[1], 3), np.uint8)
            for i in range(cantidad):
                frame[:, i*retrato.shape[1]:(i+1)*retrato.shape[1]] = retrato
            ruta_temporal = Path(temporal) / f'{cantidad}_rostros.png'
            if not cv2.imwrite(str(ruta_temporal), frame):
                raise OSError('No se pudo preparar la imagen temporal.')
            caso = evaluar_imagen(ruta_temporal, clasificador, original_modulo,
                                  args.repeticiones, None, [1, 2, 3])
            caso['archivo'] = f'composicion_en_memoria_{cantidad}_rostros'
            caso['rostros_esperados'] = cantidad
            assert len(caso['mediapipe']) == cantidad
            assert len(caso['haar']) == cantidad
            assert all(r['entrada'] is not None for r in caso['mediapipe'])
            assert len(caso['parejas']) == cantidad

            # Ejercitar el mismo bucle que la aplicación, con ambos modelos reales.
            with aplicacion.crear_detector() as detector:
                resultado = aplicacion.detectar_rostros(detector, frame, 0)
                recortes, indices, crops = preparar_rostros(
                    frame, resultado.face_landmarks, margen=config.MARGEN_ROSTRO,
                    minimo=config.MINIMO_ROSTRO, fraccion_visible=config.FRACCION_VISIBLE)
                tensor = clasificador.preparar(crops)
                clasificador.inferir(tensor)  # Calentamiento fuera de la medición aislada.
                muestras_rmn = []
                for _ in range(args.repeticiones):
                    inicio = time.perf_counter()
                    clasificador.inferir(tensor)
                    muestras_rmn.append((time.perf_counter() - inicio) * 1000)
                caso['rmn_solo_inferencia_mediana_ms'] = float(np.median(muestras_rmn))
            # Contexto nuevo: ejecutar_video genera su propia secuencia de timestamps.
            with aplicacion.crear_detector() as detector:
                mediciones = aplicacion.ejecutar_video(
                    detector, CapturaDeImagen(frame), clasificador,
                    max_fotogramas=args.repeticiones, sin_ventana=True)
            caso['flujo_aplicacion_sin_webcam'] = mediciones.resumen()
            assert all(r['rostros'] == cantidad and r['clasificados'] == cantidad
                       for r in caso['flujo_aplicacion_sin_webcam'])

            if cantidad == 3 and args.vista:
                scores = clasificador.inferir(tensor)
                etiquetas = [r.motivo for r in recortes]
                for indice, probabilidades in zip(indices, scores):
                    clase = int(probabilidades.argmax())
                    etiquetas[indice] = f'{CLASES[clase]} {probabilidades[clase]:.1%}'
                vista = frame.copy()
                aplicacion.dibujar_rostros(vista, resultado.face_landmarks, True, etiquetas, recortes)
                vista = aplicacion.mostrar_informacion(vista, cantidad, 0, True, True, {})
                aplicacion.escribir_texto(vista, 'PRUEBA ESTATICA - FPS de camara no medidos', (10, 24))
                args.vista.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(args.vista), vista):
                    raise OSError('No se pudo guardar la vista.')
            informe['casos'].append(caso)
            print(f'Caso {cantidad} rostros: cargador, recortes, predicciones, lotes y flujo aprobados.', flush=True)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Informe completo: {args.salida}')


if __name__ == '__main__':
    main()
