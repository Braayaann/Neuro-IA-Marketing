import unittest
from mirada.seguimiento import Seguimiento


class SeguimientoTests(unittest.TestCase):
    def test_tiempos_reales_y_perdida_de_cara(self):
        s = Seguimiento()
        for t in (0, .1, .25, .4):
            s.actualizar(t, (.25, .5), 'A')
        self.assertAlmostEqual(s.segundos['A'], .15)
        self.assertEqual(s.actualizar(.5, None, 'INDETERMINADA')[1], 'INDETERMINADA')
        self.assertAlmostEqual(s.segundos['A'], .15)
        s.actualizar(3.0, (.25, .5), 'A')
        self.assertAlmostEqual(s.segundos['A'], .15)
        self.assertAlmostEqual(sum(s.segundos.values()), 3.0)

    def test_ruido_breve_no_cambia_a_otro_anuncio(self):
        s = Seguimiento()
        for t in (0, .1, .25, .3):
            s.actualizar(t, (.25, .5), 'A')
        self.assertEqual(s.actualizar(.31, (.75, .5), 'B')[1], 'A')
        for t in (.5, .6, .8, 1.0):
            punto, estado = s.actualizar(t, (.75, .5), 'B')
        self.assertEqual(estado, 'B')

    def test_fuera_y_reinicio_no_ocultan_tiempo(self):
        s = Seguimiento()
        s.actualizar(0, None, 'FUERA')
        s.actualizar(.2, None, 'FUERA')
        self.assertEqual(s.resumen()['cobertura'], 0)
        self.assertAlmostEqual(s.segundos['FUERA'], .2)
        s.reiniciar()
        self.assertEqual(s.resumen()['total_segundos'], 0)


if __name__ == '__main__':
    unittest.main()
