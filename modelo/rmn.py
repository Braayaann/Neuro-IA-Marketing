"""Clasificador RMN original: pruebas locales con una foto o cámara."""
import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np
import torch

BASE = Path(__file__).resolve().parent
CLASES = ['Enojo', 'Disgusto', 'Miedo', 'Alegria', 'Tristeza', 'Sorpresa', 'Neutral']
SHA256 = '5bd51cff4ad2f4e5ee34fd9a1fb838ebac606e22bd85475947fd746b749efe87'


class ClasificadorRMN:
    def __init__(self):
        from rmn_autores.resmasking import resmasking, resmasking_dropout1
        torch.set_num_threads(4)
        ruta = BASE / 'pesos' / 'resmasking_net.pth'
        with ruta.open('rb') as archivo:
            if hashlib.file_digest(archivo, 'sha256').hexdigest() != SHA256:
                raise ValueError('El checkpoint no coincide con el original publicado.')
        checkpoint = torch.load(ruta, map_location='cpu', weights_only=True)
        pesos = checkpoint.get('net', checkpoint)
        if all(k.startswith('module.') for k in pesos):
            pesos = {k.removeprefix('module.'): v for k, v in pesos.items()}
        if 'fc.1.weight' in pesos and pesos['fc.1.weight'].shape == (7, 512):
            self.modelo = resmasking_dropout1()
        elif 'fc.weight' in pesos and pesos['fc.weight'].shape == (7, 512):
            self.modelo = resmasking(in_channels=3, num_classes=7)
        else:
            raise ValueError('Arquitectura de checkpoint no reconocida.')
        self.modelo.load_state_dict(pesos, strict=True)
        self.modelo.eval()

    def predecir(self, rostro):
        if rostro is None or rostro.size == 0:
            raise ValueError('El recorte del rostro está vacío.')
        gris = cv2.cvtColor(rostro, cv2.COLOR_BGR2GRAY) if rostro.ndim == 3 else rostro
        gris = cv2.resize(gris, (224, 224), interpolation=cv2.INTER_LINEAR)
        tensor = np.repeat(gris[None, None], 3, axis=1).astype(np.float32) / 255.0
        with torch.inference_mode():
            scores = self.modelo(torch.from_numpy(tensor)).softmax(dim=1).numpy()[0]
        if scores.shape != (7,) or not np.all(np.isfinite(scores)):
            raise ValueError('El modelo produjo una salida inválida.')
        return scores


def crear_detector():
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if detector.empty():
        raise RuntimeError('No se pudo cargar el detector de rostros de OpenCV.')
    return detector


def detectar(detector, imagen):
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    return detector.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modos = parser.add_subparsers(dest='modo', required=True)
    foto = modos.add_parser('foto', help='Clasificar una foto local.')
    foto.add_argument('archivo', type=Path)
    foto.add_argument('--recortado', action='store_true', help='La foto ya contiene solo una cara.')
    camara = modos.add_parser('camara', help='Probar cámara local sin grabar ni subir video.')
    camara.add_argument('--indice', type=int, default=0)
    args = parser.parse_args()
    modelo = ClasificadorRMN()
    detector = crear_detector()
    if args.modo == 'foto':
        imagen = cv2.imread(str(args.archivo))
        if imagen is None:
            raise FileNotFoundError(args.archivo)
        regiones = [(0, 0, imagen.shape[1], imagen.shape[0])] if args.recortado else detectar(detector, imagen)
        if len(regiones) == 0:
            raise RuntimeError('No se detectaron caras. Usa --recortado solo si la foto ya es un rostro recortado.')
        for numero, (x, y, ancho, alto) in enumerate(regiones, start=1):
            scores = modelo.predecir(imagen[y:y+alto, x:x+ancho])
            print(f'Rostro {numero}: {CLASES[int(scores.argmax())]}')
            print(dict(zip(CLASES, np.round(scores, 4).tolist())))
        return
    captura = cv2.VideoCapture(args.indice)
    try:
        if not captura.isOpened():
            raise RuntimeError('No se pudo abrir la cámara. Revisa permisos e índice.')
        while True:
            correcto, imagen = captura.read()
            if not correcto:
                break
            for x, y, ancho, alto in detectar(detector, imagen):
                scores = modelo.predecir(imagen[y:y+alto, x:x+ancho])
                cv2.rectangle(imagen, (x, y), (x+ancho, y+alto), (0, 200, 0), 2)
                cv2.putText(imagen, CLASES[int(scores.argmax())], (x, max(20, y-8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)
            cv2.imshow('RMN - Q o ESC para salir', imagen)
            if cv2.waitKey(1) & 0xFF in (27, ord('q'), ord('Q')):
                break
            if cv2.getWindowProperty('RMN - Q o ESC para salir', cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        captura.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
