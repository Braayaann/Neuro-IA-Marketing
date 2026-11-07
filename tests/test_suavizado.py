"""Pruebas temporales sintéticas; no miden precisión de mirada con cámara."""
import unittest

import numpy as np

from mirada.calibracion import Calibracion, OBJETIVOS
from mirada.suavizado import SuavizadoMirada


class SuavizadoMiradaTest(unittest.TestCase):
    def test_posicion_constante_no_se_desplaza(self):
        filtro = SuavizadoMirada()
        for t in np.arange(0., 2., 1/30):
            np.testing.assert_allclose(filtro.actualizar([.4, .6], t), [.4, .6])

    def test_reduce_ruido_en_fijacion(self):
        filtro = SuavizadoMirada()
        tiempos = np.arange(0., 3., 1/30)
        ruido = .003 * np.sin(2*np.pi*9*tiempos)
        entrada = np.column_stack((.5 + ruido, .5 - ruido))
        salida = np.array([filtro.actualizar(p, t) for p, t in zip(entrada, tiempos)])
        rms_entrada = np.sqrt(np.mean((entrada[30:] - .5)**2))
        rms_salida = np.sqrt(np.mean((salida[30:] - .5)**2))
        self.assertLess(rms_salida, .4*rms_entrada)

    def test_adaptacion_responde_mas_rapido_al_movimiento(self):
        adaptativo = SuavizadoMirada()
        fijo = SuavizadoMirada(beta=0.)
        for i in range(30):
            adaptativo.actualizar([.4, .5], i/30)
            fijo.actualizar([.4, .5], i/30)
        for i in range(30, 36):
            a = adaptativo.actualizar([.6, .5], i/30)
            f = fijo.actualizar([.6, .5], i/30)
        self.assertLess(abs(a[0]-.6), abs(f[0]-.6))
        np.testing.assert_allclose(a[1], .5)

    def test_tasa_de_camara_no_define_el_tiempo_del_filtro(self):
        finales = []
        for fps in (15, 30, 60):
            filtro = SuavizadoMirada(beta=0.)
            filtro.actualizar([0., 0.], 0.)
            for i in range(1, fps+1):
                salida = filtro.actualizar([1., 1.], i/fps)
            finales.append(salida[0])
        self.assertLess(max(finales)-min(finales), .01)

    def test_perdida_y_pausa_no_arrastran_posicion_anterior(self):
        for evento in ('perdida', 'reinicio', 'pausa', 'reloj'):
            filtro = SuavizadoMirada()
            filtro.actualizar([.2, .3], 10.)
            if evento == 'perdida':
                self.assertIsNone(filtro.actualizar(None, 10.01))
            elif evento == 'reinicio':
                filtro.reiniciar()
            tiempo = 11. if evento == 'pausa' else 9. if evento == 'reloj' else 10.02
            np.testing.assert_allclose(filtro.actualizar([.8, .7], tiempo), [.8, .7])

    def test_muestra_invalida_no_contamina_recuperacion(self):
        for muestra, tiempo in (([np.nan, .5], 1.), ([.5, .5], np.inf), ([.5], 1.)):
            filtro = SuavizadoMirada()
            filtro.actualizar([.2, .3], 0.)
            self.assertIsNone(filtro.actualizar(muestra, tiempo))
            np.testing.assert_allclose(filtro.actualizar([.8, .7], 1.1), [.8, .7])

    def test_no_modifica_muestras_de_calibracion(self):
        entrada = np.array(OBJETIVOS, dtype=float)
        original = entrada.copy()
        filtro = SuavizadoMirada()
        for i, punto in enumerate(entrada):
            salida = filtro.actualizar(punto, i/30)
            salida[:] = 0.
        np.testing.assert_array_equal(entrada, original)
        ajuste = Calibracion().ajustar(entrada)
        np.testing.assert_allclose(ajuste.predecir([.3, .7]), [.3, .7])

    def test_parametros_invalidos(self):
        for parametros in ({'corte_minimo': 0}, {'beta': -1}, {'corte_velocidad': np.nan}, {'pausa_maxima': 0}):
            with self.assertRaises(ValueError):
                SuavizadoMirada(**parametros)


if __name__ == '__main__':
    unittest.main()
