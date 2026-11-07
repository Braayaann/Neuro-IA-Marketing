import unittest

import numpy as np

from mirada.calibracion import Calibracion, OBJETIVOS, VALIDACION, evaluar, seleccionar_ajuste


class CalibracionTest(unittest.TestCase):
    def test_cuadratico_mejora_relacion_curva_en_puntos_nuevos(self):
        def pantalla(x):
            x = np.asarray(x)
            return np.column_stack((.1+.65*x[:, 0]+.18*x[:, 1]**2,
                                    .1+.55*x[:, 1]+.2*x[:, 0]*x[:, 1]))
        muestras = np.array(OBJETIVOS)
        objetivos = pantalla(muestras)
        comprobacion = np.array(VALIDACION)
        modelos = {m: Calibracion(m).ajustar(muestras, objetivos) for m in ('lineal', 'cuadratico')}
        metricas = {m: evaluar(modelo, comprobacion, pantalla(comprobacion), (2560, 1440))
                    for m, modelo in modelos.items()}
        self.assertLess(metricas['cuadratico']['error_medio_px'], metricas['lineal']['error_medio_px']/5)
        self.assertEqual(seleccionar_ajuste(metricas), 'cuadratico')

    def test_lineal_sigue_reproduciendo_el_metodo_anterior(self):
        modelo = Calibracion('lineal').ajustar(OBJETIVOS)
        np.testing.assert_allclose(modelo.predecir([.3, .7]), [.3, .7])

    def test_prefiere_lineal_si_no_hay_mejora_relevante(self):
        for lineal, cuadratico in ((30., 29.), (100., 96.), (0., 0.)):
            self.assertEqual(seleccionar_ajuste({'lineal': {'error_medio_px': lineal},
                                                'cuadratico': {'error_medio_px': cuadratico}}), 'lineal')

    def test_rechaza_geometria_degenerada(self):
        for metodo in ('lineal', 'cuadratico'):
            with self.assertRaises(ValueError):
                Calibracion(metodo).ajustar(np.ones((9, 2)))
            with self.assertRaises(ValueError):
                Calibracion(metodo).ajustar(np.column_stack((np.arange(9), np.arange(9))))

    def test_errores_sin_recortar_predicciones_fuera_de_pantalla(self):
        modelo = Calibracion().ajustar(OBJETIVOS)
        metricas = evaluar(modelo, [[1.2, .5]], [[1., .5]], (1001, 501))
        self.assertAlmostEqual(metricas['error_medio_px'], 200.)
