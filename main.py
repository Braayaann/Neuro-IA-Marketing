"""Mirada con iris binocular o L2CS-Net, y expresiones RMN. Una sola cámara."""
import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
import unicodedata
import webbrowser

import cv2
import mediapipe as mp
import numpy as np

from mirada.calibracion import Calibracion, CONTROL, OBJETIVOS, VALIDACION, corregir_deriva, evaluar, seleccionar_ajuste
from mirada.captura import CapturaPunto
from mirada.iris import CENTROS_IRIS, ConsistenciaBinocular, obtener_iris_por_ojo
from mirada.postura import obtener_postura, comparar_postura
from mirada.diagnostico import ResumenTerminal, emitir
from mirada.suavizado import SuavizadoMirada

BASE = Path(__file__).resolve().parent


def cargar_perfil(ruta):
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    ajuste = Calibracion(datos['metodo']).ajustar(datos['puntos'])
    delta = np.asarray(datos.get('desplazamiento', [0., 0.]), dtype=float)
    if delta.shape != (2,) or not np.isfinite(delta).all():
        raise ValueError('Desplazamiento de perfil inválido.')
    ajuste.desplazamiento = delta
    postura = datos['postura']
    if postura is not None:
        postura = np.asarray(postura, dtype=float)
        if postura.shape != (6,) or not np.isfinite(postura).all() or postura[5] <= 0:
            raise ValueError('Postura de referencia inválida')
    return ajuste, postura


def guardar_perfil(ruta, ajuste, puntos, postura):
    datos = dict(metodo=ajuste.metodo, puntos=np.asarray(puntos).tolist(),
                 postura=None if postura is None else postura.tolist(), desplazamiento=ajuste.desplazamiento.tolist())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=ruta.parent, delete=False) as archivo:
        temporal = Path(archivo.name)
    try:
        temporal.write_text(json.dumps(datos, allow_nan=False), encoding='utf-8')
        temporal.replace(ruta)
    finally:
        temporal.unlink(missing_ok=True)


def clasificar(frame, rostros, modelo):
    from emociones.rmn_detector import CLASES
    alto, ancho = frame.shape[:2]
    etiquetas = []
    for rostro in rostros:
        puntos = np.array([(p.x*ancho, p.y*alto) for p in rostro.landmark[:468]])
        minimo, maximo = puntos.min(0), puntos.max(0)
        margen = .1*max(maximo-minimo)
        x1, y1 = np.maximum(0, minimo-margen).astype(int)
        x2, y2 = np.minimum([ancho, alto], maximo+margen).astype(int)
        if min(x2-x1, y2-y1) < 60:
            continue
        scores = modelo.predecir(frame[y1:y2, x1:x2])
        indice = int(scores.argmax())
        etiquetas.append(((x1, y1, x2, y2), f'{CLASES[indice]} {scores[indice]:.0%}'))
    return etiquetas


def persistir(perfil, ajuste, referencia):
    if perfil is not None:
        try:
            guardar_perfil(perfil, ajuste, ajuste.muestras, referencia)
            print('Calibración guardada para la próxima sesión.')
        except OSError as error:
            print(f'Calibración activa solo en esta sesión: {error}')


