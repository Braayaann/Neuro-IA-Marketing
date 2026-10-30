"""MediaPipe para el iris y RMN para expresiones. Una sola cámara."""
import argparse
from pathlib import Path
import time
import webbrowser

import cv2
import mediapipe as mp
import numpy as np

from mirada.calibracion import Calibracion, OBJETIVOS

BASE = Path(__file__).resolve().parent


def obtener_iris(rostros):
    if len(rostros) != 1:
        return None
    p = rostros[0].landmark
    # Mismo punto utilizado por mouse_ocular.py del cliente.
    if p[145].y-p[159].y < .004:
        return None
    xy = np.array([p[475].x, p[475].y])
    return xy if np.isfinite(xy).all() and ((xy >= 0) & (xy <= 1)).all() else None


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
    puntos, muestras = [], []
    inicio = 0.
    ultimo_click = 0.
    ventana = 'Neuro IA - Camara'
    objetivo_ventana = 'Calibracion - mira el punto'
    print('Q: salir | C: calibrar | P: pausar/reanudar cursor. Mantén la posición tras calibrar.')
    pausa = False
    anterior_c = anterior_p = False
    try:
        with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True, max_num_faces=2) as detector:
            while True:
                ok, frame = camara.read()
                if not ok or frame is None:
                    raise RuntimeError('La cámara dejó de entregar imágenes.')
                frame = cv2.flip(frame, 1)
                rostros = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).multi_face_landmarks or []
                iris = obtener_iris(rostros)
                ahora = time.perf_counter()
                if calibrando:
                    transcurrido = ahora-inicio
                    if .8 <= transcurrido <= 2.8 and iris is not None:
                        muestras.append(iris)
                    if transcurrido > 2.8:
                        if len(muestras) >= 10:
                            puntos.append(np.median(muestras, axis=0))
                        else:
                            print('Pocas muestras válidas. Se repite el punto.')
                        muestras = []
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
                            inicio = ahora
                    if calibrando:
                        pantalla = np.zeros((alto, ancho, 3), np.uint8)
                        x, y = OBJETIVOS[len(puntos)]
                        cv2.circle(pantalla, (round(x*(ancho-1)), round(y*(alto-1))), 16, (0, 230, 255), -1)
                        cv2.putText(pantalla, f'Mira el punto {len(puntos)+1}/9 - Q cancela', (30, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, .8, (255, 255, 255), 2)
                        cv2.imshow(objetivo_ventana, pantalla)
                elif mirada and not pausa and iris is not None and (ajuste or args.sin_calibracion):
                    xy = ajuste.predecir(iris) if ajuste else iris
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
                    cv2.circle(vista, tuple((iris*[frame.shape[1], frame.shape[0]]).astype(int)), 3, (0, 255, 255), -1)
                estado = 'CALIBRANDO' if calibrando else 'PAUSA' if pausa else 'LISTO' if ajuste else 'C: calibrar'
                cv2.putText(vista, f'{estado} | Q: salir', (10, vista.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                cv2.imshow(ventana, vista)
                tecla = cv2.waitKey(1) & 0xff
                salir = tecla in (27, ord('q')) or (mirada and keyboard.is_pressed('q'))
                if salir or cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
                    break
                c = mirada and (tecla == ord('c') or keyboard.is_pressed('c'))
                p = mirada and (tecla == ord('p') or keyboard.is_pressed('p'))
                if c and not anterior_c:
                    ajuste, puntos, muestras = None, [], []
                    calibrando = True
                    cv2.namedWindow(objetivo_ventana, cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty(objetivo_ventana, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    inicio = time.perf_counter()
                if p and not anterior_p and not calibrando:
                    pausa = not pausa
                anterior_c, anterior_p = c, p
    finally:
        camara.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modo', choices=('mirada', 'emociones', 'ambos'), default='ambos')
    parser.add_argument('--camara', type=int, default=0)
    parser.add_argument('--sin-calibracion', action='store_true', help='Conversión directa del cliente; solo para comparar.')
    parser.add_argument('--clic-parpadeo', action='store_true', help='Habilita los clics del ejemplo original.')
    parser.add_argument('--diagnostico', action='store_true', help='Prueba modelos sin cámara ni movimiento del cursor.')
    try:
        ejecutar(parser.parse_args())
    except (OSError, ValueError, RuntimeError, ImportError, cv2.error) as error:
        parser.exit(1, f'{error}\n')
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
