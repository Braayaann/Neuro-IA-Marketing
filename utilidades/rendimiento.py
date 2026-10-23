"""Tiempos en milisegundos, separados por modo y cantidad de rostros."""

import json
from pathlib import Path


class Mediciones:
    def __init__(self):
        self.grupos = {}

    def agregar(self, modo, detectados, clasificados, tiempos):
        clave = (modo, detectados, clasificados)
        grupo = self.grupos.setdefault(clave, {'fotogramas': 0, 'sumas_ms': {}})
        grupo['fotogramas'] += 1
        for etapa, valor in tiempos.items():
            grupo['sumas_ms'][etapa] = grupo['sumas_ms'].get(etapa, 0.0) + valor

    def resumen(self):
        filas = []
        for (modo, detectados, clasificados), grupo in self.grupos.items():
            medias = {k: v / grupo['fotogramas'] for k, v in grupo['sumas_ms'].items()}
            filas.append(dict(modo=modo, rostros=detectados, clasificados=clasificados,
                              fotogramas=grupo['fotogramas'], media_ms=medias,
                              fps=1000 / medias['ciclo'] if medias.get('ciclo', 0) > 0 else 0))
        return filas

    def guardar(self, ruta, contexto):
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(dict(contexto=contexto, resultados=self.resumen()),
                                   indent=2, ensure_ascii=False), encoding='utf-8')
