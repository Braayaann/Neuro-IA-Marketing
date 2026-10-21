"""Regresiones geometricas y de evaluacion: sin webcam ni pesos."""
import math
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import json

from mirada.geometria import proyectar, region


class GeometriaTests(unittest.TestCase):
    def setUp(self):
        self.config = {'pantalla_cm': [40, 20], 'distancia_cm': 100,
                       'fov_horizontal_grados': 60, 'camara_sobre_pantalla_cm': 0}

    def test_rayos_a_objetivos_conocidos_en_ambas_mitades(self):
        for x, esperado in [(-10, 'A'), (10, 'B')]:
            horizontal = -math.atan2(x, 100)
            vertical = -math.atan2(10, math.sqrt(100**2 + x**2))
            punto = proyectar(horizontal, vertical, (640, 360), (1280, 720), self.config)
            self.assertAlmostEqual(punto[0], .25 if x < 0 else .75)
            self.assertAlmostEqual(punto[1], .5)
            self.assertEqual(region(punto), esperado)

    def test_no_forzar_miradas_fuera_de_pantalla_a_los_anuncios(self):
        self.assertEqual(region((-0.1, .5)), 'FUERA')
        self.assertEqual(region((.5, .5)), 'INDETERMINADA')
        self.assertIsNone(proyectar(math.pi, 0, (640, 360), (1280, 720), self.config))
        self.assertIsNone(proyectar(float('nan'), 0, (640, 360), (1280, 720), self.config))

    def test_posicion_del_observador_afecta_proyeccion(self):
        centro = proyectar(0, -.1, (640, 360), (1280, 720), self.config)
        desplazado = proyectar(0, -.1, (740, 360), (1280, 720), self.config)
        self.assertGreater(desplazado[0], centro[0])

    def test_rechazos_no_desaparecen_del_informe(self):
        from mirada import probar
        filas = [{'prueba': 0, 'prediccion': 'INDETERMINADA'} for _ in range(3)]
        filas.append({'prueba': 0, 'prediccion': 'A'})
        with TemporaryDirectory() as carpeta, patch.object(probar, 'BASE', Path(carpeta)):
            ruta, informe = probar.guardar_prueba(filas, self.config)
            self.assertEqual(informe['fraccion_asignada'], .25)
            self.assertFalse(informe['por_prueba'][0]['coincide'])
            self.assertEqual(informe['total_pruebas'], 8)
            json.loads(ruta.read_text())


if __name__ == '__main__':
    unittest.main()
