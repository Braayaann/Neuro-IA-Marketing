"""Adaptador local L2CS-Net/Gaze360. No convierte ángulos en píxeles por sí solo."""
import hashlib
from pathlib import Path

import cv2
import numpy as np

SHA256 = '8a7f3480d868dd48261e1d59f915b0ef0bb33ea12ea00938fb2168f212080665'
PESOS = Path(__file__).resolve().parent / 'pesos' / 'L2CSNet_gaze360.pkl'


def verificar_pesos(ruta=PESOS):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError('Faltan pesos L2CS. Ejecuta: python -m mirada.recuperar_pesos. '
                                'O utiliza --estimador iris.')
    with ruta.open('rb') as archivo:
        digest = hashlib.file_digest(archivo, 'sha256').hexdigest()
    if digest != SHA256:
        raise ValueError(f'Pesos L2CS distintos de la copia registrada. SHA256: {digest}')
    return ruta


def recortar_rostro(frame_reflejado, rostros):
    if len(rostros) != 1 or len(rostros[0].landmark) < 468:
        return None
    alto, ancho = frame_reflejado.shape[:2]
    puntos = np.array([(p.x*ancho, p.y*alto) for p in rostros[0].landmark[:468]])
    if not np.isfinite(puntos).all():
        return None
    minimo, maximo = puntos.min(axis=0), puntos.max(axis=0)
    margen = .1*(maximo-minimo)
    x1, y1 = np.maximum([0, 0], minimo-margen).astype(int)
    x2, y2 = np.minimum([ancho, alto], maximo+margen).astype(int)
    if min(x2-x1, y2-y1) < 60:
        return None
    # El resto del prototipo muestra espejo; el modelo recibe el rostro sin espejo.
    return cv2.flip(frame_reflejado[y1:y2, x1:x2], 1)


def crear_modelo():
    """Arquitectura equivalente a L2CS ResNet50, sin pesos ImageNet ni descargas.

    Adaptada con torchvision; procedencia y licencia en mirada/l2cs_autores/.
    Se conservan nombres de checkpoint, incluida la cabeza vestigial.
    """
    from torch import nn
    from torchvision.models.resnet import ResNet, Bottleneck

    class RedL2CS(ResNet):
        def __init__(self):
            super().__init__(Bottleneck, [3, 4, 6, 3])
            self.fc = nn.Identity()
            self.fc_yaw_gaze = nn.Linear(2048, 90)
            self.fc_pitch_gaze = nn.Linear(2048, 90)
            self.fc_finetune = nn.Linear(2051, 3)

        def forward(self, x):
            caracteristicas = super().forward(x)
            return self.fc_yaw_gaze(caracteristicas), self.fc_pitch_gaze(caracteristicas)

    return RedL2CS()


class EstimadorL2CS:
    def __init__(self, ruta=PESOS, dispositivo='cpu'):
        ruta = verificar_pesos(ruta)
        import torch
        from torchvision import transforms
        if dispositivo not in ('cpu', 'cuda'):
            raise ValueError('El dispositivo L2CS debe ser cpu o cuda.')
        if dispositivo == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA no está disponible en este entorno de PyTorch.')
        self.torch = torch
        self.dispositivo = torch.device(dispositivo)
        torch.set_num_threads(4)
        self.modelo = crear_modelo()
        pesos = torch.load(ruta, map_location='cpu', weights_only=True)
        self.modelo.load_state_dict(pesos, strict=True)
        self.modelo.to(self.dispositivo).eval()
        # Misma secuencia de la demo oficial: RGB 224 -> PIL -> 448 -> ImageNet.
        self.transformar = transforms.Compose([
            transforms.ToPILImage(), transforms.Resize(448), transforms.ToTensor(),
            transforms.Normalize([.485, .456, .406], [.229, .224, .225])])
        self.indices = torch.arange(90, dtype=torch.float32, device=self.dispositivo)

    def preparar(self, rostro_bgr):
        if rostro_bgr is None or rostro_bgr.size == 0 or rostro_bgr.ndim != 3 or rostro_bgr.shape[2] != 3 or rostro_bgr.dtype != np.uint8:
            raise ValueError('L2CS espera un recorte BGR uint8 de tres canales.')
        rgb = cv2.cvtColor(rostro_bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        return self.transformar(rgb).unsqueeze(0).to(self.dispositivo)

    def predecir(self, rostro_bgr):
        with self.torch.inference_mode():
            salidas = self.modelo(self.preparar(rostro_bgr))
            # Se conserva el orden de las dos cabezas del modelo original.
            angulos = [(salida.softmax(dim=1)*self.indices).sum(dim=1)*4-180 for salida in salidas]
            resultado = self.torch.stack(angulos, dim=1)[0].cpu().numpy()*np.pi/180
        if resultado.shape != (2,) or not np.isfinite(resultado).all():
            raise ValueError('L2CS produjo ángulos inválidos.')
        return resultado

    def estimar(self, frame_reflejado, rostros):
        recorte = recortar_rostro(frame_reflejado, rostros)
        return None if recorte is None else self.predecir(recorte)
