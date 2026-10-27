"""A/B pareado: mismas muestras y objetivos, sin corregir coordenadas a mano."""
import csv
import numpy as np
from calibracion.calibrador import Calibrador, evaluar
from config import Config
from deteccion.detector_ocular import Observacion


def completar_muestras(muestras):
    """Admite los registros anteriores de 10 variables: roll ya estaba en contexto."""
    salida = []
    for s in muestras:
        x = list(s['x'])
        if len(x) == 10:
            x.append(float(s['contexto'][5]/35))
        if len(x) != 11:
            raise ValueError('La comparación requiere las ocho variables oculares y yaw/pitch/roll')
        salida.append(dict(s, x=x))
    return salida


def diagnosticar_sesgo(reporte):
    """Descripción, no prueba estadística: los frames vecinos no son independientes."""
    valores = [p['sesgo_y_px'] for p in reporte['por_punto']]
    media = reporte['sesgo_y_px']
    negativos = sum(v < -1 for v in valores)
    positivos = sum(v > 1 for v in valores)
    if abs(media) <= 1:
        texto = 'Sesgo medio cercano a cero; revisa errores absolutos por zona.'
    elif max(negativos, positivos)/len(valores) >= .75:
        texto = 'Tendencia vertical consistente en esta validación: '+('hacia arriba.' if media < 0 else 'hacia abajo.')
    else:
        texto = 'El sesgo cambia entre objetivos; no respalda una corrección vertical fija.'
    return dict(texto=texto, puntos_hacia_arriba=negativos, puntos_hacia_abajo=positivos,
                umbral_descriptivo_px=1., advertencia='No demuestra la causa ni significación estadística.')


class Comparador:
    def ajustar(self, muestras):
        muestras = completar_muestras(muestras)
        self.modelos = {
            'R': Calibrador().ajustar(muestras),
            'A': Calibrador().ajustar(muestras, [('ocular', list(range(8)))]),
            'B': Calibrador().ajustar(muestras, [('ocular_yaw_pitch_roll', list(range(11)))])}
        pose = np.array([s['contexto'][3:6] for s in muestras])
        self.pose_calibracion = dict(media_deg=pose.mean(0).tolist(), std_deg=pose.std(0).tolist(),
            rango_deg=np.ptp(pose, axis=0).tolist(),
            aviso='Poca variación de cabeza: B puede no aprender compensación fuera de esta postura.'
                  if np.max(pose.std(0)) < 2 else 'La compensación solo es evaluable en el rango observado.')
        self.reportes = {}
        self.predicciones = {}
        self.recomendado = None
        self.conclusion = 'Pendiente de validación independiente.'
        return self

    def validar(self, muestras, ancho, alto, intentos, cfg=Config()):
        muestras = completar_muestras(muestras)
        objetivos = [s['objetivo'] for s in muestras]
        grupos = [s['grupo'] for s in muestras]
        self.predicciones = {}
        self.reportes = {}
        for nombre, modelo in self.modelos.items():
            pred = np.array([modelo.predecir(s['x']) for s in muestras])
            self.predicciones[nombre] = pred.tolist()
            r = evaluar(pred, objetivos, grupos, ancho, alto, intentos, cfg, puntos_esperados=9)
            r['guardas_rechazarian'] = sum(bool(modelo.motivo_fuera_rango(Observacion(
                True, 'valida', np.array(s['x']), np.array(s['contexto'])))) for s in muestras)
            r['fuera_viewport'] = int(np.any((pred < 0)|(pred > 1), axis=1).sum())
            r['unidad'] = 'px CSS del viewport calibrado'
            r['sesgo_diagnostico'] = diagnosticar_sesgo(r)
            self.reportes[nombre] = r
        a, b = self.reportes['A'], self.reportes['B']
        # Orientación para elegir, no cambio automático ni afirmación de mejora poblacional.
        self.recomendado = 'B' if b['cumple_criterios'] and b['error_px'] < a['error_px']*.95 else 'A'
        referencia = self.reportes['R']
        candidato = self.reportes[self.recomendado]
        if referencia['cumple_criterios'] and (not candidato['cumple_criterios'] or candidato['error_px'] >= referencia['error_px']*.95):
            self.recomendado = 'R'
        if not self.reportes[self.recomendado]['cumple_criterios']:
            self.recomendado = 'R' if self.reportes['R']['cumple_criterios'] else None
        self.conclusion = ('B redujo más del 5 % el error total respecto a A en estas muestras.'
                           if b['error_px'] < a['error_px']*.95 else
                           'B no redujo más del 5 % el error total respecto a A; conservar A es razonable.')
        self.conclusion += ' Revisa también el sesgo y la zona inferior. La selección usa esta validación: confirma en otra sesión.'
        if self.recomendado == 'R':
            self.conclusion += ' Se sugiere conservar la referencia: el candidato no mejora su error total más del 5 %.'
        return self.reportes

    def resumen(self):
        return dict(modelos={k: v.elegido for k, v in self.modelos.items()}, reportes=self.reportes,
                    recomendado=self.recomendado, conclusion=self.conclusion, pose_calibracion=self.pose_calibracion)

    def exportar_csv(self, ruta, muestras, ancho, alto):
        with ruta.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['modelo','punto','t_monotonic_s','real_x_css','real_y_css',
                             'estimado_x_css','estimado_y_css','error_x_con_signo_px','error_y_con_signo_px','error_total_px'])
            for nombre, pred in self.predicciones.items():
                for s, p in zip(muestras, pred):
                    real = np.array(s['objetivo'])*[ancho-1, alto-1]
                    est = np.array(p)*[ancho-1, alto-1]
                    delta = est-real
                    writer.writerow([nombre, s['grupo']+1, s['t'], *real, *est, *delta, np.linalg.norm(delta)])
