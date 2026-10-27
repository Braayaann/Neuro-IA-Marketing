"""Verifica Python → posición CSS → DOM/Canvas sin cámara ni regresión."""
import uuid
import numpy as np


class PruebaDibujo:
    def __init__(self, geometria):
        self.g = geometria
        self.puntos = [(x,y) for y in (.1,.5,.9) for x in (.1,.5,.9)]
        self.filas = []
        self.nonce = uuid.uuid4().hex

    def objetivo(self):
        if len(self.filas) == len(self.puntos):
            return None
        p = self.puntos[len(self.filas)]
        return dict(nonce=self.nonce, indice=len(self.filas), total=len(self.puntos), normalizado=p,
                    css=[p[0]*(self.g['w']-1), p[1]*(self.g['h']-1)])

    def registrar(self, datos):
        o = self.objetivo()
        if not o or datos['nonce'] != self.nonce:
            raise ValueError('Confirmación de dibujo desfasada')
        dom, canvas = np.array(datos['dom'], float), np.array(datos['canvas'], float)
        if dom.shape != (2,) or canvas.shape != (2,) or not np.isfinite([dom,canvas]).all():
            raise ValueError('Medición de dibujo no válida')
        error_dom, error_canvas = dom-o['css'], canvas-o['css']
        self.filas.append(dict(punto=len(self.filas)+1, esperado_css=o['css'], dom_css=dom.tolist(),
            canvas_css=canvas.tolist(), error_dom=error_dom.tolist(), error_canvas=error_canvas.tolist()))
        self.nonce = uuid.uuid4().hex

    def reporte(self):
        if self.objetivo() is not None:
            return None
        dom = max(float(np.linalg.norm(s['error_dom'])) for s in self.filas)
        canvas = max(float(np.linalg.norm(s['error_canvas'])) for s in self.filas)
        return dict(cumple=bool(max(dom,canvas)<=1), tolerancia_css_px=1,
                    max_error_dom_px=dom, max_error_canvas_px=canvas, puntos=self.filas, geometria=self.g,
                    nota='Comprueba dibujo de coordenadas conocidas; NO mide precisión ocular.')
