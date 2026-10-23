"""Compara recortes, tensores y predicciones sobre las mismas imágenes locales."""

import argparse
import importlib.util
import json
from pathlib import Path
import time

import cv2
import numpy as np

import config
from emociones.rmn_detector import CLASES, ClasificadorRMN, preprocesar
from emociones.aplicacion import crear_detector, detectar_rostros, validar_configuracion
from utilidades.procesamiento_imagen import preparar_rostros


def cargar_original():
    ruta = config.BASE / 'referencias' / 'rmn_original' / 'rmn.py'
    spec = importlib.util.spec_from_file_location('rmn_original_referencia', ruta)
    modulo = importlib.util.module_from_spec(spec)
    # Cambiar solo la ubicacion de los pesos en memoria; la copia original
    # permanece intacta para comparar arquitectura y preprocesamiento.
    fuente = ruta.read_text(encoding='utf-8')
    ruta_anterior = "ruta = BASE / 'modelos' / 'rmn_benchmark' / 'resmasking_net.pth'"
    if fuente.count(ruta_anterior) != 1:
        raise ValueError('La referencia RMN no coincide con el cargador esperado.')
    modulo.RUTA_CHECKPOINT_ACTUAL = config.RUTA_RMN
    exec(compile(fuente.replace(ruta_anterior, 'ruta = RUTA_CHECKPOINT_ACTUAL'),
                 str(ruta), 'exec'), modulo.__dict__)
    return modulo


