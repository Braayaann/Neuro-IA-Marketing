"""Recorrido de calibración y terminal con cámara, reloj y entradas simulados."""
import io
import json
import unittest
from contextlib import ExitStack, redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

import main


class FlujoDiagnosticoTest(unittest.TestCase):
    def test_nueve_puntos_generan_referencia_y_seguimiento(self):
        estado = {'tiempo': 0., 'objetivo': np.array([.12, .12]), 'frames': 0}
        camara = MagicMock()
        camara.isOpened.return_value = True
        camara.read.return_value = (True, np.zeros((240, 320, 3), np.uint8))
        detector = MagicMock()
        detector.process.return_value.multi_face_landmarks = [SimpleNamespace(
            landmark=[SimpleNamespace(x=.5, y=.5)]*478)]
        contexto = MagicMock()
        contexto.__enter__.return_value = detector
        mouse, teclado = MagicMock(), MagicMock()
        mouse.size.return_value = (1280, 720)
        teclado.is_pressed.return_value = False
        postura = np.array([0., 0., 0., .5, .5, .2])

        def reloj():
            estado['tiempo'] += 1/30
            return estado['tiempo']

        def tecla(*args):
            estado['frames'] += 1
            if estado['frames'] == 1:
                return ord('c')
            if mouse.moveTo.called:
                return ord('q')
            self.assertLess(estado['frames'], 1200, 'La calibración no terminó.')
            return -1

        def circulo(imagen, centro, *args):
            if imagen.shape[:2] == (720, 1280):
                estado['objetivo'] = np.array(centro)/[1279, 719]
            return imagen

        def senal(*args):
            iris = np.array([.4, .48])+estado['objetivo']*[.1, .04]
            return np.array([iris, iris])

        salida = io.StringIO()
        with ExitStack() as pila:
            pila.enter_context(redirect_stdout(salida))
            pila.enter_context(patch.dict('sys.modules', {'pyautogui': mouse, 'keyboard': teclado}))
            reemplazos = {'cv2.VideoCapture': MagicMock(return_value=camara),
                          'mp.solutions.face_mesh.FaceMesh': MagicMock(return_value=contexto),
                          'time.perf_counter': reloj, 'obtener_iris_por_ojo': senal,
                          'obtener_postura': MagicMock(return_value=postura),
                          'cv2.waitKey': tecla, 'cv2.circle': circulo,
                          'cv2.getWindowProperty': MagicMock(return_value=1)}
            for nombre, reemplazo in reemplazos.items():
                pila.enter_context(patch('main.'+nombre, reemplazo))
            for nombre in ('webbrowser.open', 'cv2.imshow', 'cv2.namedWindow',
                           'cv2.setWindowProperty', 'cv2.destroyWindow', 'cv2.destroyAllWindows'):
                pila.enter_context(patch('main.'+nombre))
            main.ejecutar(SimpleNamespace(modo='mirada', diagnostico=False, camara=0,
                                         sin_suavizado=False, sin_calibracion=False, clic_parpadeo=False))
        datos = [json.loads(linea[len('[NEURO] '):]) for linea in salida.getvalue().splitlines()
                 if linea.startswith('[NEURO] ')]
        puntos = [d for d in datos if d['evento'] == 'punto_calibracion']
        self.assertEqual(len(puntos), 9)
        self.assertTrue(all(d['aceptado'] for d in puntos))
        referencia = next(d for d in datos if d['evento'] == 'calibracion_lista')['referencia_postura']
        np.testing.assert_allclose(referencia, postura)
        self.assertTrue(any(d['evento'] == 'seguimiento' for d in datos))
        mouse.moveTo.assert_called_once()
        camara.release.assert_called_once()
