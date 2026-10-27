"""Calibración supervisada y validación independiente, sin redes adicionales."""
import json
from collections import Counter
from dataclasses import asdict

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from config import Config


class CapturaPuntos:
    """La UI presenta el punto antes de iniciar su reloj de adquisición."""
    def __init__(self, puntos, cfg=Config()):
        self.puntos, self.cfg = puntos, cfg
        self.indice = 0
        self.inicio = None
        self.actuales, self.muestras = [], []
        self.intentos = 0
        self.rechazos = Counter()
        self.reintentos = 0
        self.diagnostico = []

    def presentar(self, instante):
        self.inicio = instante
        self.actuales = []
        self.intentos = 0
        self.rechazos = Counter()
        self.diagnostico = []

    def agregar(self, instante, obs):
        if self.inicio is None:
            return
        relativo = instante - self.inicio - self.cfg.espera_punto_s
        if not 0 <= relativo <= self.cfg.captura_punto_s:
            return
        self.intentos += 1
        self.diagnostico.append(dict(t=float(instante), valida=obs.valida, motivo=obs.motivo,
            aperturas=list(obs.aperturas), contexto=obs.contexto.tolist() if obs.contexto is not None else None,
            x=obs.caracteristicas.tolist() if obs.caracteristicas is not None else None))
        if not obs.valida:
            self.rechazos[obs.motivo] += 1
            return
        self.actuales.append(dict(t=float(instante), x=obs.caracteristicas.tolist(),
                                  contexto=obs.contexto.tolist(),
                                  objetivo=list(self.puntos[self.indice]), grupo=self.indice))

    def terminado(self, instante):
        return self.inicio is not None and instante-self.inicio >= self.cfg.espera_punto_s+self.cfg.captura_punto_s

    def aceptar(self):
        cantidad = len(self.actuales)
        cobertura = self.actuales[-1]['t']-self.actuales[0]['t'] if cantidad > 1 else 0
        bins = {min(2, int((s['t']-self.inicio-self.cfg.espera_punto_s)
                          / self.cfg.captura_punto_s*3)) for s in self.actuales}
        if cantidad < self.cfg.muestras_min_punto or cobertura < self.cfg.cobertura_min_punto_s or len(bins) < 3:
            self.reintentos += 1
            return False
        self.muestras.extend(self.actuales)
        self.indice += 1
        self.inicio = None
        return True


def pipeline(grado, alpha):
    return make_pipeline(StandardScaler(), PolynomialFeatures(grado, include_bias=False), Ridge(alpha=alpha))


