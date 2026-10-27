"""Resultados locales. Nunca guarda fotos ni video de la cámara."""
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def guardar_json(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


class Sesion:
    def __init__(self, base, metadata):
        self.carpeta = Path(base) / (datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
        self.carpeta.mkdir(parents=True)
        self.metadata = dict(creada_utc=datetime.now(timezone.utc).isoformat(), **metadata)
        self.archivo = (self.carpeta/'mirada.csv').open('w', newline='', encoding='utf-8')
        self.csv = csv.writer(self.archivo)
        self.csv.writerow(['utc', 'monotonic_s', 'calibracion', 'valida', 'motivo', 'x_raw_rel', 'y_raw_rel',
                           'x_suave_rel', 'y_suave_rel', 'x_original_px', 'y_original_px', 'dt_acumulado_s',
                           'deteccion_ms', 'estimacion_ms'])
        self.filas = 0
        self.eventos = []
        self.evento('sesion_creada')

    def evento(self, tipo, **datos):
        self.eventos.append(dict(utc=datetime.now(timezone.utc).isoformat(), tipo=tipo, **datos))
        self.guardar()

    def guardar(self):
        self.archivo.flush()
        guardar_json(self.carpeta/'sesion.json', dict(**self.metadata, filas_csv=self.filas, eventos=self.eventos))

    def agregar(self, t, calibracion, raw, suave, motivo, dimensiones, dt, deteccion_ms, estimacion_ms):
        x, y = raw if raw is not None else ('', '')
        sx, sy = suave if suave is not None else ('', '')
        px, py = (sx*(dimensiones[0]-1), sy*(dimensiones[1]-1)) if suave is not None else ('', '')
        self.csv.writerow([datetime.now(timezone.utc).isoformat(), t, calibracion, suave is not None,
                           motivo, x, y, sx, sy, px, py, dt, deteccion_ms, estimacion_ms])
        self.filas += 1
        if self.filas % 30 == 0:
            self.archivo.flush()

    def cerrar(self):
        self.guardar()
        self.archivo.close()
