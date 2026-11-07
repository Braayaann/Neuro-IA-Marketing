"""Ajuste de nueve objetivos a partir del iris de MediaPipe, sin modelo de cabeza."""
import numpy as np

OBJETIVOS = [(x, y) for y in (.12, .5, .88) for x in (.12, .5, .88)]
VALIDACION = [(.25, .25), (.75, .25), (.25, .75), (.75, .75), (.5, .65)]


class Calibracion:
    def __init__(self, metodo='lineal', regularizacion=.01):
        if metodo not in ('lineal', 'cuadratico', 'local') or not np.isfinite(regularizacion) or regularizacion <= 0:
            raise ValueError('Método inválido o regularización no positiva.')
        self.metodo = metodo
        self.regularizacion = regularizacion
        self.desplazamiento = np.zeros(2)

    def _matriz(self, iris):
        x, y = ((np.atleast_2d(iris)-self.media)/self.escala).T
        columnas = [np.ones(len(x)), x, y]
        if self.metodo == 'cuadratico':
            columnas += [x*x, x*y, y*y]
        return np.column_stack(columnas)

    def ajustar(self, iris, objetivos=OBJETIVOS):
        x = np.asarray(iris, dtype=float)
        y = np.asarray(objetivos, dtype=float)
        if x.shape != (9, 2) or y.shape != (9, 2) or not np.isfinite([x, y]).all():
            raise ValueError('Se necesitan nueve posiciones válidas.')
        self.media = x.mean(0)
        self.escala = x.std(0)
        if min(self.escala) < 1e-5:
            raise ValueError('El iris casi no varió: repite la calibración.')
        matriz = self._matriz(x)
        if np.linalg.matrix_rank(matriz) < matriz.shape[1]:
            raise ValueError('La calibración no cubre ambas direcciones.')
        if self.metodo != 'cuadratico':
            self.coeficientes = np.linalg.lstsq(matriz, y, rcond=None)[0]
        else:
            penalizacion = np.eye(matriz.shape[1])*self.regularizacion
            penalizacion[0, 0] = 0.
            self.coeficientes = np.linalg.solve(matriz.T@matriz+penalizacion, matriz.T@y)
        self.muestras = x.copy()
        if self.metodo == 'local':
            self.centros = matriz[:, 1:]
            self.residuos = y - matriz @ self.coeficientes
        return self

    def predecir(self, iris):
        x = np.asarray(iris, dtype=float)
        if x.shape != (2,) or not np.isfinite(x).all():
            raise ValueError('Se necesita una señal de mirada válida de dos valores.')
        matriz = self._matriz(x)
        prediccion = (matriz @ self.coeficientes)[0] + self.desplazamiento
        if self.metodo == 'local':
            distancia2 = ((self.centros-matriz[0, 1:])**2).sum(axis=1)
            pesos = np.exp(-distancia2 / (2 * .75**2))
            # El término constante atenúa la corrección lejos de la cuadrícula.
            prediccion += pesos @ self.residuos / (.15 + pesos.sum())
        return prediccion


def evaluar(modelo, muestras, objetivos, pantalla):
    predicciones = np.array([modelo.predecir(p) for p in muestras])
    diferencias = (predicciones-np.asarray(objetivos)) * (np.asarray(pantalla)-1)
    errores = np.linalg.norm(diferencias, axis=1)
    return dict(error_medio_px=float(errores.mean()), error_maximo_px=float(errores.max()),
                errores_px=errores, diferencias_px=diferencias)


def seleccionar_ajuste(metricas):
    """Prefiere el lineal salvo mejora cuadrática de al menos 5 px y 5%."""
    if 'lineal' not in metricas:
        return 'cuadratico'
    elegido = 'lineal'
    for nombre in ('cuadratico', 'local'):
        if nombre not in metricas:
            continue
        actual, nuevo = metricas[elegido], metricas[nombre]
        media = actual['error_medio_px']
        if (media-nuevo['error_medio_px'] >= max(5., .05*media)
                and nuevo.get('error_maximo_px', 0) <= actual.get('error_maximo_px', 0) + 5):
            elegido = nombre
    return elegido
