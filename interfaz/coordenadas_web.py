"""Contrato: mirada en viewport CSS [0,1]; DPR solo pertenece al raster Canvas."""
import math

CLAVES = ('w', 'h', 'dpr', 'screenX', 'screenY', 'outerW', 'outerH', 'scrollX', 'scrollY', 'scale', 'offsetX', 'offsetY')


def validar_geometria(g):
    salida = {k: float(g[k]) for k in CLAVES}
    if not all(math.isfinite(v) for v in salida.values()):
        raise ValueError('Geometría no finita')
    if not 320 <= salida['w'] <= 10000 or not 240 <= salida['h'] <= 10000:
        raise ValueError('Viewport demasiado pequeño o inválido')
    if not .25 <= salida['dpr'] <= 8 or abs(salida['scale']-1) > .01:
        raise ValueError('Usa zoom de página normal; no zoom táctil/pinch durante la prueba')
    salida['rects'] = {}
    for nombre in ('moda', 'tecnologia', 'naturaleza', 'titulo'):
        r = [float(v) for v in g.get('rects', {}).get(nombre, [])]
        if len(r) == 4 and all(math.isfinite(v) for v in r) and r[2] > 0 and r[3] > 0:
            salida['rects'][nombre] = r
    return salida


def cambio(a, b):
    if a is None:
        return False
    return any(abs(a[k]-b[k]) > (0.001 if k in ('dpr', 'scale') else 1) for k in CLAVES) or a['rects'] != b['rects']


def normalizar(x, y, g):
    punto = [float(x)/(g['w']-1), float(y)/(g['h']-1)]
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in punto):
        raise ValueError('El objetivo no está dentro del viewport')
    return punto


def anclar(punto, g):
    x, y = punto[0]*(g['w']-1), punto[1]*(g['h']-1)
    for nombre, (rx, ry, rw, rh) in g['rects'].items():
        if rx <= x <= rx+rw-1 and ry <= y <= ry+rh-1:
            return nombre, [(x-rx)/max(1, rw-1), (y-ry)/max(1, rh-1)]
    return 'pagina', list(punto)
