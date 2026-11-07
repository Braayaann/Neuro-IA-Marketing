"""Control temporal y de estabilidad con señales sintéticas de calibración."""
import unittest

import numpy as np

from mirada.captura import CapturaPunto


def completar(captura, muestras, tiempos=None):
    if tiempos is None:
        tiempos = np.linspace(.01, 2.39, len(muestras))
    for muestra, tiempo in zip(muestras, tiempos):
        captura.actualizar(muestra, captura.inicio+captura.preparacion+tiempo)
    return captura.actualizar(None, captura.inicio+captura.preparacion+captura.duracion+.01)


class CapturaPuntoTest(unittest.TestCase):
    def test_preparacion_no_captura(self):
        captura = CapturaPunto(10.)
        self.assertIsNone(captura.actualizar([.9, .9], 10.5))
        self.assertEqual(captura.total, 0)
        self.assertEqual(captura.estado(10.5)[0], 'PREPARATE')
        self.assertEqual(captura.estado(11.5)[0], 'CAPTURANDO')

    def test_acepta_fijacion_estable_y_descarta_saltos_aislados(self):
        muestras = np.tile([.45, .52], (72, 1))
        muestras[:, 0] += .001*np.sin(np.arange(72))
        muestras[::18] = [.8, .8]
        resultado = completar(CapturaPunto(0.), muestras)
        np.testing.assert_allclose(resultado.posicion, [.45, .52], atol=.001)

    def test_acepta_ritmo_de_quince_fps(self):
        resultado = completar(CapturaPunto(0.), [[.4, .5]]*36)
        np.testing.assert_allclose(resultado.posicion, [.4, .5])

    def test_configuracion_angular_no_utiliza_umbrales_de_iris(self):
        captura = CapturaPunto(0., tolerancia=np.radians([3., 3.]), duracion=4.)
        muestras = [[.2+(-1)**i*.02, -.1] for i in range(40)]
        for muestra, tiempo in zip(muestras, np.linspace(.01, 3.99, 40)):
            captura.actualizar(muestra, captura.preparacion+tiempo)
        resultado = captura.actualizar(None, captura.preparacion+4.01)
        np.testing.assert_allclose(resultado.posicion, [.2, -.1])

    def test_pocas_muestras_no_se_aceptan(self):
        resultado = completar(CapturaPunto(0.), [[.4, .5]]*10)
        self.assertIsNone(resultado.posicion)
        self.assertIn('Pocas muestras', resultado.motivo)

    def test_perdida_frecuente_repite_punto(self):
        muestras = [None if i % 2 else [.4, .5] for i in range(72)]
        resultado = completar(CapturaPunto(0.), muestras)
        self.assertIsNone(resultado.posicion)
        self.assertIn('detección', resultado.motivo)

    def test_ruido_excesivo_no_se_acepta_por_tener_muchas_muestras(self):
        muestras = [[.4 + (-1)**i*.03, .5] for i in range(72)]
        resultado = completar(CapturaPunto(0.), muestras)
        self.assertIsNone(resultado.posicion)
        self.assertIn('inestable', resultado.motivo)

    def test_rafaga_corta_no_sustituye_fijacion(self):
        resultado = completar(CapturaPunto(0.), [[.4, .5]]*30, np.linspace(1., 1.3, 30))
        self.assertIsNone(resultado.posicion)
        self.assertIn('tiempo', resultado.motivo)

    def test_deriva_lenta_se_repite(self):
        muestras = np.column_stack((np.linspace(.39, .41, 72), np.full(72, .5)))
        resultado = completar(CapturaPunto(0.), muestras)
        self.assertIsNone(resultado.posicion)
        self.assertIn('cambió', resultado.motivo)

    def test_no_finitos_no_cuentan_como_validos(self):
        captura = CapturaPunto(0.)
        resultado = completar(captura, [[np.nan, .5]]*72)
        self.assertIsNone(resultado.posicion)
        self.assertEqual(len(captura.muestras), 0)

    def test_reintento_no_arrastra_muestras_anteriores(self):
        fallido = completar(CapturaPunto(0.), [[.8, .8]]*10)
        self.assertIsNone(fallido.posicion)
        captura = CapturaPunto(4.)
        resultado = completar(captura, [[.4, .5]]*72)
        np.testing.assert_allclose(resultado.posicion, [.4, .5])
        self.assertIs(captura.actualizar([.9, .9], 8.), resultado)


if __name__ == '__main__':
    unittest.main()
