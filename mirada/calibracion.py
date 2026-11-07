"""Ajuste de nueve objetivos a partir del iris de MediaPipe, sin modelo de cabeza."""
import numpy as np

OBJETIVOS = [(x, y) for y in (.12, .5, .88) for x in (.12, .5, .88)]
VALIDACION = [(.25, .25), (.75, .25), (.25, .75), (.75, .75), (.5, .65)]


class Calibracion:
    def __init__(self, metodo='lineal', regularizacion=.01):
        if metodo not in ('lineal', 'cuadratico') or not np.isfinite(regularizacion) or regularizacion <= 0:
            raise ValueError('Método inválido o regularización no positiva.')
        self.metodo = metodo
        self.regularizacion = regularizacion

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
        if self.metodo == 'lineal':
            self.coeficientes = np.linalg.lstsq(matriz, y, rcond=None)[0]
        else:
            penalizacion = np.eye(matriz.shape[1])*self.regularizacion
            penalizacion[0, 0] = 0.
            self.coeficientes = np.linalg.solve(matriz.T@matriz+penalizacion, matriz.T@y)
        return self

    def predecir(self, iris):
        x = np.asarray(iris, dtype=float)
        if x.shape != (2,) or not np.isfinite(x).all():
            raise ValueError('Se necesita una señal de mirada válida de dos valores.')
        return (self._matriz(x) @ self.coeficientes)[0]


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
    if 'cuadratico' not in metricas:
        return 'lineal'
    lineal = metricas['lineal']['error_medio_px']
    cuadratico = metricas['cuadratico']['error_medio_px']
    return 'cuadratico' if lineal-cuadratico >= max(5., .05*lineal) else 'lineal'
