"""Señal binocular relativa a los ojos para la calibración de pantalla."""
import numpy as np

# Centro de iris, comisuras y párpados superior/inferior de FaceMesh refinado.
OJOS = ((468, 33, 133, 159, 145), (473, 362, 263, 386, 374))
CENTROS_IRIS = tuple(ojo[0] for ojo in OJOS)


def obtener_iris(rostros, tamano_frame):
    """Promedio (x, y) de ambos iris en sus ojos; None si no son utilizables.

    tamano_frame es (ancho, alto). Los ejes se construyen en píxeles para
    respetar la relación de aspecto: x entre comisuras, y entre párpados.
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
        if ancho < 1e-6:
            return None
        eje_x /= ancho
        eje_y = np.array([-eje_x[1], eje_x[0]])
        apertura = (inferior - superior) @ eje_y
        # Conserva el umbral básico de apertura del prototipo para ambos ojos.
        if apertura < .004 * dimensiones[1]:
            return None
        posiciones.append([(iris - izquierda) @ eje_x / ancho,
                           (iris - superior) @ eje_y / apertura])
    return np.mean(posiciones, axis=0)
