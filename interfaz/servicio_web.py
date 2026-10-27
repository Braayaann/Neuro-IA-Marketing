"""Control de sesión compartido por HTTP; la detección sigue en el hilo existente."""
import base64
from dataclasses import asdict, replace
from pathlib import Path
import queue
import threading
import time
import uuid

import cv2
import numpy as np

from config import Config, CALIBRACION, VALIDACION_WEB
from deteccion.detector_ocular import Camara, Observacion, dibujar_ojos
from calibracion.calibrador import Calibrador, CapturaPuntos, evaluar
from calibracion.comparador import Comparador
from mirada.estimador_mirada import EstimadorMirada
from heatmap.mapa_pagina import MapaPagina
from interfaz.coordenadas_web import validar_geometria, cambio, normalizar
from interfaz.prueba_dibujo import PruebaDibujo
from registro import Sesion, guardar_json


class Servicio:
    def __init__(self, modelo, resultados, cfg=Config(), camara_factory=Camara):
        self.modelo, self.resultados, self.cfg = Path(modelo), Path(resultados), cfg
        self.camara_factory = camara_factory
        self.lock = threading.RLock()
        self.worker = self.sesion = self.calibrador = self.estimador = self.captura = None
        self.geometria = self.validacion = None
        self.cal_id = ''
        self.estado = 'reposo'
        self.modo = 'ocular'
        self.demo_activo = False
        self.mapas = {k: MapaPagina(cfg) for k in ('ocular', 'mouse')}
        self.mapas_por_modelo = {'R': self.mapas['ocular'], 'A': MapaPagina(cfg), 'B': MapaPagina(cfg)}
        self.seleccion = 'R'
        self.comparador = None
        self.prueba_dibujo = self.reporte_dibujo = None
        self.ultimo_cliente = 0.
        self.visible = False
        self.propietario = None
        self.nonce = None
        self.fase = None
        self.mensaje = 'Inicia la cámara y calibra. La demostración con mouse está separada.'
        self.gaze = None
        self.fps = self.ms = self.pred_ms = 0.
        self.rostro = False
        self.motivo = 'camara_desconectada'
        self.aperturas = []
        self.pitch = None
        self.pose = None
        self.preview = None
        self.preview_t = 0.
        self.last_frame = 0.
        self.intentos_descartados = 0
        self.stop = threading.Event()
        self.hilo = None

    def iniciar_hilo(self):
        self.hilo = threading.Thread(target=self.bucle, daemon=True)
        self.hilo.start()

    def bucle(self):
        while not self.stop.wait(.01):
            with self.lock:
                try:
                    self.tick()
                except Exception as exc:
                    self.pausar()
                    self.estado = 'reposo'
                    self.captura = None
                    self.mensaje = f'Error: {exc}. Repite la fase.'

    def pausar(self):
        self.demo_activo = False
        self.gaze = None
        if self.estado == 'dibujo':
            self.prueba_dibujo = None
            self.estado = 'reposo'
        for mapa in self.mapas.values():
            mapa.interrumpir()
        if self.estimador:
            self.estimador.reset()
        if self.estado == 'seguimiento':
            self.estado = 'reposo'
            if self.sesion:
                self.sesion.evento('pausa')

    def invalidar(self, mensaje):
        self.pausar()
        self.calibrador = self.estimador = self.captura = self.validacion = None
        self.comparador = self.prueba_dibujo = self.reporte_dibujo = None
        self.seleccion = 'R'
        self.mapas['ocular'] = self.mapas_por_modelo['R']
        self.estado = 'reposo'
        self.nonce = None
        self.mensaje = mensaje

    def latido(self, datos):
        cliente = str(datos.get('cliente', ''))[:100]
        if not cliente:
            raise ValueError('Falta identificador de pestaña')
        ahora = time.perf_counter()
        if self.propietario and cliente != self.propietario and ahora-self.ultimo_cliente < 3:
            raise ValueError('Otra pestaña controla la cámara. Usa solo una pestaña.')
        if cliente != self.propietario:
            self.invalidar('Pestaña conectada; calibra en esta ventana.')
            self.propietario = cliente
        g = validar_geometria(datos['geometria'])
        if cambio(self.geometria, g):
            self.invalidar('Cambió tamaño, posición, zoom o desplazamiento. Mapa conservado; vuelve a calibrar.')
        self.geometria = g
        self.visible = bool(datos.get('visible'))
        self.ultimo_cliente = ahora
        if not self.visible:
            self.pausar()
            if self.captura:
                self.estado = 'reintento'
                self.captura.inicio = None
                self.nonce = None
                self.mensaje = 'La página perdió visibilidad. Repite el punto.'

    def nueva_sesion(self):
        if self.sesion is None:
            self.sesion = Sesion(self.resultados, dict(interfaz='web-v3-AB', config=asdict(self.cfg),
                espacio='viewport CSS normalizado; tarjetas ancladas a sus rectángulos DOM',
                nota='Mouse y ocular tienen acumulaciones y archivos separados.'))

    def comando(self, accion, datos):
        if self.geometria is None or not self.visible:
            raise ValueError('La página debe estar visible y enviar su geometría')
        self.nueva_sesion()
        if accion == 'camara_iniciar':
            if self.worker:
                raise ValueError('La cámara ya está abierta o cerrándose')
            self.invalidar('Abriendo cámara…')
            self.worker = self.camara_factory(int(datos.get('camara', 0)), self.modelo, self.cfg)
            self.worker.start()
        elif accion == 'camara_detener':
            self.invalidar('Cerrando cámara…')
            if self.worker:
                self.worker.detener()
        elif accion == 'modo':
            modo = datos.get('modo')
            if modo not in self.mapas:
                raise ValueError('Modo desconocido')
            self.pausar()
            self.estado = 'reposo'
            self.captura = None
            self.prueba_dibujo = None
            self.nonce = None
            self.modo = modo
            self.demo_activo = modo == 'mouse'
            self.mensaje = 'Demostración con mouse: no mide precisión ocular.' if modo == 'mouse' else 'Modo ocular: solo coordenadas estimadas por Python.'
            self.sesion.evento('cambio_modo', modo=modo)
        elif accion == 'comprobar_dibujo':
            if self.captura:
                raise ValueError('Cancela o completa la fase de captura primero')
            self.pausar()
            self.prueba_dibujo = PruebaDibujo(self.geometria)
            self.reporte_dibujo = None
            self.estado = 'dibujo'
            self.mensaje = 'Comprobando coordenadas conocidas, sin registrar mirada ni calor.'
        elif accion == 'seleccionar_modelo':
            nombre = datos.get('modelo')
            if self.estado != 'reposo' or not self.comparador or nombre not in self.comparador.reportes:
                raise ValueError('Pausa y completa la validación A/B antes de seleccionar')
            self.pausar()
            self.seleccion = nombre
            self.calibrador = self.comparador.modelos[nombre]
            self.estimador = EstimadorMirada(self.calibrador, self.cfg)
            self.validacion = self.comparador.reportes[nombre]
            self.mapas['ocular'] = self.mapas_por_modelo[nombre]
            self.sesion.evento('modelo_seleccionado', modelo=nombre, calibracion=self.cal_id)
            self.mensaje = f'Modelo {nombre} seleccionado. Su mapa ocular se conserva separado.'
        elif accion in ('calibrar', 'validar'):
            if self.modo != 'ocular' or not self.worker or not self.worker.is_alive() or time.perf_counter()-self.last_frame > 1:
                raise ValueError('Necesitas modo ocular y cámara con imágenes recientes')
            if accion == 'validar' and not self.calibrador:
                raise ValueError('Completa la calibración primero')
            self.pausar()
            if accion == 'calibrar':
                self.invalidar('Mira cada objetivo; mantén la cabeza estable.')
                self.cal_id = uuid.uuid4().hex[:8]
            self.validacion = None
            if self.comparador:
                self.comparador.reportes = {}
            self.fase = accion
            self.intentos_validacion = 0
            self.intentos_descartados = 0
            self.captura = CapturaPuntos(CALIBRACION if accion == 'calibrar' else VALIDACION_WEB, self.cfg)
            self.siguiente()
        elif accion == 'repetir_punto':
            if self.estado != 'reintento' or not self.captura:
                raise ValueError('No hay un punto incompleto')
            self.siguiente()
        elif accion == 'seguir':
            if not self.worker or not self.worker.is_alive() or time.perf_counter()-self.last_frame > 1:
                raise ValueError('La cámara no entrega imágenes recientes')
            if self.modo != 'ocular' or self.estado != 'reposo' or not self.calibrador or not self.validacion:
                raise ValueError('Completa calibración y validación primero')
            if not self.validacion['cumple_criterios']:
                raise ValueError('Validación insuficiente. Recalibra; no se habilita el seguimiento ocular.')
            self.pausar()
            self.estado = 'seguimiento'
            self.inicio_seguimiento = time.perf_counter()
            self.sesion.evento('inicio_seguimiento', calibracion=self.cal_id, modelo=self.seleccion)
            self.mensaje = 'Seguimiento ocular activo. El mapa representa mirada estimada.'
        elif accion == 'pausar':
            self.pausar()
            self.captura = None
            self.prueba_dibujo = None
            self.nonce = None
            self.estado = 'reposo'
            self.mensaje = 'Pausado.'
        elif accion == 'demo':
            if self.modo != 'mouse':
                raise ValueError('Selecciona demostración con mouse')
            self.demo_activo = True
        elif accion == 'limpiar':
            self.mapas[self.modo].limpiar()
            self.sesion.evento('limpiar', modo=self.modo)
        elif accion == 'guardar':
            self.exportar()
        else:
            raise ValueError('Acción desconocida')

    def siguiente(self):
        self.estado = 'esperando_punto'
        self.captura.inicio = None
        self.nonce = uuid.uuid4().hex

    def confirmar_objetivo(self, datos):
        if self.estado != 'esperando_punto' or datos.get('nonce') != self.nonce:
            raise ValueError('Objetivo caducado o ya iniciado')
        punto = normalizar(datos['x'], datos['y'], self.geometria)
        esperado = self.captura.puntos[self.captura.indice]
        if np.linalg.norm(np.asarray(punto)-esperado) > .015:
            raise ValueError('El punto dibujado no coincide con el objetivo solicitado')
        self.captura.puntos = list(self.captura.puntos)
        self.captura.puntos[self.captura.indice] = punto
        self.captura.presentar(time.perf_counter())
        self.estado = 'capturando'
        self.sesion.evento('objetivo_visible', fase=self.fase, punto=self.captura.indice+1,
                           css=[datos['x'], datos['y']], normalizado=punto, geometria=self.geometria)

    def mouse(self, datos):
        if self.modo != 'mouse':
            raise ValueError('El mouse está deshabilitado en modo ocular')
        punto = datos.get('punto') if self.visible and self.demo_activo else None
        if punto is not None and (len(punto) != 2 or not all(np.isfinite(punto))):
            raise ValueError('Coordenada inválida')
        self.mapas['mouse'].agregar(punto, time.perf_counter(), self.geometria)

    def procesar(self, paquete):
        t, frame, obs, self.ms, self.fps = paquete
        if obs.caracteristicas is not None and len(obs.caracteristicas) == 10 and obs.contexto is not None:
            obs = replace(obs, caracteristicas=np.r_[obs.caracteristicas, obs.contexto[5]/35])
        self.last_frame = t
        if time.perf_counter()-t > .5:
            obs = replace(obs, valida=False, motivo='frame_atrasado')
        self.rostro = obs.motivo not in ('sin_rostro', 'varias_personas')
        self.motivo = obs.motivo
        self.aperturas = list(obs.aperturas)
        self.pitch = float(obs.contexto[4]) if obs.contexto is not None else None
        self.pose = obs.contexto[3:6].tolist() if obs.contexto is not None else None
        if time.perf_counter()-self.preview_t > .2:
            self.preview_t = time.perf_counter()
            mini = cv2.resize(dibujar_ojos(frame, obs), (240, 180))
            ok, jpg = cv2.imencode('.jpg', mini, [cv2.IMWRITE_JPEG_QUALITY, 65])
            if ok:
                self.preview = base64.b64encode(jpg).decode('ascii')
        if self.estado == 'capturando':
            # Validación cruda: NO quitar predicciones por la guarda del modelo.
            # Así se distingue un fallo de modelo de un rechazo durante seguimiento.
            self.captura.agregar(t, obs)
        elif self.estado == 'seguimiento' and t >= self.inicio_seguimiento:
            inicio = time.perf_counter()
            raw, suave, motivo = self.estimador.estimar(obs, t)
            self.pred_ms = (time.perf_counter()-inicio)*1000
            self.motivo = motivo
            self.gaze = dict(raw=raw.tolist() if raw is not None else None,
                             suave=suave.tolist() if suave is not None else None, motivo=motivo)
            dt = self.mapas['ocular'].agregar(suave, t, self.geometria)
            self.sesion.agregar(t, self.cal_id+':'+self.seleccion, raw, suave, motivo,
                 (self.geometria['w'], self.geometria['h']), dt, self.ms, self.pred_ms)

    def terminar_punto(self):
        c = self.captura
        num, n = c.indice+1, len(c.actuales)
        intentos = c.intentos
        guardar_json(self.sesion.carpeta/f'diagnostico_{self.cal_id}_{self.fase}_{num}_{time.time_ns()}.json',
                     dict(objetivo=c.puntos[c.indice], muestras=c.diagnostico, rechazos=dict(c.rechazos)))
        aceptado = c.aceptar()
        self.sesion.evento('punto_capturado', fase=self.fase, punto=num, validas=n, intentos=intentos,
                          aceptado=aceptado, rechazos=dict(c.rechazos))
        if not aceptado:
            if self.fase == 'validar':
                self.intentos_descartados += intentos
            self.estado = 'reintento'
            c.inicio = None
            self.nonce = None
            self.mensaje = f'Punto {num}: {n}/{intentos} muestras. Corrige posición/iluminación y pulsa Repetir punto.'
            return
        if self.fase == 'validar':
            self.intentos_validacion += intentos
        if c.indice < len(c.puntos):
            self.siguiente()
            return
        muestras = c.muestras
        self.estado = 'ajustando'
        if self.fase == 'calibrar':
            self.comparador = Comparador().ajustar(muestras)
            self.calibrador = self.comparador.modelos['R']
            self.estimador = EstimadorMirada(self.calibrador, self.cfg)
            for nombre, modelo in self.comparador.modelos.items():
                modelo.guardar(self.sesion.carpeta/f'calibracion_{self.cal_id}_{nombre}.json',
                    dict(geometria=self.geometria, version_caracteristicas=3, modelo_comparado=nombre))
            guardar_json(self.sesion.carpeta/f'muestras_{self.cal_id}.json', muestras)
            self.mensaje = 'Referencia y modelos A/B ajustados. Valida para compararlos en nueve objetivos diferentes.'
        else:
            reportes = self.comparador.validar(muestras, self.geometria['w'], self.geometria['h'], self.intentos_validacion, self.cfg)
            for r in reportes.values():
                r['intentos_en_puntos_repetidos'] = self.intentos_descartados
            self.validacion = reportes[self.seleccion]
            pred = self.comparador.predicciones[self.seleccion]
            nombre = f'validacion_{self.cal_id}_{time.time_ns()}'
            guardar_json(self.sesion.carpeta/f'{nombre}.json', self.validacion)
            guardar_json(self.sesion.carpeta/f'{nombre}_muestras.json', dict(muestras=muestras, predicciones=pred))
            guardar_json(self.sesion.carpeta/f'{nombre}_AB.json', self.comparador.resumen())
            self.comparador.exportar_csv(self.sesion.carpeta/f'{nombre}_AB_muestras.csv', muestras,
                                        self.geometria['w'], self.geometria['h'])
            self.mensaje = f'Validación A/B terminada. Revisa sesgo vertical y regiones; selecciona el modelo. Sigue activo: {self.seleccion}.'
        self.estado = 'reposo'
        self.captura = None
        self.nonce = None

    def tick(self):
        ahora = time.perf_counter()
        if ahora-self.ultimo_cliente > 1 or not self.visible:
            self.pausar()
            if self.estado in ('capturando', 'esperando_punto'):
                self.estado = 'reintento'
                self.captura.inicio = None
                self.nonce = None
                self.mensaje = 'Se interrumpió la conexión/visibilidad. Repite el punto.'
        if self.worker:
            if ahora-self.ultimo_cliente > 5:
                self.worker.detener()
            try:
                self.procesar(self.worker.cola.get_nowait())
            except queue.Empty:
                pass
            if not self.worker.is_alive():
                error = self.worker.error
                self.worker = None
                self.preview = None
                self.rostro = False
                self.fps = self.ms = self.pred_ms = 0.
                self.aperturas = []
                self.pitch = None
                self.pose = None
                self.motivo = 'camara_desconectada'
                self.invalidar(f'Cámara cerrada. {error or ""}')
            elif ahora-self.last_frame > .5:
                self.gaze = None
                self.rostro = False
                self.mapas['ocular'].interrumpir()
                self.motivo = 'esperando_frames'
        if self.estado == 'capturando' and self.captura.terminado(ahora):
            self.terminar_punto()

    def exportar(self):
        etiqueta = self.modo+('_'+self.seleccion if self.modo == 'ocular' else '')
        prefijo = f'mapa_{etiqueta}_{time.time_ns()}'
        self.mapas[self.modo].guardar(self.sesion.carpeta, self.geometria, prefijo)
        guardar_json(self.sesion.carpeta/f'{prefijo}_geometria.json',
                     dict(geometria=self.geometria, modo=self.modo, calibracion=self.cal_id, modelo=self.seleccion))
        self.sesion.evento('exportacion', archivo=prefijo+'.png', modo=self.modo)
        self.mensaje = f'Guardado en {self.sesion.carpeta / (prefijo+".png")}'

    def snapshot(self):
        objetivo = None
        if self.captura and self.nonce and self.captura.indice < len(self.captura.puntos):
            objetivo = dict(nonce=self.nonce, indice=self.captura.indice, punto=self.captura.puntos[self.captura.indice],
                total=len(self.captura.puntos), fase=self.fase, n=len(self.captura.actuales),
                restante=max(0, self.cfg.espera_punto_s+self.cfg.captura_punto_s-(time.perf_counter()-self.captura.inicio)) if self.captura.inicio else None)
        return dict(estado=self.estado, modo=self.modo, demo_activo=self.demo_activo, mensaje=self.mensaje,
            seleccion=self.seleccion, comparacion=self.comparador.resumen() if self.comparador else None,
            prueba_dibujo=self.prueba_dibujo.objetivo() if self.prueba_dibujo else None, reporte_dibujo=self.reporte_dibujo,
            camara=self.worker is not None and self.worker.is_alive(), rostro=self.rostro, motivo=self.motivo,
            fps=self.fps, deteccion_ms=self.ms, estimacion_ms=self.pred_ms, aperturas=self.aperturas, pitch=self.pitch, pose=self.pose,
            calibracion=self.calibrador.elegido if self.calibrador else None, validacion=self.validacion,
            objetivo=objetivo, gaze=self.gaze, preview=self.preview, mapa_revision=self.mapas[self.modo].revision,
            segundos=self.mapas[self.modo].segundos, carpeta=str(self.sesion.carpeta) if self.sesion else None)

    def cerrar(self):
        self.stop.set()
        if self.hilo:
            self.hilo.join(timeout=5)
        if self.worker:
            self.worker.detener()
            self.worker.join(timeout=5)
        if self.sesion:
            if self.geometria:
                for modo, mapa in self.mapas.items():
                    mapa.guardar(self.sesion.carpeta, self.geometria, f'cierre_{modo}')
                for modelo, mapa in self.mapas_por_modelo.items():
                    mapa.guardar(self.sesion.carpeta, self.geometria, f'cierre_ocular_{modelo}')
            self.sesion.cerrar()

    def confirmar_dibujo(self, datos):
        if self.estado != 'dibujo' or self.prueba_dibujo is None:
            raise ValueError('No hay comprobación de dibujo activa')
        self.prueba_dibujo.registrar(datos)
        self.reporte_dibujo = self.prueba_dibujo.reporte()
        if self.reporte_dibujo:
            guardar_json(self.sesion.carpeta/f'prueba_dibujo_{time.time_ns()}.json', self.reporte_dibujo)
            self.prueba_dibujo = None
            self.estado = 'reposo'
            self.mensaje = ('Dibujo comprobado: error DOM/Canvas ≤1 px CSS. No mide precisión ocular.'
                            if self.reporte_dibujo['cumple'] else 'Hay un error de representación; consulta el diagnóstico de dibujo.')