def interseccion_sobre_union(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    interseccion = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - interseccion
    return interseccion / union if union else 0.0


def emparejar(cajas_mp, cajas_haar):
    """Solo mejores parejas mutuas inequívocas: no comparar personas por su orden."""
    if not cajas_mp or not cajas_haar:
        return []
    matriz = np.array([[interseccion_sobre_union(a, b) if a else 0
                        for b in cajas_haar] for a in cajas_mp])
    parejas = []
    for i, fila in enumerate(matriz):
        j = int(fila.argmax())
        if fila[j] < 0.25 or int(matriz[:, j].argmax()) != i:
            continue
        # Solapamientos similares se dejan sin asociar; requieren inspección visual.
        if len(fila) > 1 and np.sort(fila)[-1] - np.sort(fila)[-2] < 0.05:
            continue
        columna = matriz[:, j]
        if len(columna) > 1 and np.sort(columna)[-1] - np.sort(columna)[-2] < 0.05:
            continue
        parejas.append((i, j, float(fila[j])))
    return parejas


def resumen_tensor(rostro):
    tensor = preprocesar(rostro)
    return dict(recorte_bgr_shape=list(rostro.shape), recorte_dtype=str(rostro.dtype),
                tensor_shape=list(tensor.shape), tensor_dtype=str(tensor.dtype),
                minimo=float(tensor.min()), maximo=float(tensor.max()),
                canales_iguales=bool(np.array_equal(tensor[:, 0], tensor[:, 1]) and
                                     np.array_equal(tensor[:, 1], tensor[:, 2])))


def comparar_mismo_recorte(integrado, original, rostro):
    recibidos = []
    hook = integrado.modelo.register_forward_pre_hook(
        lambda modelo, args: recibidos.append(args[0].detach().cpu().numpy().copy()))
    try:
        esperado = original.predecir(rostro)
    finally:
        hook.remove()
    tensor_original = recibidos[0]
    tensor_integrado = preprocesar(rostro)
    actual = integrado.predecir(rostro)
    misma_entrada = bool(np.array_equal(tensor_original, tensor_integrado))
    misma_salida = bool(np.allclose(esperado, actual, rtol=1e-5, atol=1e-6))
    if not misma_entrada or not misma_salida:
        raise AssertionError('Cambió la entrada o la salida respecto a rmn.py para el MISMO recorte.')
    return dict(tensor_identico=misma_entrada, salida_equivalente=misma_salida,
                diferencia_maxima=float(np.max(np.abs(esperado - actual))),
                original=esperado.tolist(), integrado=actual.tolist(),
                clase_original=CLASES[int(esperado.argmax())],
                clase_integrada=CLASES[int(actual.argmax())])


def medir(funcion, repeticiones):
    funcion()  # Calentamiento separado: no incluir inicialización en la mediana.
    muestras = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        funcion()
        muestras.append((time.perf_counter() - inicio) * 1000)
    return dict(mediana_ms=float(np.median(muestras)), minimo_ms=float(min(muestras)),
                maximo_ms=float(max(muestras)), repeticiones=repeticiones)


def evaluar_imagen(ruta, clasificador, original_modulo, repeticiones, guardar, lotes):
    imagen = cv2.imread(str(ruta))
    if imagen is None:
        raise FileNotFoundError(f'No se pudo leer {ruta}')
    detector_haar = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if detector_haar.empty():
        raise RuntimeError('No se pudo cargar Haar.')

    def detectar_haar():
        # Exactamente los parámetros de rmn.py; también funciona sin importar torch.
        return detector_haar.detectMultiScale(cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY),
                                              scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    cajas_haar = [(int(x), int(y), int(x + w), int(y + h)) for x, y, w, h in detectar_haar()]
    crops_haar = [imagen[y:b, x:a] for x, y, a, b in cajas_haar]
    timestamp = 0
    with crear_detector() as detector:
        def detectar_mp():
            nonlocal timestamp
            timestamp += 1
            return detectar_rostros(detector, imagen, timestamp)

        def recortar(resultado):
            return preparar_rostros(imagen, resultado.face_landmarks,
                                    margen=config.MARGEN_ROSTRO, minimo=config.MINIMO_ROSTRO,
                                    fraccion_visible=config.FRACCION_VISIBLE)

        resultado = detectar_mp()
        recortes, indices, crops_mp = recortar(resultado)
        datos = dict(archivo=str(ruta.resolve()), imagen_shape=list(imagen.shape),
                     landmarks_por_rostro=[len(x) for x in resultado.face_landmarks],
                     mediapipe=[dict(caja=r.caja, motivo=r.motivo,
                                     entrada=resumen_tensor(r.imagen) if r.imagen is not None else None)
                                for r in recortes],
                     haar=[dict(caja=caja, entrada=resumen_tensor(crop))
                           for caja, crop in zip(cajas_haar, crops_haar)])
        datos['tiempos'] = dict(mediapipe=medir(detectar_mp, repeticiones),
                                haar=medir(detectar_haar, repeticiones))
        parejas = emparejar([r.caja for r in recortes], cajas_haar)
        datos['parejas'] = []
        for i, j, iou in parejas:
            diferencia = float(np.abs(preprocesar(recortes[i].imagen) - preprocesar(crops_haar[j])).mean())
            datos['parejas'].append(dict(mediapipe=i, haar=j, iou=iou,
                                         diferencia_media_tensor_por_recorte=diferencia))

        if clasificador is not None:
            # Reutilizar el mismo modelo verificado en CPU evita duplicar su memoria.
            # Se ejecuta predecir() ORIGINAL sin alterar su código. Esto valida el
            # adaptador; no constituye una segunda validación independiente del loader.
            original = original_modulo.ClasificadorRMN.__new__(original_modulo.ClasificadorRMN)
            original.modelo = clasificador.modelo
            for r, crop in zip(datos['haar'], crops_haar):
                r['comparacion_mismo_recorte'] = comparar_mismo_recorte(clasificador, original, crop)
            for i in indices:
                datos['mediapipe'][i]['comparacion_mismo_recorte'] = comparar_mismo_recorte(
                    clasificador, original, recortes[i].imagen)
            for pareja in datos['parejas']:
                a = datos['mediapipe'][pareja['mediapipe']]['comparacion_mismo_recorte']
                b = datos['haar'][pareja['haar']]['comparacion_mismo_recorte']
                pareja['cambio_clase_por_recorte'] = a['clase_integrada'] != b['clase_original']
                pareja['delta_max_probabilidad'] = float(np.abs(
                    np.array(a['integrado']) - np.array(b['original'])).max())

            def solo_original():
                for x, y, w, h in original_modulo.detectar(detector_haar, imagen):
                    original.predecir(imagen[y:y+h, x:x+w])

            datos['tiempos']['haar_mas_rmn_original'] = medir(solo_original, repeticiones)
            datos['tiempos']['lotes_integrados'] = []
            lote_anterior = clasificador.lote
            for lote in lotes:
                clasificador.lote = lote

                def integrado():
                    _, _, crops = recortar(detectar_mp())
                    clasificador.inferir(clasificador.preparar(crops))
                    clasificador.sincronizar()

                medicion = medir(integrado, repeticiones)
                medicion.update(lote=lote, rostros_validos=len(indices))
                if crops_mp:
                    referencia = np.array([original.predecir(crop) for crop in crops_mp])
                    actual = clasificador.inferir(clasificador.preparar(crops_mp))
                    medicion['delta_vs_individual'] = float(np.abs(referencia - actual).max())
                    medicion['equivalente'] = bool(np.allclose(referencia, actual, rtol=1e-4, atol=1e-6))
                    if not medicion['equivalente']:
                        raise AssertionError(f'El lote {lote} no coincide con inferencias individuales.')
                datos['tiempos']['lotes_integrados'].append(medicion)
            clasificador.lote = lote_anterior
        if guardar is not None:
            guardar.mkdir(parents=True, exist_ok=True)
            for nombre, crops in [('haar', crops_haar), ('mediapipe', crops_mp)]:
                for i, crop in enumerate(crops):
                    prefijo = guardar / f'{nombre}_{i}'
                    if not cv2.imwrite(str(prefijo) + '.png', crop):
                        raise OSError(f'No se pudo guardar {prefijo}')
                    np.save(str(prefijo) + '.npy', preprocesar(crop))
    return datos


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('imagenes', type=Path, nargs='+')
    parser.add_argument('--solo-recortes', action='store_true', help='No necesita checkpoint ni torch.')
    parser.add_argument('--repeticiones', type=int, default=5)
    parser.add_argument('--lotes', nargs='+', type=int, default=[1, 2, 3])
    parser.add_argument('--salida', type=Path, help='JSON de resultados; por defecto solo consola.')
    parser.add_argument('--guardar-recortes', type=Path, help='Optativo: guarda PNG y tensores NPY.')
    args = parser.parse_args(argv)
    if args.repeticiones < 1 or min(args.lotes) < 1:
        parser.error('Repeticiones y lotes deben ser positivos.')
    try:
        validar_configuracion()
        clasificador, original = None, None
        if not args.solo_recortes:
            clasificador = ClasificadorRMN(config.RUTA_RMN, 'cpu', config.HILOS_RMN, 1)
            original = cargar_original()
            if tuple(original.CLASES) != CLASES:
                raise AssertionError('El orden de clases cambió.')
        datos = dict(solo_recortes=args.solo_recortes, dispositivo='cpu',
                     rmn_ejecutado=clasificador is not None,
                     nota='Tiempos sobre imágenes estáticas, sin cámara ni ventanas. No son FPS de webcam. '
                          'Original e integrado comparten el modelo en eval; se compara predecir original. '
                          'La equivalencia numérica no mide exactitud de clasificación.',
                     configuracion=dict(margen=config.MARGEN_ROSTRO, minimo=config.MINIMO_ROSTRO,
                                        ancho_mp=config.ANCHO_PROCESAMIENTO, hilos=config.HILOS_RMN),
                     clases=CLASES, resultados=[])
        for i, ruta in enumerate(args.imagenes):
            carpeta = args.guardar_recortes / str(i) if args.guardar_recortes else None
            datos['resultados'].append(evaluar_imagen(ruta, clasificador, original,
                                                      args.repeticiones, carpeta, args.lotes))
        texto = json.dumps(datos, indent=2, ensure_ascii=False)
        if args.salida:
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(texto, encoding='utf-8')
            print(f'Resultados: {args.salida}')
        else:
            print(texto)
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, AssertionError, cv2.error) as error:
        print(f'Validación no completada: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
