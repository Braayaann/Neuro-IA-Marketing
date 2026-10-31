"""Adaptador del RMN original: mismas clases, arquitectura y preprocesamiento."""

import hashlib
from pathlib import Path

import cv2
import numpy as np

# Índices copiados de rmn.py. Sin tildes para cv2.putText (fuente Hershey).
CLASES = ('Enojo', 'Disgusto', 'Miedo', 'Alegria', 'Tristeza', 'Sorpresa', 'Neutral')
SHA256_ORIGINAL = '5bd51cff4ad2f4e5ee34fd9a1fb838ebac606e22bd85475947fd746b749efe87'


def verificar_checkpoint(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(
            f'Falta el checkpoint original RMN: {ruta}\n'
            'Para recuperar los pesos ejecuta: python -m emociones.recuperar_pesos. '
            'Para probar solo la mirada: python main.py --modo mirada'
        )
    with ruta.open('rb') as archivo:
        digest = hashlib.file_digest(archivo, 'sha256').hexdigest()
    if digest != SHA256_ORIGINAL:
        raise ValueError(f'El checkpoint RMN no coincide con el original. SHA256: {digest}')
    return ruta


def preprocesar(rostro):
    """Replica rmn.py: BGR uint8 → gris → 224² → 3 canales float32 / 255."""
    if rostro is None or rostro.size == 0:
        raise ValueError('El recorte del rostro está vacío.')
    if rostro.dtype != np.uint8 or rostro.ndim not in (2, 3):
        raise ValueError('RMN espera una imagen uint8 gris o BGR, sin normalizar.')
    if rostro.ndim == 3 and rostro.shape[2] != 3:
        raise ValueError('La imagen BGR debe tener tres canales.')
    # No convertir antes a RGB: los coeficientes de gris esperan BGR de OpenCV.
    gris = cv2.cvtColor(rostro, cv2.COLOR_BGR2GRAY) if rostro.ndim == 3 else rostro
    gris = cv2.resize(gris, (224, 224), interpolation=cv2.INTER_LINEAR)
    return np.repeat(gris[None, None], 3, axis=1).astype(np.float32) / 255.0


class ClasificadorRMN:
    def __init__(self, ruta, dispositivo='auto', hilos=4, lote=1):
        ruta = verificar_checkpoint(ruta)
        # Importación diferida: solo MediaPipe puede funcionar sin instalar torch.
        import torch
        from .rmn_autores.resmasking import resmasking, resmasking_dropout1

        if dispositivo not in ('auto', 'cpu', 'cuda'):
            raise ValueError('DISPOSITIVO_RMN debe ser auto, cpu o cuda.')
        if dispositivo == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA no está disponible en este entorno de PyTorch.')
        self.torch = torch
        self.dispositivo = torch.device(
            'cuda' if dispositivo == 'auto' and torch.cuda.is_available()
            else 'cpu' if dispositivo == 'auto' else dispositivo
        )
        self.lote = lote
        torch.set_num_threads(hilos)
        checkpoint = torch.load(ruta, map_location='cpu', weights_only=True)
        pesos = checkpoint.get('net', checkpoint)
        if all(k.startswith('module.') for k in pesos):
            pesos = {k.removeprefix('module.'): v for k, v in pesos.items()}
        if 'fc.1.weight' in pesos and pesos['fc.1.weight'].shape == (7, 512):
            self.modelo = resmasking_dropout1()
        elif 'fc.weight' in pesos and pesos['fc.weight'].shape == (7, 512):
            self.modelo = resmasking(in_channels=3, num_classes=7)
        else:
            raise ValueError('Arquitectura de checkpoint RMN no reconocida.')
        self.modelo.load_state_dict(pesos, strict=True)
        self.modelo.to(self.dispositivo).eval()

    def sincronizar(self):
        if self.dispositivo.type == 'cuda':
            self.torch.cuda.synchronize(self.dispositivo)

    def preparar(self, recortes):
        if not recortes:
            return None
        # NCHW, tres canales iguales. No aplicar Normalize ni dividir de nuevo.
        matriz = np.concatenate([preprocesar(rostro) for rostro in recortes], axis=0)
        return self.torch.from_numpy(matriz).to(self.dispositivo)

    def inferir(self, tensor):
        if tensor is None:
            return np.empty((0, 7), dtype=np.float32)
        if tensor.ndim != 4 or tuple(tensor.shape[1:]) != (3, 224, 224):
            raise ValueError('Forma de entrada RMN inválida: se espera N x 3 x 224 x 224.')
        with self.torch.inference_mode():
            # El lote por defecto es 1, como en el original. Es configurable.
            salidas = [self.modelo(parte).softmax(dim=1)
                       for parte in tensor.split(self.lote)]
            scores = self.torch.cat(salidas).cpu().numpy()
        if scores.shape != (len(tensor), 7) or not np.all(np.isfinite(scores)):
            raise ValueError('El modelo produjo una salida inválida.')
        return scores

    def predecir(self, rostro):
        return self.inferir(self.preparar([rostro]))[0]
