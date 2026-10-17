"""Inferencia local: MobileNet/AffectNet (Keras) y RMN int8 (ONNX)."""
from pathlib import Path
import json
import hashlib
from time import perf_counter
import numpy as np
from PIL import Image, ImageOps

CLASES = ['angry', 'disgusted', 'happy', 'neutral', 'sad', 'surprised']
SALIDAS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised']

class Clasificadores:
    def __init__(self, base):
        from tensorflow import keras
        import onnxruntime as ort
        self.base = Path(base)
        pesos = self.base / 'modelos' / 'preentrenados'
        self.mobile = keras.models.load_model(pesos / 'mobilenet_7.h5', compile=False)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        self.rmn = ort.InferenceSession(str(pesos / 'resmasking_int8.onnx'),
            sess_options=opts, providers=['CPUExecutionProvider'])
        self.rmn_input = self.rmn.get_inputs()[0].name
        assert self.mobile.input_shape[1:] == (224, 224, 3)
        assert self.mobile.output_shape[-1] == 7

    def predecir(self, imagen, nombre):
        # Se espera una cara ya recortada, no un cuadro completo de la cámara.
        rgb = ImageOps.exif_transpose(imagen).convert('RGB')
        if nombre == 'MobileNet':
            x = np.array(rgb.resize((224, 224), Image.Resampling.BILINEAR), dtype=np.float32)
            # Preprocesamiento del notebook oficial de EmotiEffLib: RGB menos estas medias.
            x -= np.array([103.939, 116.779, 123.68], dtype=np.float32)
            scores = np.asarray(self.mobile([x[None]], training=False))[0]
        elif nombre == 'RMN_int8':
            gris = np.array(rgb.convert('L').resize((224, 224), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
            x = np.repeat(gris[None, None], 3, axis=1)
            logits = np.asarray(self.rmn.run(None, {self.rmn_input: x})[0]).reshape(-1)
            scores = np.exp(logits - logits.max())
            scores /= scores.sum()
            # RMN: angry, disgust, fear, happy, sad, surprise, neutral.
            scores = scores[[0, 1, 2, 3, 6, 4, 5]]
        else:
            raise ValueError(nombre)
        if scores.shape != (7,) or not np.all(np.isfinite(scores)):
            raise ValueError(f'Salida inválida de {nombre}: {scores}')
        return scores

    def evaluar(self, rutas, reales, salida, contexto):
        from sklearn.metrics import accuracy_score, f1_score, classification_report, ConfusionMatrixDisplay
        import matplotlib.pyplot as plt
        import csv
        salida = Path(salida)
        salida.mkdir(parents=True, exist_ok=True)
        resultados = []
        for nombre in ('MobileNet', 'RMN_int8'):
            # Calentar ambos motores; la descarga/carga no forma parte de la latencia.
            with Image.open(rutas[0]) as img:
                for _ in range(3): self.predecir(img, nombre)
            pred, tiempos = [], []
            for i, ruta in enumerate(rutas):
                with Image.open(ruta) as img:
                    img.load()
                    inicio = perf_counter()
                    scores = self.predecir(img, nombre)
                    tiempos.append((perf_counter() - inicio) * 1000)
                pred.append(SALIDAS[int(np.argmax(scores))])
                if (i+1) % 100 == 0: print(f'{nombre}: {i+1}/{len(rutas)}', flush=True)
            texto = classification_report(reales, pred, labels=CLASES, digits=3, zero_division=0)
            fila = {'modelo': nombre, 'accuracy': float(accuracy_score(reales, pred)),
                'macro_f1_6_clases': float(f1_score(reales, pred, labels=CLASES, average='macro', zero_division=0)),
                'predicciones_miedo': pred.count('fearful'), 'imagenes': len(rutas),
                'mediana_ms_por_rostro': float(np.median(tiempos)), 'contexto': contexto}
            print(json.dumps(fila, ensure_ascii=False), flush=True)
            print(texto, flush=True)
            (salida / (nombre + '_reporte.txt')).write_text(texto, encoding='utf-8')
            with (salida / (nombre + '_predicciones.csv')).open('w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerow(['archivo', 'real', 'prediccion', 'ms'])
                w.writerows(zip(map(str, rutas), reales, pred, tiempos))
            fig, ax = plt.subplots(figsize=(9, 7))
            ConfusionMatrixDisplay.from_predictions(reales, pred, labels=SALIDAS, display_labels=SALIDAS,
                normalize='true', values_format='.2f', cmap='Blues', xticks_rotation=45, ax=ax)
            ax.set(title=f'{nombre} — {contexto}', xlabel='Predicción', ylabel='Clase real')
            fig.tight_layout()
            fig.savefig(salida / (nombre + '_matriz.png'), dpi=150)
            plt.show()
            plt.close(fig)
            resultados.append(fila)
        (salida / 'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding='utf-8')
        with (salida / 'comparacion.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(resultados[0]))
            w.writeheader()
            w.writerows(resultados)
        return resultados

def registrar_pesos(base):
    carpeta = Path(base) / 'modelos' / 'preentrenados'
    fuentes = {
        'mobilenet_7.h5': 'https://github.com/sb-ai-lab/EmotiEffLib',
        'resmasking_int8.onnx': 'https://huggingface.co/phamquiluan/ResidualMaskingNetwork',
    }
    registro = []
    for nombre, fuente in fuentes.items():
        p = carpeta / nombre
        with p.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        registro.append({'archivo': nombre, 'fuente': fuente, 'bytes': p.stat().st_size,
            'sha256': digest})
    (carpeta / 'procedencia.json').write_text(json.dumps(registro, indent=2), encoding='utf-8')
    return registro