def ejecutar(args):
    estimador = getattr(args, 'estimador', 'iris')
    mirada = args.modo != 'emociones'
    modelo_mirada = None
    opciones_captura = {}
    if mirada and estimador == 'l2cs':
        if args.sin_calibracion:
            raise ValueError('L2CS produce ángulos, no píxeles. Omite --sin-calibracion y pulsa C.')
        from mirada.l2cs import EstimadorL2CS
        modelo_mirada = EstimadorL2CS(dispositivo=getattr(args, 'dispositivo_mirada', 'cpu'))
        opciones_captura = {'tolerancia': np.radians([3., 3.]), 'duracion': 4.}
        print(f'Mirada L2CS/Gaze360: {modelo_mirada.dispositivo}. Se requiere calibración de pantalla.')
    modelo = None
    if args.modo != 'mirada':
        from emociones.rmn_detector import ClasificadorRMN
        modelo = ClasificadorRMN(BASE/'emociones'/'pesos'/'resmasking_net.pth')
        print(f'Expresiones RMN: {modelo.dispositivo}')
    if args.diagnostico:
        with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True) as detector:
            assert not detector.process(np.zeros((240, 320, 3), np.uint8)).multi_face_landmarks
        if modelo is not None:
            resultado = modelo.predecir(np.zeros((100, 100, 3), np.uint8))
            assert resultado.shape == (7,) and np.isfinite(resultado).all()
        if modelo_mirada is not None:
            resultado = modelo_mirada.predecir(np.zeros((180, 180, 3), np.uint8))
            assert resultado.shape == (2,) and np.isfinite(resultado).all()
        print('OK: modelos cargados e inferencia completada. No mide precisión real.')
        return
    if mirada:
        import pyautogui
        import keyboard
        ancho, alto = pyautogui.size()
        # Conserva FAILSAFE: mover el mouse a una esquina permite interrumpirlo.
        pyautogui.PAUSE = .01
        webbrowser.open((BASE/'mirada'/'heatmap.html').as_uri())
    camara = cv2.VideoCapture(args.camara, cv2.CAP_DSHOW)
    if not camara.isOpened():
        camara.release()
        camara = cv2.VideoCapture(args.camara)
    if not camara.isOpened():
        camara.release()
        raise RuntimeError('No se pudo abrir la cámara. Revisa permisos y otras aplicaciones.')
    ajuste = None
    calibrando = False
    validando = False
    control_rapido = False
    anterior_v = False
    candidatos, pruebas = {}, []
    metodo_ajuste = getattr(args, 'ajuste', 'auto')
    puntos = []
    captura = None
    intento = 1
    aviso = ''
    ultimo_click = 0.
    ventana = 'Neuro IA - Camara'
    objetivo_ventana = 'Calibracion - mira el punto'
    print('Q: salir | C: calibrar | V: comprobar y corregir perfil | P: pausa | S: suavizado.')
    pausa = False
    suavizado = not args.sin_suavizado
    filtro = SuavizadoMirada()
    consistencia = ConsistenciaBinocular()
    anterior_c = anterior_p = anterior_s = False
    referencia_postura = None
    perfil = None
    if mirada and not args.sin_calibracion:
        perfil = BASE/'resultados'/'calibraciones'/f'v1-{estimador}-{metodo_ajuste}-cam{args.camara}-{ancho}x{alto}.json'
        try:
            ajuste, referencia_postura = cargar_perfil(perfil)
            print('Calibración recuperada. Pulsa C si necesitas reemplazarla.')
        except FileNotFoundError:
            print('Primer uso con esta configuración. Pulsa C para crear tu perfil.')
        except (OSError, KeyError, TypeError, ValueError) as error:
            print(f'Perfil ilegible ({error}). Pulsa C para calibrar.')
    posturas_punto, posturas_aceptadas = [], []
    inicio_sesion = time.perf_counter()
    resumen = ResumenTerminal(inicio_sesion)
    emitir('inicio', version=2, modo=args.modo, camara=args.camara,
           ajuste_solicitado=metodo_ajuste,
           estimador=estimador if mirada else None, unidades_senal='radianes' if modelo_mirada else 'ancho_ojo',
           captura_segundos=opciones_captura.get('duracion', CapturaPunto.duracion),
           tolerancia_captura=opciones_captura.get('tolerancia', CapturaPunto.tolerancia),
           pantalla=[ancho, alto] if mirada else None, mediapipe=mp.__version__, opencv=cv2.__version__,
           suavizado=suavizado, filtro={'corte_minimo': filtro.corte_minimo, 'beta': filtro.beta},
           umbrales_postura={'grados': 8, 'desplazamiento_anchos_cara': .15, 'cambio_ancho': .15})
    try:
        with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True, max_num_faces=2) as detector:
            while True:
                ok, frame = camara.read()
                if not ok or frame is None:
                    raise RuntimeError('La cámara dejó de entregar imágenes.')
                frame = cv2.flip(frame, 1)
                rostros = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).multi_face_landmarks or []
                ojos = obtener_iris_por_ojo(rostros, (frame.shape[1], frame.shape[0]))
                iris = None if ojos is None else ojos.mean(axis=0)
                ahora = time.perf_counter()
                if modelo_mirada:
                    senal_cruda = modelo_mirada.estimar(frame, rostros) if iris is not None else None
                else:
                    senal_cruda = iris if consistencia.aceptar(ojos, ahora) else None
                postura = obtener_postura(rostros, (frame.shape[1], frame.shape[0])) if mirada else None
                xy = None
                if senal_cruda is None or calibrando or pausa or not suavizado or not (ajuste or args.sin_calibracion):
                    filtro.reiniciar()
                if calibrando:
                    objetivos = CONTROL if control_rapido else VALIDACION if validando else OBJETIVOS
                    posiciones = pruebas if validando else puntos
                    antes = len(captura.muestras)
                    resultado = captura.actualizar(senal_cruda, ahora, postura if estimador == 'iris' else None)
                    if len(captura.muestras) > antes and postura is not None:
                        posturas_punto.append(postura)
                    if resultado is not None:
                        evento = 'punto_control' if control_rapido else 'punto_validacion' if validando else 'punto_calibracion'
                        emitir(evento, punto=len(posiciones)+1, intento=intento,
                               objetivo=objetivos[len(posiciones)], aceptado=resultado.posicion is not None,
                               motivo=resultado.motivo, muestras=len(captura.muestras), total=captura.total,
                               dispersion=np.std(captura.muestras, axis=0) if captura.muestras else None,
                               senal=resultado.posicion, estimador=estimador,
                               postura_mediana=np.median(posturas_punto, axis=0) if posturas_punto else None)
                        if resultado.posicion is not None:
                            posiciones.append(resultado.posicion)
                            if posturas_punto and not validando:
                                posturas_aceptadas.append(np.median(posturas_punto, axis=0))
                            intento = 1
                            aviso = ''
                        else:
                            intento += 1
                            aviso = resultado.motivo
                            print(f'Punto {len(posiciones)+1}: {aviso} Se repite.')
                        if len(posiciones) == len(objetivos):
                            try:
                                if control_rapido:
                                    aplicado, motivo, antes, despues = corregir_deriva(ajuste, pruebas, (ancho, alto))
                                    emitir('control_rapido', aplicado=aplicado, motivo=motivo, antes=antes,
                                           errores_propuestos_px=despues, desplazamiento=ajuste.desplazamiento)
                                    print(motivo)
                                    if aplicado:
                                        persistir(perfil, ajuste, referencia_postura)
                                    control_rapido = calibrando = validando = False
                                elif not validando:
                                    candidatos = {'lineal': Calibracion('lineal').ajustar(puntos)}
                                    if metodo_ajuste == 'auto' and estimador == 'iris':
                                        candidatos['local'] = Calibracion('local').ajustar(puntos)
                                    try:
                                        candidatos['cuadratico'] = Calibracion('cuadratico').ajustar(puntos)
                                    except ValueError as error:
                                        emitir('ajuste_descartado', metodo='cuadratico', motivo=str(error))
                                    if metodo_ajuste != 'auto' and metodo_ajuste not in candidatos:
                                        raise ValueError('El ajuste solicitado no pudo calcularse. Repite la calibración.')
                                    referencia_postura = np.median(posturas_aceptadas, axis=0) if posturas_aceptadas else None
                                    emitir('calibracion_capturada', puntos=np.asarray(puntos), objetivos=OBJETIVOS,
                                           referencia_postura=referencia_postura)
                                    validando = True
                                    print('Nueve puntos capturados. Ahora comprueba cinco puntos nuevos.')
                                else:
                                    metricas = {nombre: evaluar(m, pruebas, VALIDACION, (ancho, alto))
                                                for nombre, m in candidatos.items()}
                                    elegido = seleccionar_ajuste(metricas) if metodo_ajuste == 'auto' else metodo_ajuste
                                    ajuste = candidatos[elegido]
                                    persistir(perfil, ajuste, referencia_postura)
                                    emitir('validacion_lista', metricas=metricas, elegido=elegido,
                                           muestras=np.asarray(pruebas), objetivos=VALIDACION)
                                    emitir('calibracion_lista', metodo=elegido, puntos=np.asarray(puntos), objetivos=OBJETIVOS,
                                           media=ajuste.media, escala=ajuste.escala, coeficientes=ajuste.coeficientes,
                                           referencia_postura=referencia_postura)
                                    print(f'Ajuste {elegido}: error medio de comprobación '
                                          f'{metricas[elegido]["error_medio_px"]:.0f} px. Vuelve al navegador.')
                                    calibrando = validando = False
                            except ValueError as error:
                                print(error)
                                ajuste, referencia_postura = respaldo
                                emitir('calibracion_fallida', motivo=str(error))
                                control_rapido = calibrando = validando = False
                        if not calibrando:
                            cv2.destroyWindow(objetivo_ventana)
                        else:
                            captura = CapturaPunto(ahora, **opciones_captura)
                        posturas_punto = []
                    if calibrando:
                        pantalla = np.zeros((alto, ancho, 3), np.uint8)
                        objetivos = CONTROL if control_rapido else VALIDACION if validando else OBJETIVOS
                        indice_punto = len(pruebas) if validando else len(puntos)
                        x, y = objetivos[indice_punto]
                        fase, restante = captura.estado(ahora)
                        color = (0, 230, 255) if fase == 'PREPARATE' else (0, 220, 0)
                        cv2.circle(pantalla, (round(x*(ancho-1)), round(y*(alto-1))), 16, color, -1)
                        etapa = 'CONTROL RAPIDO' if control_rapido else 'COMPROBACION' if validando else 'CALIBRACION'
                        mensajes = [(30, f'{etapa} {indice_punto+1}/{len(objetivos)} | Intento {intento} | Cabeza estable | Q: salir'),
                                    (alto-35, f'{fase}: {restante:.1f}s | Muestras validas: {len(captura.muestras)}')]
                        if aviso:
                            mensajes.append((alto-10, 'Se repite: ' + aviso))
                        # Hershey no dibuja tildes; el motivo completo también va a consola.
                        for altura_texto, texto in mensajes:
                            texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
                            cv2.putText(pantalla, texto, (20, altura_texto),
                                        cv2.FONT_HERSHEY_SIMPLEX, min(.55, ancho/1800), (255, 255, 255), 1)
                        cv2.imshow(objetivo_ventana, pantalla)
                elif mirada and not pausa and senal_cruda is not None and (ajuste or args.sin_calibracion):
                    senal = filtro.actualizar(senal_cruda, ahora) if suavizado else senal_cruda
                    xy = ajuste.predecir(senal) if ajuste else senal
                    if np.isfinite(xy).all() and ((xy >= 0) & (xy <= 1)).all():
                        pyautogui.moveTo(round(xy[0]*(ancho-1)), round(xy[1]*(alto-1)))
                if mirada and args.clic_parpadeo and not pausa and not calibrando and len(rostros) == 1:
                    p = rostros[0].landmark
                    if p[145].y-p[159].y < .004 and ahora-ultimo_click > 1:
                        pyautogui.click()
                        ultimo_click = ahora
                vista = frame.copy()
                if modelo is not None and not calibrando:
                    for (x1, y1, x2, y2), texto in clasificar(frame, rostros, modelo):
                        cv2.rectangle(vista, (x1, y1), (x2, y2), (0, 220, 0), 1)
                        cv2.putText(vista, texto, (x1, max(20, y1-8)), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 220, 0), 2)
                if iris is not None:
                    for indice in CENTROS_IRIS:
                        centro = rostros[0].landmark[indice]
                        cv2.circle(vista, (round(centro.x*frame.shape[1]), round(centro.y*frame.shape[0])),
                                   3, (0, 255, 255), -1)
                estado = 'VALIDANDO' if validando else 'CALIBRANDO' if calibrando else 'PAUSA' if pausa else 'LISTO' if ajuste else 'C: calibrar'
                estado_postura, delta_postura = comparar_postura(postura, referencia_postura)
                if mirada:
                    texto_filtro = 'CALIBRACION SIN FILTRO' if calibrando else f'S: suavizado {"ON" if suavizado else "OFF"}'
                    cv2.putText(vista, texto_filtro, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                    cv2.putText(vista, estado_postura, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, .5,
                                (0, 180, 255) if estado_postura == 'POSTURA CAMBIO' else (255, 255, 255), 1)
                    cv2.putText(vista, f'Mirada: {estimador} | Ajuste: {ajuste.metodo if ajuste else "pendiente"}',
                                (10, 75), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
                resumen.actualizar(ahora, iris, senal=senal_cruda, estado=estado, ojos=ojos, suavizado=suavizado,
                                   estimador=estimador, metodo_ajuste=ajuste.metodo if ajuste else None,
                                   resolucion_camara=[frame.shape[1], frame.shape[0]],
                                   postura=postura, estado_postura=estado_postura, delta_postura=delta_postura,
                                   estimacion_px=xy*np.array([ancho-1, alto-1]) if xy is not None else None,
                                   dentro_pantalla=bool(((xy >= 0) & (xy <= 1)).all()) if xy is not None else None,
                                   brillo_frame=round(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()), 1))
                cv2.putText(vista, f'{estado} | Q: salir', (10, vista.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                cv2.imshow(ventana, vista)
                tecla = cv2.waitKey(1) & 0xff
                salir = tecla in (27, ord('q')) or (mirada and keyboard.is_pressed('q'))
                if salir or cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
                    break
                c = mirada and (tecla == ord('c') or keyboard.is_pressed('c'))
                v = mirada and (tecla == ord('v') or keyboard.is_pressed('v'))
                p = mirada and (tecla == ord('p') or keyboard.is_pressed('p'))
                s = mirada and (tecla == ord('s') or keyboard.is_pressed('s'))
                iniciar_control = v and not anterior_v and ajuste is not None
                if (c and not anterior_c) or (iniciar_control and not calibrando):
                    if not calibrando:
                        respaldo = ajuste, referencia_postura
                    control_rapido = bool(iniciar_control and not c)
                    filtro.reiniciar()
                    puntos = []
                    validando, candidatos, pruebas = control_rapido, {}, []
                    intento, aviso = 1, ''
                    if not control_rapido:
                        referencia_postura = None
                    posturas_punto, posturas_aceptadas = [], []
                    emitir('control_inicio' if control_rapido else 'calibracion_inicio')
                    calibrando = True
                    cv2.namedWindow(objetivo_ventana, cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty(objetivo_ventana, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    captura = CapturaPunto(time.perf_counter(), **opciones_captura)
                if p and not anterior_p and not calibrando:
                    pausa = not pausa
                    filtro.reiniciar()
                if s and not anterior_s:
                    suavizado = not suavizado
                    filtro.reiniciar()
                    print(f'Suavizado: {"ON" if suavizado else "OFF"}. La calibración siempre usa muestras sin filtrar.')
                anterior_c, anterior_p, anterior_s = c, p, s
                anterior_v = v
    finally:
        camara.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modo', choices=('mirada', 'emociones', 'ambos'), default='ambos')
    parser.add_argument('--camara', type=int, default=0)
    parser.add_argument('--sin-calibracion', action='store_true', help='Conversión directa de la señal relativa binocular; sin precisión de pantalla.')
    parser.add_argument('--clic-parpadeo', action='store_true', help='Habilita los clics del ejemplo original.')
    parser.add_argument('--sin-suavizado', action='store_true', help='Inicia sin filtro temporal; S permite alternarlo durante la sesión.')
    parser.add_argument('--ajuste', choices=('auto', 'lineal', 'cuadratico'), default='auto',
                        help='Auto compara los ajustes en cinco puntos nuevos tras calibrar con nueve.')
    parser.add_argument('--estimador', choices=('iris', 'l2cs'), default='iris',
                        help='Iris binocular o modelo preentrenado L2CS/Gaze360. Ambos se calibran con C.')
    parser.add_argument('--dispositivo-mirada', choices=('cpu', 'cuda'), default='cpu',
                        help='Dispositivo para L2CS. La instalación CPU no incluye CUDA.')
    parser.add_argument('--diagnostico', action='store_true', help='Prueba modelos sin cámara ni movimiento del cursor.')
    try:
        ejecutar(parser.parse_args())
    except (OSError, ValueError, RuntimeError, ImportError, cv2.error) as error:
        parser.exit(1, f'{error}\n')
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