class Calibrador:
    def __init__(self):
        self.modelo = None

    def ajustar(self, muestras, conjuntos=None):
        x = np.array([s['x'] for s in muestras], dtype=float)
        y = np.array([s['objetivo'] for s in muestras], dtype=float)
        grupos = np.array([s['grupo'] for s in muestras])
        unicos = np.unique(grupos)
        if len(unicos) != 9 or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError('Se necesitan los nueve puntos con características finitas')
        if min(np.sum(grupos == g) for g in unicos) < 3:
            raise ValueError('Faltan observaciones por punto')
        medias = np.array([x[grupos == g].mean(axis=0) for g in unicos])
        if np.max(np.std(medias[:, :4], axis=0)) < 0.002:
            raise ValueError('La señal ocular casi no varía entre puntos. Repite mirando cada objetivo.')
        # Igual número de observaciones por objetivo: no favorece al que tuvo más FPS.
        n = min(np.sum(grupos == g) for g in unicos)
        ids = np.concatenate([np.flatnonzero(grupos == g)[np.linspace(0, np.sum(grupos == g)-1, n).astype(int)] for g in unicos])
        x, y, grupos = x[ids], y[ids], grupos[ids]
        self.candidatos = []
        # Separar por objetivo evita que frames casi idénticos aparezcan en ambos lados.
        if conjuntos is None:
            # Referencia conservada: mismos candidatos que la versión web anterior.
            conjuntos = [('iris', list(range(4)))]
            if x.shape[1] >= 10:
                conjuntos += [('iris_parpados', list(range(8))), ('iris_parpados_pose', list(range(10)))]
        for nombre, columnas in conjuntos:
          for grado, alphas in ((1, (0.1, 1., 10.)), (2, (1., 10., 100.))):
            for alpha in alphas:
                errores = []
                for g in unicos:
                    train = grupos != g
                    m = pipeline(grado, alpha).fit(x[train][:, columnas], y[train])
                    errores.append(float(np.linalg.norm(m.predict(x[~train][:, columnas])-y[~train], axis=1).mean()))
                self.candidatos.append(dict(grado=grado, alpha=alpha, variables=nombre, columnas=columnas,
                                            error_cv=float(np.mean(errores))))
        mejor = min(self.candidatos, key=lambda c: c['error_cv'])
        cercanos = [c for c in self.candidatos if c['error_cv'] <= mejor['error_cv']*1.05+1e-10]
        self.elegido = min(cercanos, key=lambda c: (c['grado'], len(c['columnas']), c['error_cv']))
        self.columnas = self.elegido['columnas']
        self.modelo = pipeline(self.elegido['grado'], self.elegido['alpha']).fit(x[:, self.columnas], y)
        # Referencia de postura y rango ocular: limita extrapolaciones de la calibración.
        contexto = np.array([s['contexto'] for s in muestras])
        self.contexto_min = np.quantile(contexto, .05, axis=0)
        self.contexto_max = np.quantile(contexto, .95, axis=0)
        self.feature_min = np.quantile(x, .01, axis=0)
        self.feature_max = np.quantile(x, .99, axis=0)
        return self

    def predecir(self, features):
        if self.modelo is None:
            raise ValueError('No hay calibración')
        return self.modelo.predict(np.asarray(features, dtype=float).reshape(1, -1)[:, self.columnas])[0]

    def motivo_fuera_rango(self, obs):
        # No son probabilidades de confianza: son guardas geométricas explícitas.
        margen = np.array([.06, .06, max(self.contexto_max[2]*.20, .02), 10., 10., 10.])
        if ((obs.contexto < self.contexto_min-margen) | (obs.contexto > self.contexto_max+margen)).any():
            return 'postura_distinta_recalibrar'
        # Una variable descartada por la selección no debe bloquear la predicción.
        # Ejemplo: apertura menor al mirar abajo, pero aún por encima del parpadeo.
        columnas = self.columnas
        minimo, maximo = self.feature_min[columnas], self.feature_max[columnas]
        amplitud = np.maximum(maximo-minimo, .02)
        if ((obs.caracteristicas[columnas] < minimo-amplitud*.35) |
                (obs.caracteristicas[columnas] > maximo+amplitud*.35)).any():
            return 'caracteristicas_fuera_calibracion'
        return None

    def guardar(self, ruta, metadata):
        scaler, poly, ridge = self.modelo.steps[0][1], self.modelo.steps[1][1], self.modelo.steps[2][1]
        datos = dict(version=1, elegido=self.elegido, candidatos=self.candidatos,
                     media=scaler.mean_.tolist(), escala=scaler.scale_.tolist(),
                     potencias=poly.powers_.tolist(), coef=ridge.coef_.tolist(), intercepto=ridge.intercept_.tolist(),
                     contexto_min=self.contexto_min.tolist(), contexto_max=self.contexto_max.tolist(),
                     feature_min=self.feature_min.tolist(), feature_max=self.feature_max.tolist(), **metadata)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def evaluar(predicciones, objetivos, grupos, ancho, alto, intentos, cfg=Config(), puntos_esperados=5):
    """Métricas sobre predicciones CRUDAS: no ocultar errores con clipping/suavizado."""
    p, y = np.asarray(predicciones, float), np.asarray(objetivos, float)
    g = np.asarray(grupos)
    if len(p) == 0 or not np.isfinite(p).all():
        raise ValueError('No hay predicciones finitas para validar')
    error = np.linalg.norm((p-y)*[ancho-1, alto-1], axis=1)
    diagonal = np.hypot(ancho-1, alto-1)
    dentro = ((p >= 0) & (p <= 1)).all(axis=1)
    regiones_p = np.minimum(np.floor(p*3), 2)
    regiones_y = np.minimum(np.floor(y*3), 2)
    aciertos = dentro & (regiones_p == regiones_y).all(axis=1)
    por_punto = []
    for grupo in np.unique(g):
        sel = g == grupo
        dispersion = (p[sel]-p[sel].mean(axis=0))*[ancho-1, alto-1]
        delta = (p[sel]-y[sel])*[ancho-1, alto-1]
        objetivo = y[sel][0]
        zona = ('superior', 'central', 'inferior')[min(2, int(objetivo[1]*3))]
        por_punto.append(dict(punto=int(grupo+1), n=int(sel.sum()), zona=zona,
                              objetivo=objetivo.tolist(), estimado=p[sel].mean(axis=0).tolist(),
                              error_horizontal_px=float(np.abs(delta[:, 0]).mean()),
                              error_vertical_px=float(np.abs(delta[:, 1]).mean()),
                              sesgo_x_px=float(delta[:, 0].mean()), sesgo_y_px=float(delta[:, 1].mean()),
                              error_px=float(error[sel].mean()),
                              estabilidad_rms_px=float(np.sqrt(np.mean(np.sum(dispersion**2, axis=1)))),
                              acierto_region=float(aciertos[sel].mean())))
    # Promedio de objetivos con el mismo peso; no premiar puntos con más frames.
    medio = float(np.mean([v['error_px'] for v in por_punto]))
    regiones = float(np.mean([v['acierto_region'] for v in por_punto]))
    cobertura = len(p)/max(intentos, 1)
    por_zona = {}
    for zona in ('superior', 'central', 'inferior'):
        puntos = [v for v in por_punto if v['zona'] == zona]
        if puntos:
            por_zona[zona] = {k: float(np.mean([v[k] for v in puntos])) for k in
                ('error_px', 'error_horizontal_px', 'error_vertical_px', 'sesgo_x_px', 'sesgo_y_px',
                 'estabilidad_rms_px', 'acierto_region')}
            por_zona[zona]['muestras'] = sum(v['n'] for v in puntos)
    aprobado = (len(por_punto) == puntos_esperados and medio/diagonal <= cfg.error_validacion_max
                and regiones >= cfg.acierto_region_min and cobertura >= cfg.cobertura_validacion_min)
    return dict(error_px=medio, error_normalizado_diagonal=medio/diagonal,
                acierto_regiones=regiones, muestras_validas=len(p), intentos=int(intentos),
                cobertura=cobertura, estabilidad_rms_px=float(np.mean([v['estabilidad_rms_px'] for v in por_punto])),
                por_punto=por_punto, por_zona=por_zona,
                error_horizontal_px=float(np.mean([v['error_horizontal_px'] for v in por_punto])),
                error_vertical_px=float(np.mean([v['error_vertical_px'] for v in por_punto])),
                sesgo_x_px=float(np.mean([v['sesgo_x_px'] for v in por_punto])),
                sesgo_y_px=float(np.mean([v['sesgo_y_px'] for v in por_punto])),
                cumple_criterios=bool(aprobado), criterios=asdict(cfg),
                nota='Criterios exploratorios; no certifican exactitud ni fijaciones oculares.')
