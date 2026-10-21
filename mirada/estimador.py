"""L2CS-Net con pesos verificados; Haar localiza cara y ojos en este prototipo."""
from pathlib import Path
import hashlib
import itertools
import cv2
import numpy as np
from PIL import Image
import torch
from torchvision.models.resnet import Bottleneck
from torchvision import transforms

from .descargar import SHA

BASE = Path(__file__).resolve().parent


class Estimador:
    def __init__(self):
        from .l2cs_autores.model import L2CS
        ruta = BASE / 'pesos' / 'L2CSNet_gaze360.pkl'
        with ruta.open('rb') as archivo:
            if hashlib.file_digest(archivo, 'sha256').hexdigest() != SHA:
                raise ValueError('El archivo L2CS no coincide con los pesos documentados.')
        torch.set_num_threads(4)
        self.modelo = L2CS(Bottleneck, [3, 4, 6, 3], 90)
        self.modelo.load_state_dict(torch.load(ruta, map_location='cpu', weights_only=True), strict=True)
        self.modelo.eval()
        self.indices = torch.arange(90, dtype=torch.float32)
        self.transformar = transforms.Compose([
            transforms.Resize(448), transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        self.caras = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.ojos = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye_tree_eyeglasses.xml')
        if self.caras.empty() or self.ojos.empty():
            raise RuntimeError('No se pudieron cargar los detectores de OpenCV.')

    def angulos(self, recorte):
        rgb = cv2.cvtColor(cv2.resize(recorte, (224, 224)), cv2.COLOR_BGR2RGB)
        tensor = self.transformar(Image.fromarray(rgb)).unsqueeze(0)
        with torch.inference_mode():
            primero, segundo = self.modelo(tensor)
            valores = [float((salida.softmax(1)[0] * self.indices).sum() * 4 - 180)
                       for salida in (primero, segundo)]
        if not np.isfinite(valores).all():
            raise ValueError('Salida de mirada no finita.')
        return tuple(np.deg2rad(valores))

    def procesar(self, frame):
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        caras = self.caras.detectMultiScale(gris, 1.1, 5, minSize=(60, 60))
        if len(caras) != 1:
            return {'estado': 'SIN CARA' if len(caras) == 0 else 'VARIAS PERSONAS'}
        x, y, ancho, alto = map(int, caras[0])
        recorte = frame[y:y+alto, x:x+ancho]
        ojos = self.ojos.detectMultiScale(gris[y:y+int(alto * .65), x:x+ancho], 1.1, 5, minSize=(10, 10))
        candidatos = []
        for e1, e2 in itertools.combinations(ojos, 2):
            c1 = (e1[0] + e1[2] / 2, e1[1] + e1[3] / 2)
            c2 = (e2[0] + e2[2] / 2, e2[1] + e2[3] / 2)
            if .2 * ancho < abs(c1[0] - c2[0]) < .8 * ancho and abs(c1[1] - c2[1]) < .2 * alto:
                candidatos.append((abs(c1[1] - c2[1]), ((c1[0]+c2[0])/2+x, (c1[1]+c2[1])/2+y)))
        if not candidatos:
            return {'estado': 'OJOS NO LOCALIZADOS', 'cara': (x, y, ancho, alto)}
        ojo = min(candidatos, key=lambda par: par[0])[1]
        horizontal, vertical = self.angulos(recorte)
        return {'estado': 'OK', 'cara': (x, y, ancho, alto), 'ojo': ojo,
                'horizontal': horizontal, 'vertical': vertical}
