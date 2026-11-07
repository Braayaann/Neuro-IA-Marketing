import unittest

import numpy as np

from mirada.calibracion import Calibracion, CONTROL, OBJETIVOS, VALIDACION, corregir_deriva, evaluar, seleccionar_ajuste


class CalibracionTest(unittest.TestCase):
    def test_deriva_uniforme_verificada_y_sin_doble_correccion(self):
        modelo = Calibracion().ajustar(OBJETIVOS)
        muestras = np.array(CONTROL) + [.04, -.03]
        self.assertTrue(corregir_deriva(modelo, muestras, (1000, 800))[0])
        np.testing.assert_allclose(modelo.predecir(muestras[-1]), CONTROL[-1])
        self.assertFalse(corregir_deriva(modelo, muestras, (1000, 800))[0])

    def test_deriva_variable_o_no_confirmada_conserva_perfil(self):
        for indice in (1, 3):
            muestras = np.array(CONTROL) + [.05, 0]
            muestras[indice, 0] -= .05
            modelo = Calibracion().ajustar(OBJETIVOS)
            self.assertFalse(corregir_deriva(modelo, muestras, (1000, 800))[0])
            np.testing.assert_array_equal(modelo.desplazamiento, [0, 0])

    def test_ajuste_local_con_distorsion_limitada_a_una_zona(self):
        def deformar(puntos):
            puntos = np.array(puntos)
            distancia2 = ((puntos-[.12, .12])**2).sum(axis=1)
            return puntos + np.exp(-distancia2[:, None]/.09)*[.1, .08]
        metricas = {}
        for nombre in ('lineal', 'local'):
            ajuste = Calibracion(nombre).ajustar(OBJETIVOS, deformar(OBJETIVOS))
            metricas[nombre] = evaluar(ajuste, VALIDACION, deformar(VALIDACION), (2560, 1440))
        self.assertEqual(seleccionar_ajuste(metricas), 'local')

    def test_descarta_mejora_media_si_empeora_el_peor_objetivo(self):
        self.assertEqual(seleccionar_ajuste({
            'lineal': dict(error_medio_px=60, error_maximo_px=100),
            'local': dict(error_medio_px=40, error_maximo_px=120)}), 'lineal')

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
