"""Pruebas de contrato y errores. No requieren cámara ni checkpoint."""

import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
import torch

import config
import main
from emociones.rmn_detector import CLASES, ClasificadorRMN, preprocesar, verificar_checkpoint
from utilidades.procesamiento_imagen import GuardadorRecortes, extraer_rostro, preparar_rostros
from validar_integracion import cargar_original, emparejar


def landmarks(x1=0.3, y1=0.25, x2=0.6, y2=0.7):
    puntos = [SimpleNamespace(x=(x1+x2)/2, y=(y1+y2)/2, z=0) for _ in range(478)]
    puntos[0] = SimpleNamespace(x=x1, y=y1, z=0)
    puntos[2] = SimpleNamespace(x=x2, y=y2, z=0)
    return puntos


class RedDeContrato(torch.nn.Module):
    """Doble explícito para probar cableado; NO representa predicciones de RMN."""
    def __init__(self):
        super().__init__()
        self.entradas = []

    def forward(self, tensor):
        assert torch.is_inference_mode_enabled()
        self.entradas.append(tensor.clone())
        return tensor.mean(dim=(1, 2, 3))[:, None] * torch.arange(7)[None, :]


def adaptador_de_prueba(lote=1):
    adaptador = ClasificadorRMN.__new__(ClasificadorRMN)
    adaptador.modelo = RedDeContrato().eval()
    adaptador.torch = torch
    adaptador.dispositivo = torch.device('cpu')
    adaptador.lote = lote
    return adaptador


