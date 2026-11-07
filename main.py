"""MediaPipe para el iris y RMN para expresiones. Una sola cámara."""
import argparse
from pathlib import Path
import time
import unicodedata
import webbrowser

import cv2
import mediapipe as mp
import numpy as np

from mirada.calibracion import Calibracion, OBJETIVOS
from mirada.captura import CapturaPunto
from mirada.iris import CENTROS_IRIS, obtener_iris
from mirada.suavizado import SuavizadoMirada

BASE = Path(__file__).resolve().parent


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


def ejecutar(args):
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
        print('OK: modelos cargados e inferencia completada. No mide precisión real.')
        return
    mirada = args.modo != 'emociones'
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
    puntos = []
    captura = None
    intento = 1
    aviso = ''
    ultimo_click = 0.
    ventana = 'Neuro IA - Camara'
    objetivo_ventana = 'Calibracion - mira el punto'
    print('Q: salir | C: calibrar | P: pausar/reanudar | S: suavizado ON/OFF. Mantén la posición tras calibrar.')
    pausa = False
    suavizado = not args.sin_suavizado
    filtro = SuavizadoMirada()
    anterior_c = anterior_p = anterior_s = False
    try:
        with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True, max_num_faces=2) as detector:
            while True:
                ok, frame = camara.read()
                if not ok or frame is None:
                    raise RuntimeError('La cámara dejó de entregar imágenes.')
                frame = cv2.flip(frame, 1)
                rostros = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).multi_face_landmarks or []
                iris = obtener_iris(rostros, (frame.shape[1], frame.shape[0]))
                ahora = time.perf_counter()
                if iris is None or calibrando or pausa or not suavizado or not (ajuste or args.sin_calibracion):
                    filtro.reiniciar()
                if calibrando:
                    resultado = captura.actualizar(iris, ahora)
                    if resultado is not None:
                        if resultado.posicion is not None:
                            puntos.append(resultado.posicion)
                            intento = 1
                            aviso = ''
                        else:
                            intento += 1
                            aviso = resultado.motivo
                            print(f'Punto {len(puntos)+1}: {aviso} Se repite.')
                        if len(puntos) == 9:
                            try:
                                ajuste = Calibracion().ajustar(puntos)
                                print('Calibración lista. Vuelve al navegador para ver el mapa.')
                            except ValueError as error:
                                print(error)
                                ajuste = None
                            calibrando = False
                            cv2.destroyWindow(objetivo_ventana)
                        else:
                            captura = CapturaPunto(ahora)
                    if calibrando:
                        pantalla = np.zeros((alto, ancho, 3), np.uint8)
                        x, y = OBJETIVOS[len(puntos)]
                        fase, restante = captura.estado(ahora)
                        color = (0, 230, 255) if fase == 'PREPARATE' else (0, 220, 0)
                        cv2.circle(pantalla, (round(x*(ancho-1)), round(y*(alto-1))), 16, color, -1)
                        mensajes = [(30, f'Punto {len(puntos)+1}/9 | Intento {intento} | Mira el punto sin mover la cabeza | Q: salir'),
                                    (alto-35, f'{fase}: {restante:.1f}s | Muestras validas: {len(captura.muestras)}')]
                        if aviso:
                            mensajes.append((alto-10, 'Se repite: ' + aviso))
                        # Hershey no dibuja tildes; el motivo completo también va a consola.
                        for altura_texto, texto in mensajes:
                            texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
                            cv2.putText(pantalla, texto, (20, altura_texto),
                                        cv2.FONT_HERSHEY_SIMPLEX, min(.55, ancho/1800), (255, 255, 255), 1)
                        cv2.imshow(objetivo_ventana, pantalla)
                elif mirada and not pausa and iris is not None and (ajuste or args.sin_calibracion):
                    senal = filtro.actualizar(iris, ahora) if suavizado else iris
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
                estado = 'CALIBRANDO' if calibrando else 'PAUSA' if pausa else 'LISTO' if ajuste else 'C: calibrar'
                if mirada:
                    texto_filtro = 'CALIBRACION SIN FILTRO' if calibrando else f'S: suavizado {"ON" if suavizado else "OFF"}'
                    cv2.putText(vista, texto_filtro, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                cv2.putText(vista, f'{estado} | Q: salir', (10, vista.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                cv2.imshow(ventana, vista)
                tecla = cv2.waitKey(1) & 0xff
                salir = tecla in (27, ord('q')) or (mirada and keyboard.is_pressed('q'))
                if salir or cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
                    break
                c = mirada and (tecla == ord('c') or keyboard.is_pressed('c'))
                p = mirada and (tecla == ord('p') or keyboard.is_pressed('p'))
                s = mirada and (tecla == ord('s') or keyboard.is_pressed('s'))
                if c and not anterior_c:
                    filtro.reiniciar()
                    ajuste, puntos = None, []
                    intento, aviso = 1, ''
                    calibrando = True
                    cv2.namedWindow(objetivo_ventana, cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty(objetivo_ventana, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    captura = CapturaPunto(time.perf_counter())
                if p and not anterior_p and not calibrando:
                    pausa = not pausa
                    filtro.reiniciar()
                if s and not anterior_s:
                    suavizado = not suavizado
                    filtro.reiniciar()
                    print(f'Suavizado: {"ON" if suavizado else "OFF"}. La calibración siempre usa muestras sin filtrar.')
                anterior_c, anterior_p, anterior_s = c, p, s
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
    parser.add_argument('--diagnostico', action='store_true', help='Prueba modelos sin cámara ni movimiento del cursor.')
    try:
        ejecutar(parser.parse_args())
    except (OSError, ValueError, RuntimeError, ImportError, cv2.error) as error:
        parser.exit(1, f'{error}\n')
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
