"""Distribución espacial de segundos estimados sobre la publicidad original."""
import cv2
import numpy as np
from PIL import Image
from config import Config


class MapaCalor:
    def __init__(self, imagen, cfg=Config()):
        self.imagen, self.cfg = imagen.convert('RGB'), cfg
        self.ancho, self.alto = imagen.size
        escala = min(1., cfg.resolucion_calor_max/max(imagen.size))
        self.w, self.h = max(2, round(self.ancho*escala)), max(2, round(self.alto*escala))
        self.grid = np.zeros((self.h, self.w), np.float64)
        self.segundos = 0.
        self.interrumpir()

    def interrumpir(self):
        self.anterior = None

    def limpiar(self):
        self.grid.fill(0)
        self.segundos = 0.
        self.interrumpir()

    def depositar(self, punto, segundos):
        x, y = np.asarray(punto)*[self.w-1, self.h-1]
        sigma = max(1., min(self.w, self.h)*self.cfg.sigma_calor_rel)
        r = int(np.ceil(3*sigma))
        x0, x1 = max(0, int(x)-r), min(self.w, int(x)+r+2)
        y0, y1 = max(0, int(y)-r), min(self.h, int(y)+r+2)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        kernel = np.exp(-((xx-x)**2+(yy-y)**2)/(2*sigma**2))
        # Normalizar también en bordes conserva la suma temporal del mapa.
        self.grid[y0:y1, x0:x1] += segundos*kernel/kernel.sum()

    def agregar(self, punto, instante):
        if punto is None or not np.isfinite(punto).all() or ((np.asarray(punto) < 0) | (np.asarray(punto) > 1)).any():
            self.interrumpir()
            return 0.
        dt = 0.
        if self.anterior is not None:
            t0, p0 = self.anterior
            diferencia = instante-t0
            if 0 < diferencia <= self.cfg.hueco_max_s:
                dt = diferencia
                self.depositar(p0, dt/2)
                self.depositar(punto, dt/2)
                self.segundos += dt
        self.anterior = (instante, np.asarray(punto).copy())
        return dt

    def overlay(self):
        if not self.grid.any():
            return self.imagen.copy()
        nivel = cv2.resize(self.grid, (self.ancho, self.alto), interpolation=cv2.INTER_LINEAR)
        nivel /= nivel.max()
        color = cv2.cvtColor(cv2.applyColorMap((nivel*255).astype(np.uint8), cv2.COLORMAP_TURBO), cv2.COLOR_BGR2RGB)
        alpha = (.72*np.sqrt(nivel))[..., None]
        rgb = np.asarray(self.imagen)*(1-alpha)+color*alpha
        return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))

    def guardar(self, carpeta, prefijo):
        self.overlay().save(carpeta / f'{prefijo}.png')
        np.savez_compressed(carpeta / f'{prefijo}_datos.npz', segundos_por_celda=self.grid,
                            tamano_original=[self.ancho, self.alto], segundos=self.segundos,
                            sigma_rel=self.cfg.sigma_calor_rel)
