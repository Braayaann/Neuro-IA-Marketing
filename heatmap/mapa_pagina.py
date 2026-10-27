"""Reutiliza kernels del mapa original; ancla las tarjetas al DOM al redimensionar."""
import io
import cv2
import numpy as np
from PIL import Image
from heatmap.generador_heatmap import MapaCalor
from interfaz.coordenadas_web import anclar
from config import Config


class MapaPagina:
    def __init__(self, cfg=Config()):
        self.cfg = cfg
        self.capas = {}
        self.segundos = 0.
        self.anterior = None
        self.revision = 0

    def interrumpir(self):
        self.anterior = None

    def limpiar(self):
        self.capas = {}
        self.segundos = 0.
        self.interrumpir()
        self.revision += 1

    def deposito(self, punto, dt, g):
        nombre, relativo = anclar(punto, g)
        if nombre not in self.capas:
            w, h = (g['w'], g['h']) if nombre == 'pagina' else g['rects'][nombre][2:]
            self.capas[nombre] = MapaCalor(Image.new('RGB', (max(2, round(w)), max(2, round(h)))), self.cfg)
        mapa = self.capas[nombre]
        mapa.depositar(relativo, dt)
        mapa.segundos += dt

    def agregar(self, punto, t, g):
        if punto is None or not np.isfinite(punto).all() or ((np.asarray(punto)<0)|(np.asarray(punto)>1)).any():
            self.interrumpir()
            return 0.
        dt = 0.
        if self.anterior:
            t0, p0 = self.anterior
            if 0 < t-t0 <= self.cfg.hueco_max_s:
                dt = t-t0
                self.deposito(p0, dt/2, g)
                self.deposito(punto, dt/2, g)
                self.segundos += dt
                self.revision += 1
        self.anterior = (t, list(punto))
        return dt

    def imagen(self, g):
        w, h = round(g['w']), round(g['h'])
        total = np.zeros((h, w), np.float32)
        for nombre, mapa in self.capas.items():
            r = [0, 0, w, h] if nombre == 'pagina' else g['rects'].get(nombre)
            if r is None:
                continue
            x, y, rw, rh = map(round, r)
            rw, rh = max(1, rw), max(1, rh)
            capa = cv2.resize(mapa.grid.astype(np.float32), (rw, rh))
            # Mantener densidad temporal al cambiar el número de píxeles de destino.
            capa *= mapa.grid.size/(rw*rh)
            x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x+rw), min(h, y+rh)
            if x1 > x0 and y1 > y0:
                total[y0:y1, x0:x1] += capa[y0-y:y1-y, x0-x:x1-x]
        nivel = total/max(float(total.max()), 1e-12)
        rgba = np.zeros((h, w, 4), np.uint8)
        rgba[..., 0] = 255
        rgba[..., 1] = (255*(1-nivel)).astype(np.uint8)
        rgba[..., 3] = (210*np.sqrt(nivel)).astype(np.uint8)
        return Image.fromarray(rgba, 'RGBA')

    def png(self, g):
        buf = io.BytesIO()
        self.imagen(g).save(buf, format='PNG')
        return buf.getvalue()

    def guardar(self, ruta, g, prefijo):
        (ruta/f'{prefijo}.png').write_bytes(self.png(g))
        np.savez_compressed(ruta/f'{prefijo}.npz', **{k: m.grid for k, m in self.capas.items()}, segundos=self.segundos)
