import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from mirada.postura import MODELO, INDICES, obtener_postura, comparar_postura


def proyectar(rotacion):
    camara = np.array([[640., 0, 320], [0, 640, 240], [0, 0, 1]])
    imagen, _ = cv2.projectPoints(MODELO, np.asarray(rotacion, dtype=float),
                                 np.array([0., 0., 600.]), camara, np.zeros(4))
    puntos = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    for indice, xy in zip(INDICES, imagen.reshape(-1, 2)/[640, 480]):
        puntos[indice] = SimpleNamespace(x=xy[0], y=xy[1])
    return SimpleNamespace(landmark=puntos)


class PosturaTest(unittest.TestCase):
    def test_descarta_ajuste_incompatible_con_landmarks(self):
        rostro = proyectar(np.zeros(3))
        rostro.landmark[1].x += .2
        self.assertIsNone(obtener_postura([rostro], (640, 480)))

    def test_recupera_rotaciones_sinteticas(self):
        for eje in range(3):
            for grados in (-20., 0., 20.):
                rotacion = np.zeros(3)
                rotacion[eje] = np.radians(grados)
                postura = obtener_postura([proyectar(rotacion)], (640, 480))
                esperado = np.zeros(3)
                esperado[eje] = grados
                np.testing.assert_allclose(postura[:3], esperado, atol=1e-4)

    def test_perdida_o_geometria_degenerada_no_crashea(self):
        degenerado = SimpleNamespace(landmark=[SimpleNamespace(x=.5, y=.5)]*478)
        for rostros in ([], [degenerado], [degenerado, degenerado]):
            self.assertIsNone(obtener_postura(rostros, (640, 480)))

    def test_detecta_giro_desplazamiento_y_cambio_de_tamano(self):
        referencia = np.array([0., 0., 0., .5, .5, .2])
        self.assertEqual(comparar_postura(referencia, referencia)[0], 'POSTURA SIMILAR')
        for indice, valor in ((0, 9.), (1, 9.), (2, 9.), (3, .54), (4, .54), (5, .24)):
            actual = referencia.copy()
            actual[indice] = valor
            self.assertEqual(comparar_postura(actual, referencia)[0], 'POSTURA CAMBIO')

    def test_no_inventa_referencia_y_resuelve_cruce_de_angulos(self):
        referencia = np.array([179., 0., 0., .5, .5, .2])
        actual = referencia.copy()
        actual[0] = -179.
        self.assertEqual(comparar_postura(actual, referencia)[0], 'POSTURA SIMILAR')
        self.assertEqual(comparar_postura(actual, None), ('SIN REFERENCIA', None))
        self.assertEqual(comparar_postura(None, referencia), ('SIN POSTURA', None))
