"""Prueba experimental A/B con mirada L2CS, independiente de RMN."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import time

import cv2
import numpy as np

from .estimador import Estimador
from .geometria import proyectar, region
from .seguimiento import Seguimiento

BASE = Path(__file__).resolve().parent
VENTANA = 'Prueba A/B - mirada experimental'
SECUENCIA = ['A', 'B', 'B', 'A', 'B', 'A', 'A', 'B']


def cargar_config(ruta):
    config = json.loads(Path(ruta).read_text(encoding='utf-8'))
    if len(config['pantalla_px']) != 2 or min(config['pantalla_px']) < 400:
        raise ValueError('Resolucion de pantalla incorrecta.')
    valores = [*config['pantalla_cm'], config['distancia_cm'], config['fov_horizontal_grados']]
    if not np.isfinite(valores).all() or min(valores) <= 0:
        raise ValueError('Revisa las dimensiones, la distancia y el FOV en config.json.')
    if not 1 < config['fov_horizontal_grados'] < 179:
        raise ValueError('FOV fuera de rango.')
    return config


def texto(canvas, contenido, x, y, escala, color=(245, 245, 245)):
    cv2.putText(canvas, contenido, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX,
                escala, color, max(1, int(escala * 2)), cv2.LINE_AA)


def renderizar(config, estado, punto=None, objetivo=None, paso=None, imagenes=None, resumen=None, calor=False):
    ancho, alto = config['pantalla_px']
    escala = ancho / 1600
    canvas = np.full((alto, ancho, 3), (24, 20, 18), np.uint8)
    texto(canvas, 'PROTOTIPO SIN VALIDAR - NO MIDE PREFERENCIA', ancho * .03, alto * .055, .75 * escala)
    etiqueta = 'Prueba en curso: sigue la cruz' if objetivo else f'Estimacion: {estado}'
    texto(canvas, etiqueta, ancho * .03, alto * .115, 1.0 * escala, (80, 225, 240))
    texto(canvas, 'Mirada aproximada por zonas | Una persona a 1 m | Camara arriba al centro',
          ancho * .03, alto * .16, .57 * escala, (170, 170, 170))
    for i, nombre in enumerate(('A', 'B')):
        x1 = int(ancho * (.02 if i == 0 else .52))
        x2 = int(ancho * (.48 if i == 0 else .98))
        y1, y2 = int(alto * .20), int(alto * .90)
        color = (100, 65, 30) if i == 0 else (55, 90, 75)
        canvas[y1:y2, x1:x2] = color
        if imagenes and imagenes[i] is not None:
            imagen = imagenes[i]
            factor = min((x2-x1)/imagen.shape[1], (y2-y1)/imagen.shape[0])
            imagen = cv2.resize(imagen, (max(1, int(imagen.shape[1]*factor)), max(1, int(imagen.shape[0]*factor))))
            ix, iy = (x1+x2-imagen.shape[1])//2, (y1+y2-imagen.shape[0])//2
            canvas[iy:iy+imagen.shape[0], ix:ix+imagen.shape[1]] = imagen
        else:
            texto(canvas, f'ANUNCIO {nombre}', x1 + (x2-x1)*.20, alto*.53, 1.6*escala)
        if objetivo is None and calor and resumen:
            # Color uniforme por anuncio: no simula precision espacial dentro de la zona.
            porcentaje = resumen['porcentaje_del_tiempo_asignado'][nombre]
            color_calor = cv2.applyColorMap(np.uint8([[round(porcentaje*2.55)]]), cv2.COLORMAP_JET)[0, 0]
            capa = np.full_like(canvas[y1:y2, x1:x2], color_calor)
            cv2.addWeighted(capa, .45, canvas[y1:y2, x1:x2], .55, 0, canvas[y1:y2, x1:x2])
        if objetivo is None and resumen:
            segundos = resumen['segundos'][nombre]
            porcentaje = resumen['porcentaje_del_tiempo_asignado'][nombre]
            cv2.rectangle(canvas, (x1, y2-int(alto*.07)), (x2, y2), (25, 25, 25), -1)
            texto(canvas, f'{nombre}: {segundos:.1f} s | {porcentaje:.1f}% del tiempo asignado',
                  x1+ancho*.01, y2-alto*.025, .55*escala)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (150, 150, 150), max(1, int(escala)))
    if objetivo is None and punto is not None and all(np.isfinite(punto)) and 0 <= punto[0] <= 1 and 0 <= punto[1] <= 1:
        # Solo muestra un punto estimado, nunca se fuerza uno fuera de pantalla a entrar.
        posicion = (int(punto[0] * (ancho-1)), int(punto[1] * (alto-1)))
        cv2.circle(canvas, posicion, max(6, int(10*escala)), (0, 220, 250), 2)
    if objetivo:
        posicion = (int(ancho*(.25 if objetivo == 'A' else .75)), int(alto*.55))
        cv2.drawMarker(canvas, posicion, (255, 255, 255), cv2.MARKER_CROSS, int(35*escala), max(2, int(escala*2)))
        texto(canvas, f'PRUEBA {paso}/8: mira la cruz del anuncio {objetivo}',
              ancho*.03, alto*.95, .75*escala)
    else:
        if resumen:
            texto(canvas, f"Cobertura: {resumen['cobertura']:.0%} | Fuera: {resumen['segundos']['FUERA']:.1f} s | Sin asignar: {resumen['segundos']['INDETERMINADA']:.1f} s",
                  ancho*.03, alto*.935, .52*escala)
        texto(canvas, 'H: calor por zonas | R: guardar/reiniciar | T: prueba | V: camara | Q: salir', ancho*.03, alto*.975, .55*escala)
    return canvas


def guardar_prueba(lecturas, config):
    por_prueba = []
    for indice, esperado in enumerate(SECUENCIA):
        muestras = [fila for fila in lecturas if fila['prueba'] == indice]
        conteo = Counter(fila['prediccion'] for fila in muestras)
        # Contar indeterminadas y fuera: no ocultarlas al calcular el resultado.
        mayor = max(conteo.values(), default=0)
        ganadores = [k for k, v in conteo.items() if v == mayor]
        resultado = ganadores[0] if len(ganadores) == 1 else 'INDETERMINADA'
        por_prueba.append({'objetivo': esperado, 'resultado_mayoritario': resultado,
                          'coincide': resultado == esperado, 'muestras': dict(conteo)})
    validas = sum(fila['prediccion'] in ('A', 'B') for fila in lecturas)
    informe = {
        'tipo': 'prueba exploratoria, no calibracion ni validacion de publico',
        'configuracion': config,
        'pruebas_coincidentes': sum(fila['coincide'] for fila in por_prueba),
        'total_pruebas': len(SECUENCIA), 'lecturas_totales': len(lecturas),
        'lecturas_asignadas_a_anuncios': validas,
        'fraccion_asignada': validas/len(lecturas) if lecturas else 0,
        'por_prueba': por_prueba, 'lecturas': lecturas,
    }
    carpeta = BASE / 'resultados'
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / datetime.now().strftime('prueba_AB_%Y%m%d_%H%M%S_%f.json')
    ruta.write_text(json.dumps(informe, indent=2, allow_nan=False), encoding='utf-8')
    return ruta, informe


def guardar_sesion(seguimiento, config):
    carpeta = BASE / 'resultados'
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / datetime.now().strftime('sesion_zonas_%Y%m%d_%H%M%S_%f.json')
    informe = {'tipo': 'tiempo de mirada estimado por zonas, no preferencia',
               'configuracion': config, 'resumen': seguimiento.resumen(),
               'suavizado_segundos': seguimiento.ventana,
               'permanencia_segundos': seguimiento.permanencia}
    ruta.write_text(json.dumps(informe, indent=2, allow_nan=False), encoding='utf-8')
    print('Sesion guardada:', ruta)
    return ruta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE/'config.json')
    parser.add_argument('--anuncio-a', type=Path)
    parser.add_argument('--anuncio-b', type=Path)
    args = parser.parse_args()
    config = cargar_config(args.config)
    imagenes = []
    for ruta in (args.anuncio_a, args.anuncio_b):
        imagen = cv2.imread(str(ruta)) if ruta else None
        if ruta and imagen is None:
            parser.error(f'No se pudo leer el anuncio: {ruta}')
        imagenes.append(imagen)
    print('Cargando L2CS. Prueba geometrica aproximada, sin validacion de precision.')
    estimador = Estimador()
    camara = cv2.VideoCapture(config['camara_indice'])
    seguimiento = Seguimiento(banda=config['banda_central_fraccion'])
    calor = False
    inicio_prueba, lecturas, ver_camara = None, [], False
    indice_visible, visible_desde = None, None
    try:
        if not camara.isOpened():
            raise RuntimeError('No se pudo abrir la camara; cierra el otro programa de video.')
        camara.set(cv2.CAP_PROP_FRAME_WIDTH, config['captura_px'][0])
        camara.set(cv2.CAP_PROP_FRAME_HEIGHT, config['captura_px'][1])
        camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        while True:
            correcto, frame = camara.read()
            if not correcto:
                raise RuntimeError('No se pudo leer la camara.')
            capturado = time.monotonic()
            # Sin espejo: los ejes se corresponden con la camara y la pantalla.
            resultado = estimador.procesar(frame)
            punto, estado = None, 'INDETERMINADA'
            if resultado['estado'] == 'OK':
                punto = proyectar(resultado['horizontal'], resultado['vertical'], resultado['ojo'],
                                  (frame.shape[1], frame.shape[0]), config)
                estado = region(punto, config['banda_central_fraccion'])
                if punto is not None and not .20 <= punto[1] <= .90:
                    estado = 'FUERA'
                if punto is not None and not .02 <= punto[0] <= .98:
                    estado = 'FUERA'
            ahora = time.monotonic()
            punto_crudo, estado_crudo = punto, estado
            if inicio_prueba is None:
                punto, estado = seguimiento.actualizar(ahora, punto, estado)
            objetivo, paso = None, None
            if inicio_prueba is not None:
                transcurrido = ahora - inicio_prueba
                indice = int(transcurrido // 4)
                if indice >= len(SECUENCIA):
                    ruta, informe = guardar_prueba(lecturas, config)
                    print(f"Prueba: {informe['pruebas_coincidentes']}/8 coincidencias. Lecturas asignadas: {informe['fraccion_asignada']:.1%}")
                    print('Informe:', ruta)
                    inicio_prueba = None
                    seguimiento.reiniciar()
                else:
                    objetivo, paso = SECUENCIA[indice], indice+1
                    if indice == indice_visible and capturado - visible_desde >= 1:
                        lecturas.append({'prueba': indice, 'segundos': round(transcurrido, 3),
                                         'objetivo': objetivo, 'prediccion': estado_crudo,
                                         'estado_detector': resultado['estado'],
                                         'punto_estimado': list(punto_crudo) if punto_crudo else None})
                    if indice != indice_visible:
                        indice_visible, visible_desde = indice, ahora
            cv2.imshow(VENTANA, renderizar(config, estado, punto, objetivo, paso, imagenes, seguimiento.resumen(), calor))
            if ver_camara:
                cv2.imshow('Camara - sin grabacion', frame)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (27, ord('q'), ord('Q')):
                break
            if tecla in (ord('h'), ord('H')) and inicio_prueba is None:
                calor = not calor
            if tecla in (ord('r'), ord('R')) and inicio_prueba is None:
                guardar_sesion(seguimiento, config)
                seguimiento.reiniciar()
            if tecla in (ord('t'), ord('T')) and inicio_prueba is None:
                guardar_sesion(seguimiento, config)
                seguimiento.reiniciar()
                inicio_prueba, lecturas = time.monotonic(), []
                indice_visible, visible_desde = None, None
                if ver_camara:
                    cv2.destroyWindow('Camara - sin grabacion')
                ver_camara = False
            if tecla in (ord('v'), ord('V')) and inicio_prueba is None:
                ver_camara = not ver_camara
                if not ver_camara:
                    cv2.destroyWindow('Camara - sin grabacion')
            if cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        try:
            if seguimiento.resumen()['total_segundos'] > 0:
                guardar_sesion(seguimiento, config)
        finally:
            camara.release()
            cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
