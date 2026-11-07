"""Señal binocular relativa a los ojos para la calibración de pantalla."""
import numpy as np

# Centro de iris, comisuras y párpados superior/inferior de FaceMesh refinado.
OJOS = ((468, 33, 133, 159, 145), (473, 362, 263, 386, 374))
CENTROS_IRIS = tuple(ojo[0] for ojo in OJOS)


def obtener_iris_por_ojo(rostros, tamano_frame):
    """Posiciones (x, y) de ambos iris; None si no son utilizables.

    tamano_frame es (ancho, alto). Los ejes se construyen en píxeles para
    respetar la relación de aspecto. Ambos ejes se normalizan por el ancho
    entre comisuras; y se centra en su punto medio con un desplazamiento .5.
    Los párpados solo se usan para comprobar la apertura mínima del ojo.
    La señal es relativa al ojo, no una coordenada de pantalla ni un ángulo.
    """
    if len(rostros) != 1 or len(rostros[0].landmark) < 478:
        return None
    dimensiones = np.asarray(tamano_frame, dtype=float)
    if dimensiones.shape != (2,) or not np.isfinite(dimensiones).all() or (dimensiones <= 0).any():
        return None
    puntos = rostros[0].landmark
    posiciones = []
    for indices in OJOS:
        xy = np.array([(puntos[i].x, puntos[i].y) for i in indices])
        if not np.isfinite(xy).all() or ((xy < 0) | (xy > 1)).any():
            return None
        iris, extremo1, extremo2, superior, inferior = xy * dimensiones
        izquierda, derecha = sorted((extremo1, extremo2), key=lambda p: p[0])
        eje_x = derecha - izquierda
        ancho = np.linalg.norm(eje_x)
        # En ojos de pocos píxeles un solo píxel domina el movimiento medido.
        if ancho < 8:
            return None
        eje_x /= ancho
        eje_y = np.array([-eje_x[1], eje_x[0]])
        apertura = (inferior - superior) @ eje_y
        # Conserva el umbral básico de apertura del prototipo para ambos ojos.
        if apertura < max(.004 * dimensiones[1], .08 * ancho):
            return None
        centro_ojo = (izquierda + derecha) / 2
        x = (iris - izquierda) @ eje_x / ancho
        margen = .06 * ancho
        if not 0 <= x <= 1 or (iris-superior) @ eje_y < -margen or (iris-inferior) @ eje_y > margen:
            return None
        posiciones.append([x, .5 + (iris - centro_ojo) @ eje_y / ancho])
    return np.asarray(posiciones)


def obtener_iris(rostros, tamano_frame):
    posiciones = obtener_iris_por_ojo(rostros, tamano_frame)
    return None if posiciones is None else posiciones.mean(axis=0)


class ConsistenciaBinocular:
    """Omite saltos aislados de disparidad, conservando movimientos conjuntos."""

    def __init__(self):
        self.anterior = None
        self.pendiente = None
        self.tiempo = None

    def aceptar(self, ojos, ahora):
        if ojos is None:
            self.anterior = self.pendiente = self.tiempo = None
            return False
        diferencia = ojos[0] - ojos[1]
        tolerancia = np.array([.035, .022])
        continuo = self.tiempo is not None and 0 < ahora-self.tiempo < .4
        self.tiempo = ahora
        if continuo and (np.abs(diferencia-self.anterior) > tolerancia).any():
            if self.pendiente is None or (np.abs(diferencia-self.pendiente) > tolerancia).any():
                self.pendiente = diferencia
                return False
        self.anterior, self.pendiente = diferencia, None
        return True
