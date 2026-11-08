import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from main import cargar_perfil, guardar_perfil
from mirada.calibracion import Calibracion, OBJETIVOS
from mirada.comparador import Alternativas, OBJETIVOS_PRUEBA


class ComparadorTest(unittest.TestCase):
    def test_desfase_y_escala_recuperan_objetivos_y_persisten(self):
        base = Calibracion().ajustar(OBJETIVOS)
        alternativas = Alternativas(base, (1001, 801))
        muestras = (np.array(OBJETIVOS_PRUEBA)-.5-[.03, -.025])/[1.1, .9]+.5
        alternativas.escalar(0, .1)
        alternativas.escalar(1, -.1)
        alternativas.mover(0, 30)
        alternativas.mover(1, -20)
        metricas = alternativas.errores(muestras)
        self.assertLess(metricas['lineal']['error_maximo_px'], 1e-8)
        self.assertGreater(metricas['guardado']['error_medio_px'], 10)
        self.assertGreater(metricas['local']['error_medio_px'], 10)
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta)/'perfil.json'
            guardar_perfil(ruta, alternativas.modelo, base.muestras, None)
            restaurado, _ = cargar_perfil(ruta)
            for muestra, objetivo in zip(muestras, OBJETIVOS_PRUEBA):
                np.testing.assert_allclose(restaurado.predecir(muestra), objetivo)

    def test_alternativas_no_modifican_el_perfil_original(self):
        base = Calibracion('local').ajustar(OBJETIVOS)
        alternativas = Alternativas(base, (800, 600))
        alternativas.mover(1, -10)
        alternativas.escalar(0, 1)
        np.testing.assert_array_equal(base.ganancia, [1, 1])
        np.testing.assert_array_equal(base.desplazamiento, [0, 0])
        self.assertEqual(alternativas.modelo.ganancia[0], 1.5)