class Preprocesamiento(unittest.TestCase):
    def test_igualdad_exacta_con_codigo_original(self):
        modulo = cargar_original()
        self.assertEqual(tuple(modulo.CLASES), CLASES)
        original = modulo.ClasificadorRMN.__new__(modulo.ClasificadorRMN)
        original.modelo = RedDeContrato().eval()
        adaptador = adaptador_de_prueba()
        rng = np.random.default_rng(42)
        for forma in [(71, 95, 3), (224, 224, 3), (73, 52)]:
            rostro = rng.integers(0, 256, forma, dtype=np.uint8)
            esperado = original.predecir(rostro)
            recibido = adaptador.predecir(rostro)
            np.testing.assert_array_equal(original.modelo.entradas[-1].numpy(), preprocesar(rostro))
            np.testing.assert_array_equal(esperado, recibido)

    def test_bgr_y_escala_sin_doble_normalizacion(self):
        bgr = np.full((10, 10, 3), [255, 0, 0], dtype=np.uint8)
        tensor = preprocesar(bgr)
        self.assertEqual(tensor.shape, (1, 3, 224, 224))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertAlmostEqual(float(tensor[0, 0, 0, 0]), 29 / 255, places=7)
        np.testing.assert_array_equal(tensor[:, 0], tensor[:, 2])

    def test_entradas_invalidas(self):
        for rostro in (None, np.empty((0, 0, 3), np.uint8), np.ones((20, 20, 3), np.float32),
                       np.ones((20, 20, 4), np.uint8)):
            with self.assertRaises(ValueError):
                preprocesar(rostro)

    def test_lotes_y_orden(self):
        imagenes = [np.full((60, 60, 3), color, np.uint8) for color in (20, 180, 70)]
        modelo = adaptador_de_prueba(lote=2)
        salida = modelo.inferir(modelo.preparar(imagenes))
        esperado = np.array([modelo.predecir(imagen) for imagen in imagenes])
        # Una reducción vectorizada float32 puede diferir unos ulp según el lote.
        np.testing.assert_allclose(salida, esperado, rtol=1e-5, atol=1e-6)
        self.assertEqual(modelo.inferir(None).shape, (0, 7))

    def test_checkpoint_ausente_y_distinto(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'resmasking_net.pth'
            with self.assertRaises(FileNotFoundError):
                verificar_checkpoint(ruta)
            ruta.write_bytes(b'No son pesos originales')
            with self.assertRaisesRegex(ValueError, 'no coincide'):
                verificar_checkpoint(ruta)


class Recortes(unittest.TestCase):
    def setUp(self):
        self.imagen = np.random.default_rng(1).integers(0, 256, (480, 640, 3), dtype=np.uint8)

    def test_cuadrado_y_pixeles_originales(self):
        r = extraer_rostro(self.imagen, landmarks())
        self.assertEqual(r.motivo, '')
        x1, y1, x2, y2 = r.caja
        self.assertEqual(x2-x1, y2-y1)
        self.assertGreater(x2-x1, 0.45 * 480)
        np.testing.assert_array_equal(r.imagen, self.imagen[y1:y2, x1:x2])

    def test_borde_sin_estirar_ni_rellenar(self):
        r = extraer_rostro(self.imagen, landmarks(0, 0.2, 0.2, 0.5))
        self.assertIsNotNone(r.imagen)
        self.assertEqual(r.caja[0], 0)
        self.assertEqual(r.imagen.shape[0], r.imagen.shape[1])

    def test_invalidos_pequenos_y_parciales(self):
        self.assertEqual(extraer_rostro(self.imagen, []).motivo, 'landmarks incompletos')
        self.assertEqual(extraer_rostro(self.imagen, landmarks(.4, .4, .41, .41)).motivo, 'rostro pequeno')
        puntos = landmarks()
        puntos[33].x = -0.1
        self.assertEqual(extraer_rostro(self.imagen, puntos).motivo, 'rostro parcial')
        puntos[33].x = float('nan')
        self.assertEqual(extraer_rostro(self.imagen, puntos).motivo, 'coordenadas invalidas')
        self.assertEqual(extraer_rostro(self.imagen, landmarks(-.3, .2, .3, .7)).motivo, 'rostro parcial')
        self.assertEqual(extraer_rostro(self.imagen, landmarks(0, 0, .99, .99)).motivo,
                         'sin espacio para recorte')

    def test_indices_preservados_al_descartar_rostro(self):
        recortes, indices, imagenes = preparar_rostros(self.imagen, [landmarks(), [], landmarks(.6,.2,.8,.6)])
        self.assertEqual(indices, [0, 2])
        self.assertEqual(len(imagenes), 2)
        self.assertEqual(recortes[1].motivo, 'landmarks incompletos')

    def test_no_guardar_por_defecto_y_limite_optativo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            recortes, indices, _ = preparar_rostros(self.imagen, [landmarks(), landmarks()])
            apagado = GuardadorRecortes(False, carpeta)
            apagado.guardar(0, recortes, indices)
            self.assertEqual(list(Path(carpeta).iterdir()), [])
            activo = GuardadorRecortes(True, carpeta, maximo=1, intervalo=2)
            activo.guardar(1, recortes, indices)
            self.assertEqual(list(Path(carpeta).iterdir()), [])
            activo.guardar(2, recortes, indices)
            activo.guardar(4, recortes, indices)
            self.assertEqual(len(list(Path(carpeta).rglob('*.png'))), 1)
            tensor = np.load(next(Path(carpeta).rglob('*.npy')))
            np.testing.assert_array_equal(tensor, preprocesar(recortes[0].imagen))

    def test_parejas_por_geometria_y_ambiguedad(self):
        a, b = (0, 0, 100, 100), (200, 0, 300, 100)
        self.assertEqual([(i, j) for i, j, _ in emparejar([a, b], [b, a])], [(0, 1), (1, 0)])
        self.assertEqual(emparejar([a], [a, a]), [])


class FlujoVideo(unittest.TestCase):
    def test_timestamp_teclas_y_asociacion(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[:, 320:] = 200
        a, b = landmarks(.1,.2,.4,.6), landmarks(.55,.2,.85,.6)
        camara = Mock()
        camara.read.return_value = (True, frame)
        modelo = adaptador_de_prueba()
        resultado = SimpleNamespace(face_landmarks=[a, [], b])
        # La cara inválida no llega a dibujar: aquí se sustituye solo la visualización.
        with patch.object(main, 'detectar_rostros', return_value=resultado) as detectar, \
             patch.object(main, 'dibujar_rostros') as dibujar, \
             patch.object(main.cv2, 'namedWindow'), patch.object(main.cv2, 'imshow'), \
             patch.object(main.cv2, 'getWindowProperty', return_value=1), \
             patch.object(main.cv2, 'waitKey', side_effect=[ord('m'), ord('r'), ord('q')]), \
             patch.object(main.time, 'monotonic_ns', return_value=100):
            main.ejecutar_video(Mock(), camara, modelo)
        self.assertEqual([c.args[2] for c in detectar.call_args_list], [0, 1, 2])
        self.assertEqual([c.args[2] for c in dibujar.call_args_list], [True, False, False])
        etiquetas = dibujar.call_args_list[0].args[3]
        self.assertTrue(etiquetas[0].startswith('Enojo'))
        self.assertEqual(etiquetas[1], 'landmarks incompletos')
        self.assertTrue(etiquetas[2].startswith('Neutral'))
        self.assertEqual(dibujar.call_args_list[2].args[3], ['RMN OFF'] * 3)
        self.assertEqual(len(modelo.modelo.entradas), 4)  # 2 rostros x 2 fotogramas
        self.assertTrue(np.all(frame[:, :320] == 0))

    def test_cambio_de_orden_no_reutiliza_etiquetas(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[:, 320:] = 200
        a, b = landmarks(.1,.2,.4,.6), landmarks(.55,.2,.85,.6)
        modelo = adaptador_de_prueba()
        for puntos, esperados in [([a, b], [0, 6]), ([b, a], [6, 0])]:
            _, indices, crops = preparar_rostros(frame, puntos)
            self.assertEqual(indices, [0, 1])
            self.assertEqual(modelo.inferir(modelo.preparar(crops)).argmax(axis=1).tolist(), esperados)

    def test_fotograma_sin_rostros_no_infiere(self):
        camara = Mock()
        camara.read.return_value = (True, np.zeros((480, 640, 3), np.uint8))
        modelo = adaptador_de_prueba()
        with patch.object(main, 'detectar_rostros', return_value=SimpleNamespace(face_landmarks=[])):
            main.ejecutar_video(Mock(), camara, modelo, 1, True)
        self.assertEqual(modelo.modelo.entradas, [])

    def test_reduccion_rgb_y_coordenadas_originales(self):
        frame = np.full((480, 640, 3), [255, 20, 10], np.uint8)
        detector = Mock()
        with patch.object(config, 'ANCHO_PROCESAMIENTO', 320):
            main.detectar_rostros(detector, frame, 123)
        imagen, timestamp = detector.detect_for_video.call_args.args
        self.assertEqual(timestamp, 123)
        self.assertEqual(imagen.numpy_view().shape, (240, 320, 3))
        np.testing.assert_array_equal(imagen.numpy_view()[0, 0], [10, 20, 255])
        puntos, caja = main.obtener_puntos_y_limites(landmarks(), 640, 480)
        self.assertEqual(caja, (192, 120, 384, 336))

    def test_camara_no_abre_y_se_libera(self):
        camara = Mock()
        camara.isOpened.return_value = False
        with patch.object(main.cv2, 'VideoCapture', return_value=camara):
            with self.assertRaises(RuntimeError):
                main.abrir_camara()
        camara.release.assert_called_once()

    def test_error_captura_libera_camara_y_detector(self):
        camara = Mock()
        camara.read.return_value = (False, None)
        contexto = unittest.mock.MagicMock()
        with patch.object(main, 'crear_detector', return_value=contexto), \
             patch.object(main, 'abrir_camara', return_value=camara), \
             patch.object(main.cv2, 'destroyAllWindows') as cerrar:
            codigo = main.main(['--solo-mediapipe', '--sin-ventana', '--max-fotogramas', '1'])
        self.assertEqual(codigo, 1)
        camara.release.assert_called_once()
        contexto.__exit__.assert_called_once()
        cerrar.assert_called_once()

    def test_modelos_ausentes_antes_de_abrir_camara(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre, args in [('RUTA_MODELO', ['--solo-mediapipe']), ('RUTA_RMN', [])]:
                with patch.object(config, nombre, Path(carpeta)/'ausente'), \
                     patch.object(main, 'abrir_camara') as abrir:
                    self.assertEqual(main.main(args), 1)
                    abrir.assert_not_called()


if __name__ == '__main__':
    unittest.main()
