import io
import json
import unittest
from contextlib import redirect_stdout

import numpy as np

from mirada.diagnostico import ResumenTerminal, emitir


class DiagnosticoTest(unittest.TestCase):
    def test_limita_salida_y_reinicia_estadisticas_por_intervalo(self):
        salida = io.StringIO()
        resumen = ResumenTerminal(0.)
        with redirect_stdout(salida):
            resumen.actualizar(1., [.4, .5], postura=None)
            self.assertEqual(salida.getvalue(), '')
            resumen.actualizar(2., None, postura=None)
            resumen.actualizar(4., [.4, .5], postura=None)
        datos = [json.loads(linea.removeprefix('[NEURO] ')) for linea in salida.getvalue().splitlines()]
        self.assertEqual(len(datos), 2)
        self.assertEqual(datos[0]['validas_pct'], 50.)
        self.assertEqual(datos[1]['validas_pct'], 100.)
        self.assertIsNone(datos[0]['iris'])
        self.assertEqual(datos[1]['dispersion_iris'], [0., 0.])

    def test_arrays_y_unicode_se_pueden_copiar_como_json(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            emitir('prueba', datos=np.array([.5, .6]), motivo='detección')
        datos = json.loads(salida.getvalue().removeprefix('[NEURO] '))
        self.assertEqual(datos['datos'], [.5, .6])
        self.assertEqual(datos['motivo'], 'detección')
