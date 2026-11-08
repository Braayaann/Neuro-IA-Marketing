"""Recorrido de calibración y terminal con cámara, reloj y entradas simulados."""
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import ExitStack, redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

import main


class FlujoDiagnosticoTest(unittest.TestCase):
    def test_nueve_puntos_generan_referencia_y_seguimiento(self):
        self.comprobar_flujo('iris')

    def test_l2cs_calibra_angulos_y_comprueba_sin_tratarlos_como_pixeles(self):
        self.comprobar_flujo('l2cs')

    def test_control_rapido_corrige_y_persiste(self):
        self.comprobar_flujo('iris', control=True)

    def test_giro_transitorio_repite_solo_el_punto_afectado(self):
        self.comprobar_flujo('iris', giro=True)

    def test_fila_inferior_con_postura_estable_completa_al_primer_intento(self):
        self.comprobar_flujo('iris', control=True, fila_inferior=True)

    def comprobar_flujo(self, estimador, control=False, giro=False, fila_inferior=False):
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

        def observar_postura(*args):
            actual = postura.copy()
            if fila_inferior and estado['objetivo'][1] > .7:
                actual[0] += 11
            if giro and 55 < estado['frames'] < 105:
                actual[1] += 15
            return actual

        def reloj():
            estado['tiempo'] += 1/30
            return estado['tiempo']

        def tecla(*args):
            estado['frames'] += 1
            if estado['frames'] == 1:
                return ord('c')
            if mouse.moveTo.called:
                if control and not estado.get('control'):
                    estado['control'] = True
                    return ord('v')
                if control and mouse.moveTo.call_count == 1:
                    self.assertLess(estado['frames'], 4000)
                    return -1
                return ord('q')
            self.assertLess(estado['frames'], 3000, 'La calibración no terminó.')
            return -1

        def circulo(imagen, centro, *args):
            if imagen.shape[:2] == (720, 1280):
                estado['objetivo'] = np.array(centro)/[1279, 719]
            return imagen

        def senal(*args):
            iris = np.array([.4, .48])+estado['objetivo']*[.1, .04]
            if estado.get('control'):
                iris += [.005, 0.]
            return np.array([iris, iris])

        salida = io.StringIO()
        modelo_mirada = MagicMock()
        modelo_mirada.dispositivo = 'cpu'
        modelo_mirada.estimar.side_effect = lambda *args: np.array([.15, -.1])+estado['objetivo']*[.3, .15]
        with ExitStack() as pila:
            base = Path(pila.enter_context(TemporaryDirectory()))
            pila.enter_context(patch('main.BASE', base))
            pila.enter_context(redirect_stdout(salida))
            pila.enter_context(patch.dict('sys.modules', {'pyautogui': mouse, 'keyboard': teclado}))
            pila.enter_context(patch('mirada.l2cs.EstimadorL2CS', return_value=modelo_mirada))
            reemplazos = {'cv2.VideoCapture': MagicMock(return_value=camara),
                          'mp.solutions.face_mesh.FaceMesh': MagicMock(return_value=contexto),
                          'time.perf_counter': reloj, 'obtener_iris_por_ojo': senal,
                          'obtener_postura': observar_postura,
                          'cv2.waitKey': tecla, 'cv2.circle': circulo,
                          'cv2.getWindowProperty': MagicMock(return_value=1)}
            for nombre, reemplazo in reemplazos.items():
                pila.enter_context(patch('main.'+nombre, reemplazo))
            for nombre in ('webbrowser.open', 'cv2.imshow', 'cv2.namedWindow',
                           'cv2.setWindowProperty', 'cv2.destroyWindow', 'cv2.destroyAllWindows'):
                pila.enter_context(patch('main.'+nombre))
            main.ejecutar(SimpleNamespace(modo='mirada', diagnostico=False, camara=0,
                                         sin_suavizado=False, sin_calibracion=False, clic_parpadeo=False,
                                         estimador=estimador))
            ruta, = (base/'resultados'/'calibraciones').glob('*.json')
            restaurado, referencia = main.cargar_perfil(ruta)
            np.testing.assert_allclose(referencia, postura)
            self.assertTrue(np.isfinite(restaurado.coeficientes).all())
            if control:
                np.testing.assert_allclose(restaurado.desplazamiento, [-.05, 0], atol=.002)
        datos = [json.loads(linea[len('[NEURO] '):]) for linea in salida.getvalue().splitlines()
                 if linea.startswith('[NEURO] ')]
        puntos = [d for d in datos if d['evento'] == 'punto_calibracion']
        self.assertEqual(sum(d['aceptado'] for d in puntos), 9)
        self.assertEqual([d['punto'] for d in puntos if not d['aceptado']], [1] if giro else [])
        validacion = [d for d in datos if d['evento'] == 'punto_validacion']
        self.assertEqual(len(validacion), 5)
        seleccion = next(d for d in datos if d['evento'] == 'validacion_lista')
        self.assertEqual(seleccion['elegido'], 'lineal')
        self.assertLess(seleccion['metricas']['lineal']['error_medio_px'], 1.)
        referencia = next(d for d in datos if d['evento'] == 'calibracion_lista')['referencia_postura']
        np.testing.assert_allclose(referencia, postura)
        self.assertTrue(any(d['evento'] == 'seguimiento' for d in datos))
        inicio = next(d for d in datos if d['evento'] == 'inicio')
        self.assertEqual(inicio['unidades_senal'], 'radianes' if estimador == 'l2cs' else 'ancho_ojo')
        if estimador == 'l2cs':
            self.assertTrue(modelo_mirada.estimar.called)
        else:
            modelo_mirada.estimar.assert_not_called()
        self.assertEqual(mouse.moveTo.call_count, 2 if control else 1)
        camara.release.assert_called_once()
