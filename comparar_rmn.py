"""Comparar RMN del benchmark y RMN int8. Todo se procesa localmente."""
import argparse
import csv
import hashlib
import json
from pathlib import Path, PureWindowsPath
from time import perf_counter
from datetime import datetime

import cv2
import numpy as np
import onnxruntime as ort
import torch

BASE = Path(__file__).resolve().parent
CLASES = ['angry', 'disgusted', 'fearful', 'happy', 'sad', 'surprised', 'neutral']
ES = ['Enojo', 'Disgusto', 'Miedo', 'Alegria', 'Tristeza', 'Sorpresa', 'Neutral']
CLASES_PROYECTO = ['angry', 'disgusted', 'happy', 'neutral', 'sad', 'surprised']
SHA_ORIGINAL = '5bd51cff4ad2f4e5ee34fd9a1fb838ebac606e22bd85475947fd746b749efe87'

class ComparadorRMN:
    def __init__(self):
        from rmn_autores.resmasking import resmasking, resmasking_dropout1
        torch.set_num_threads(4)
        ruta = BASE / 'modelos' / 'rmn_benchmark' / 'resmasking_net.pth'
        with ruta.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != SHA_ORIGINAL:
                raise ValueError('El checkpoint no coincide con el original publicado.')
        # Cargar solo tensores y tipos básicos, sin deserialización arbitraria.
        checkpoint = torch.load(ruta, map_location='cpu', weights_only=True)
        pesos = checkpoint['net'] if 'net' in checkpoint else checkpoint
        if all(k.startswith('module.') for k in pesos):
            pesos = {k.removeprefix('module.'): v for k, v in pesos.items()}
        if 'fc.1.weight' in pesos and pesos['fc.1.weight'].shape == (7, 512):
            self.original = resmasking_dropout1()
        elif 'fc.weight' in pesos and pesos['fc.weight'].shape == (7, 512):
            self.original = resmasking(in_channels=3, num_classes=7)
        else:
            raise ValueError('La arquitectura del checkpoint no coincide con las variantes revisadas.')
        self.original.load_state_dict(pesos, strict=True)
        self.original.eval()
        self.metadata_checkpoint = {k: v for k, v in checkpoint.items()
            if k != 'net' and isinstance(v, (int, float, str, bool))}
        del pesos, checkpoint
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        self.cuantizada = ort.InferenceSession(str(BASE / 'modelos' / 'preentrenados' / 'resmasking_int8.onnx'),
            sess_options=opts, providers=['CPUExecutionProvider'])
        self.entrada = self.cuantizada.get_inputs()[0].name

    def predecir(self, rostro, version):
        # Mismo tensor en ambos motores. Sin TTA: una pasada por rostro.
        gris = cv2.cvtColor(rostro, cv2.COLOR_BGR2GRAY) if rostro.ndim == 3 else rostro
        gris = cv2.resize(gris, (224, 224), interpolation=cv2.INTER_LINEAR)
        tensor = np.repeat(gris[None, None], 3, axis=1).astype(np.float32) / 255.0
        if version == 'original':
            with torch.inference_mode():
                logits = self.original(torch.from_numpy(tensor)).numpy()[0]
        elif version == 'int8':
            logits = self.cuantizada.run(None, {self.entrada: tensor})[0].reshape(-1)
        else:
            raise ValueError(version)
        assert logits.shape == (7,) and np.all(np.isfinite(logits))
        scores = np.exp(logits - logits.max())
        return scores / scores.sum()

    def comparar(self):
        from sklearn.metrics import accuracy_score, f1_score, classification_report, ConfusionMatrixDisplay
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        division = np.load(BASE / 'modelos' / 'CNN_V2_20261013_192239_735567' / 'division_datos.npz', allow_pickle=False)
        rutas = [BASE / 'train' / PureWindowsPath(str(p)).parts[-2] / PureWindowsPath(str(p)).name for p in division['x_val']]
        reales = [CLASES_PROYECTO[int(i)] for i in division['y_val']]
        salida = BASE / 'resultados_preentrenados' / datetime.now().strftime('RMN_original_vs_int8_%Y%m%d_%H%M%S_%f')
        salida.mkdir(parents=True, exist_ok=False)
        self.ultima_salida = salida
        print('Comparación EXPLORATORIA sobre', len(rutas), 'imágenes. No reproduce el benchmark de FER2013.', flush=True)
        print('Salida:', salida, flush=True)
        filas = []
        for version in ('original', 'int8'):
            imagen = cv2.imread(str(rutas[0]), cv2.IMREAD_GRAYSCALE)
            for _ in range(3): self.predecir(imagen, version)
            pred, tiempos = [], []
            for i, ruta in enumerate(rutas):
                rostro = cv2.imread(str(ruta), cv2.IMREAD_GRAYSCALE)
                if rostro is None: raise ValueError(f'No se pudo leer: {ruta}')
                inicio = perf_counter()
                scores = self.predecir(rostro, version)
                tiempos.append((perf_counter() - inicio) * 1000)
                pred.append(CLASES[int(np.argmax(scores))])
                if (i+1) % 100 == 0: print(f'{version}: {i+1}/{len(rutas)}', flush=True)
            fila = {'version': version, 'accuracy': float(accuracy_score(reales, pred)),
                'macro_f1_seis_clases': float(f1_score(reales, pred, labels=CLASES_PROYECTO, average='macro', zero_division=0)),
                'predicciones_miedo': pred.count('fearful'), 'n': len(rutas), 'mediana_ms_cpu': float(np.median(tiempos))}
            filas.append(fila)
            print(json.dumps(fila), flush=True)
            reporte = classification_report(reales, pred, labels=CLASES_PROYECTO, digits=3, zero_division=0)
            (salida / f'{version}_reporte.txt').write_text(reporte, encoding='utf-8')
            with (salida / f'{version}_predicciones.csv').open('w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerow(['archivo', 'real', 'prediccion', 'ms'])
                w.writerows(zip(map(str, rutas), reales, pred, tiempos))
            fig, ax = plt.subplots(figsize=(9, 7))
            ConfusionMatrixDisplay.from_predictions(reales, pred, labels=CLASES, display_labels=CLASES,
                normalize='true', values_format='.2f', xticks_rotation=45, cmap='Blues', ax=ax)
            ax.set_title(f'RMN {version} — comparación exploratoria, sin TTA')
            fig.tight_layout()
            fig.savefig(salida / f'{version}_matriz.png', dpi=150)
            plt.close(fig)
        contexto = {'resultados': filas, 'checkpoint_original': 'benchmarks/resmasking_net',
            'sha256_original': SHA_ORIGINAL, 'metadata_checkpoint': self.metadata_checkpoint,
            'preprocesamiento': 'cv2 INTER_LINEAR, gris 224x224, tres canales idénticos, /255',
            'tta': False, 'dispositivo': 'CPU, 4 hilos por motor',
            'advertencia': 'Checkpoints distintos; posible solapamiento FER2013; no mide efecto aislado de cuantización ni reproduce test oficial.'}
        (salida / 'resultados.json').write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding='utf-8')
        with (salida / 'comparacion.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        print('COMPARACION_COMPLETA:', salida, flush=True)
        return filas

def detectar(frame):
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return detector.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='modo', required=True)
    sub.add_parser('comparar', help='Comparar ambos modelos en la validación guardada, sin tocar test.')
    foto = sub.add_parser('foto', help='Probar una foto local; --recortado si ya contiene solo una cara.')
    foto.add_argument('archivo', type=Path)
    foto.add_argument('--recortado', action='store_true')
    foto.add_argument('--version', choices=('original', 'int8', 'ambas'), default='ambas')
    camara = sub.add_parser('camara', help='Abrir cámara local y mostrar expresiones, sin grabar ni subir video.')
    camara.add_argument('--indice', type=int, default=0)
    camara.add_argument('--version', choices=('original', 'int8'), default='original')
    args = parser.parse_args()
    modelo = ComparadorRMN()
    if args.modo == 'comparar':
        modelo.comparar()
    elif args.modo == 'foto':
        imagen = cv2.imread(str(args.archivo))
        if imagen is None: raise FileNotFoundError(args.archivo)
        regiones = [(0, 0, imagen.shape[1], imagen.shape[0])] if args.recortado else detectar(imagen)
        if len(regiones) == 0: raise RuntimeError('No se detectaron caras. Si ya está recortada, utiliza --recortado.')
        for i, (x, y, w, h) in enumerate(regiones):
            for version in ('original', 'int8') if args.version == 'ambas' else (args.version,):
                scores = modelo.predecir(imagen[y:y+h, x:x+w], version)
                print('Rostro', i+1, version, '->', ES[int(scores.argmax())])
                print(dict(zip(ES, np.round(scores, 4).tolist())))
    else:
        captura = cv2.VideoCapture(args.indice)
        if not captura.isOpened(): raise RuntimeError('No se pudo abrir la cámara; revisa permisos e índice.')
        try:
            while True:
                ok, frame = captura.read()
                if not ok: break
                for x, y, w, h in detectar(frame):
                    scores = modelo.predecir(frame[y:y+h, x:x+w], args.version)
                    # La salida describe una expresión estimada; no el estado emocional interno.
                    texto = f'{ES[int(scores.argmax())]} ({args.version})'
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 200, 0), 2)
                    cv2.putText(frame, texto, (x, max(20, y-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)
                cv2.imshow('RMN - Q o ESC para salir', frame)
                if cv2.waitKey(1) & 0xFF in (27, ord('q')): break
        finally:
            captura.release()
            cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
