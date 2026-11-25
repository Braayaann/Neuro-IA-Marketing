"""Tiempos por cuadrante derivados de las observaciones de una sesión."""

import math


QUADRANTS = (
    ('top_left', 'Superior izquierdo'),
    ('top_right', 'Superior derecho'),
    ('bottom_left', 'Inferior izquierdo'),
    ('bottom_right', 'Inferior derecho'),
)


def quadrant_times(observations, slots):
    """Recibe todas las muestras en orden de secuencia, incluidas las inválidas.

    Las coordenadas están normalizadas respecto al área de exhibición completa.
    Cada anuncio ocupa una celda: una pantalla, dos columnas o una grilla 2x2.
    Los puntos sobre la mitad pertenecen a la derecha o a la parte inferior.
    """
    columns = 1 if len(slots) == 1 else 2
    rows = 2 if len(slots) > 2 else 1
    positions = {slot.id: slot.position for slot in slots}
    totals = {slot.id: [0.0] * 4 for slot in slots}
    previous = None
    previous_zone = None

    for observation in observations:
        zone = None
        if (observation.valid and observation.study_ad_id in positions
                and observation.x is not None and observation.y is not None
                and math.isfinite(observation.x) and math.isfinite(observation.y)
                and 0 <= observation.x <= 1 and 0 <= observation.y <= 1):
            column = min(int(observation.x * columns), columns - 1)
            row = min(int(observation.y * rows), rows - 1)
            if row * columns + column == positions[observation.study_ad_id]:
                local_x = observation.x * columns - column
                local_y = observation.y * rows - row
                zone = int(local_y >= 0.5) * 2 + int(local_x >= 0.5)

        if (previous is not None and zone is not None and zone == previous_zone
                and observation.study_ad_id == previous.study_ad_id):
            interval = observation.elapsed - previous.elapsed
            if 0 < interval <= 1.5:
                totals[observation.study_ad_id][zone] += interval

        # Una lectura inválida también interrumpe la continuidad entre muestras.
        previous, previous_zone = observation, zone

    return totals
