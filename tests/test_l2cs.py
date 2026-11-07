import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

import main
from mirada.l2cs import PESOS, EstimadorL2CS, recortar_rostro, verificar_pesos


class RecorteL2CSTest(unittest.TestCase):
    def test_recorte_deshace_espejo_y_limita_bordes(self):
        frame = np.zeros((100, 100, 3), np.uint8)
        frame[:, :50] = [10, 20, 30]
        frame[:, 50:] = [100, 120, 130]
        puntos = [SimpleNamespace(x=0., y=0.), SimpleNamespace(x=1., y=1.)]*234
        rostro = SimpleNamespace(landmark=puntos)
        recorte = recortar_rostro(frame, [rostro])
        np.testing.assert_array_equal(recorte, cv2.flip(frame, 1))
        self.assertIsNone(recortar_rostro(frame, []))
        self.assertIsNone(recortar_rostro(frame, [rostro, rostro]))

    def test_checkpoint_incorrecto_y_ausente_no_se_cargan(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta)/'pesos.pkl'
            with self.assertRaises(FileNotFoundError):
                verificar_pesos(ruta)
            ruta.write_bytes(b'no es un checkpoint')
            with self.assertRaises(ValueError):
                verificar_pesos(ruta)

    def test_l2cs_sin_calibracion_se_rechaza_antes_de_abrir_camara(self):
        with patch('main.cv2.VideoCapture') as camara:
            with self.assertRaisesRegex(ValueError, 'produce ángulos'):
                main.ejecutar(SimpleNamespace(modo='mirada', estimador='l2cs', sin_calibracion=True))
            camara.assert_not_called()


@unittest.skipUnless(PESOS.is_file(), 'Pesos locales opcionales; ejecutar python -m mirada.recuperar_pesos.')
class InferenciaL2CSTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modelo = EstimadorL2CS()

    def test_preprocesa_rgb_y_normaliza_como_demo_original(self):
        imagen = np.full((80, 100, 3), [10, 20, 30], dtype=np.uint8)
        tensor = self.modelo.preparar(imagen)
        self.assertEqual(tuple(tensor.shape), (1, 3, 448, 448))
        esperado = (np.array([30, 20, 10])/255-[.485, .456, .406])/[.229, .224, .225]
        np.testing.assert_allclose(tensor[0, :, 100, 100].numpy(), esperado, atol=1e-6)

    def test_decodifica_ambas_cabezas_a_radianes_en_orden_original(self):
        import torch
        def salidas(tensor):
            a = torch.full((1, 90), -100.)
            b = a.clone()
            a[0, 45], b[0, 50] = 100., 100.
            return a, b
        with patch.object(self.modelo, 'modelo', side_effect=salidas):
            resultado = self.modelo.predecir(np.zeros((80, 80, 3), np.uint8))
        np.testing.assert_allclose(resultado, np.radians([0., 20.]), atol=1e-6)

    def test_inferencia_real_tiene_dos_angulos_finitos(self):
        resultado = self.modelo.predecir(np.zeros((180, 180, 3), np.uint8))
        self.assertEqual(resultado.shape, (2,))
        self.assertTrue(np.isfinite(resultado).all())
