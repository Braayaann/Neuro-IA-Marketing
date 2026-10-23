"""Suavizado temporal y tiempos por zona, independientes de la webcam."""
from collections import deque
from statistics import median
from .geometria import region


class Seguimiento:
    def __init__(self, ventana=0.35, permanencia=0.20, salto_maximo=0.5, banda=0.04):
        self.ventana, self.permanencia = ventana, permanencia
        self.salto_maximo, self.banda = salto_maximo, banda
        self.reiniciar()

    def reiniciar(self):
        self.puntos = deque()
        self.candidato, self.desde = None, None
        self.anterior, self.ultimo = 'INDETERMINADA', None
        self.segundos = dict.fromkeys(('A', 'B', 'FUERA', 'INDETERMINADA'), 0.0)

    def actualizar(self, ahora, punto, estado_crudo):
        salto = self.ultimo is not None and ahora - self.ultimo > self.salto_maximo
        if salto or estado_crudo not in ('A', 'B'):
            self.puntos.clear()
            self.candidato, self.desde = None, None
        suavizado = None
        estado = estado_crudo
        if estado_crudo in ('A', 'B'):
            self.puntos.append((ahora, punto))
            while self.puntos and ahora - self.puntos[0][0] > self.ventana:
                self.puntos.popleft()
            suavizado = tuple(median(p[1][i] for p in self.puntos) for i in (0, 1))
            candidato = region(suavizado, self.banda)
            if candidato != self.candidato:
                self.candidato, self.desde = candidato, ahora
            estado = candidato if ahora - self.desde >= self.permanencia else 'INDETERMINADA'
        if self.ultimo is not None:
            intervalo = max(0.0, ahora - self.ultimo)
            # Nunca prolongar un anuncio durante perdida de rostro o pausas largas.
            destino = estado if not salto and estado == self.anterior else 'INDETERMINADA'
            self.segundos[destino] += intervalo
        self.ultimo, self.anterior = ahora, estado
        return suavizado, estado

    def resumen(self):
        total = sum(self.segundos.values())
        asignado = self.segundos['A'] + self.segundos['B']
        return {
            'segundos': dict(self.segundos), 'total_segundos': total,
            'porcentaje_del_total': {k: 100*v/total if total else 0 for k,v in self.segundos.items()},
            'porcentaje_del_tiempo_asignado': {k: 100*self.segundos[k]/asignado if asignado else 0 for k in ('A','B')},
            'cobertura': asignado/total if total else 0,
        }
