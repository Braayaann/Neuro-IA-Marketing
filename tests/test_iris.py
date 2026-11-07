"""Comprobaciones geométricas; no sustituyen la prueba de precisión con cámara."""
import unittest
from types import SimpleNamespace

import numpy as np

from mirada.calibracion import Calibracion, OBJETIVOS
from mirada.iris import obtener_iris


def rostro(posiciones=((.5, .5), (.5, .5)), escala=1., desplazamiento=(0., 0.)):
    puntos = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    for centro, indices, (x, y) in zip(
            (.35, .65), ((468, 33, 133, 159, 145), (473, 362, 263, 386, 374)), posiciones):
        coords = ((centro-.05+.1*x, .48+.04*y),
                  (centro-.05, .5), (centro+.05, .5),
                  (centro, .48), (centro, .52))
        for indice, xy in zip(indices, coords):
            px, py = np.asarray(xy)*escala + desplazamiento
            puntos[indice] = SimpleNamespace(x=px, y=py)
    return SimpleNamespace(landmark=puntos)


class SeguimientoBinocularTest(unittest.TestCase):
    def test_centro_en_ambos_ojos(self):
        for tamano in ((640, 480), (1280, 720)):
            np.testing.assert_allclose(obtener_iris([rostro()], tamano), [.5, .5])

    def test_ambos_ojos_contribuyen_a_la_senal(self):
        for posiciones in (((.2, .3), (.6, .9)), ((.6, .9), (.2, .3))):
            np.testing.assert_allclose(obtener_iris([rostro(posiciones)], (640, 480)), [.4, .53])

    def test_movimiento_de_iris_con_rostro_fijo(self):
        for punto in ((.2, .3), (.8, .7)):
            esperado = [punto[0], .5 + .3*(punto[1]-.5)]
            np.testing.assert_allclose(obtener_iris([rostro((punto, punto))], (640, 480)), esperado)

    def test_cambios_de_parpados_abiertos_no_mueven_senal(self):
        original = obtener_iris([rostro(((.3, .7), (.6, .8)))], (640, 480))
        for arriba, abajo in ((159, 145), (386, 374)):
            for superior, inferior in ((.49, .515), (.475, .51)):
                r = rostro(((.3, .7), (.6, .8)))
                r.landmark[arriba].y = superior
                r.landmark[abajo].y = inferior
                np.testing.assert_allclose(obtener_iris([r], (640, 480)), original)

    def test_cambios_de_parpados_no_mueven_prediccion_calibrada(self):
        muestras = [obtener_iris([rostro((p, p))], (640, 480)) for p in OBJETIVOS]
        ajuste = Calibracion().ajustar(muestras)
        punto = (.35, .65)
        r = rostro((punto, punto))
        r.landmark[159].y = .49
        r.landmark[145].y = .515
        r.landmark[386].y = .485
        r.landmark[374].y = .51
        np.testing.assert_allclose(ajuste.predecir(obtener_iris([r], (640, 480))), punto)

    def test_traslacion_y_escala_no_cambian_senal(self):
        posiciones = ((.3, .6), (.5, .8))
        original = obtener_iris([rostro(posiciones)], (640, 480))
        transformado = obtener_iris([rostro(posiciones, .7, (.15, .1))], (640, 480))
        np.testing.assert_allclose(original, transformado)

    def test_no_acepta_falta_de_rostro_o_varios(self):
        for rostros in ([], [rostro(), rostro()], [SimpleNamespace(landmark=[])]):
            self.assertIsNone(obtener_iris(rostros, (640, 480)))

    def test_ningun_ojo_invalido_se_promedia(self):
        for indice in (468, 473):
            r = rostro()
            r.landmark[indice].x = float('nan')
            self.assertIsNone(obtener_iris([r], (640, 480)))
        for arriba, abajo in ((159, 145), (386, 374)):
            r = rostro()
            r.landmark[abajo].y = r.landmark[arriba].y
            self.assertIsNone(obtener_iris([r], (640, 480)))

    def test_senal_compatible_con_calibracion_actual(self):
        muestras = [obtener_iris([rostro((p, p))], (640, 480)) for p in OBJETIVOS]
        ajuste = Calibracion().ajustar(muestras)
        punto = (.35, .65)
        prediccion = ajuste.predecir(obtener_iris([rostro((punto, punto))], (640, 480)))
        np.testing.assert_allclose(prediccion, punto)


if __name__ == '__main__':
    unittest.main()
