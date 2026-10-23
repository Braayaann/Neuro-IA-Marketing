"""Contrato de camara compartida y liberacion, sin dispositivos fisicos."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import numpy as np
import main
from mirada import probar


class AplicacionUnificadaTests(unittest.TestCase):
    def test_ambos_modelos_reciben_el_mismo_frame_y_una_sola_camara(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        camara = Mock()
        camara.read.return_value = (True, frame)
        estimador = Mock()
        estimador.procesar.return_value = {'estado': 'SIN CARA'}
        emociones = Mock()
        emociones.procesar.return_value = 'Sin rostro'
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta)/'resumen.json'
            with patch.object(probar, 'Estimador', return_value=estimador), \
                 patch.object(probar.cv2, 'VideoCapture', return_value=camara) as captura, \
                 patch.object(probar.cv2, 'namedWindow') as ventana, \
                 patch('emociones.sesion.SesionEmociones', return_value=emociones):
                codigo = main.main(['--sin-ventana', '--max-fotogramas', '2',
                                    '--mediciones', str(ruta)])
            self.assertEqual(codigo, 0)
            captura.assert_called_once()
            ventana.assert_not_called()
            emociones.abrir.assert_called_once()
            emociones.cerrar.assert_called_once()
            camara.release.assert_called_once()
            self.assertEqual(estimador.procesar.call_count, 2)
            self.assertEqual(emociones.procesar.call_count, 2)
            self.assertTrue(all(llamada.args[0] is frame for llamada in estimador.procesar.call_args_list))
            self.assertTrue(all(llamada.args[0] is frame for llamada in emociones.procesar.call_args_list))
            self.assertIn('resumen', json.loads(ruta.read_text(encoding='utf-8')))

    def test_error_lectura_libera_ambos_recursos(self):
        camara = Mock()
        camara.read.return_value = (False, None)
        emociones = Mock()
        with patch.object(probar, 'Estimador'), \
             patch.object(probar.cv2, 'VideoCapture', return_value=camara), \
             patch('emociones.sesion.SesionEmociones', return_value=emociones):
            self.assertEqual(main.main(['--sin-ventana', '--max-fotogramas', '1']), 1)
        emociones.cerrar.assert_called_once()
        camara.release.assert_called_once()

    def test_modo_emociones_conserva_opciones_originales(self):
        with patch('emociones.aplicacion.main', return_value=0) as ejecutar:
            self.assertEqual(main.main(['--modo','emociones','--max-fotogramas','1']), 0)
        ejecutar.assert_called_once_with(['--max-fotogramas','1'])

    def test_errores_de_carga_no_abren_camara(self):
        with patch.object(probar, 'Estimador', side_effect=FileNotFoundError('Faltan pesos')), \
             patch.object(probar.cv2, 'VideoCapture') as captura:
            self.assertEqual(main.main(['--modo', 'mirada']), 1)
        captura.assert_not_called()


if __name__ == '__main__':
    unittest.main()
