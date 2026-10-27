"""Interfaz local Tkinter. Solo el hilo principal toca los controles gráficos."""
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageTk

from config import Config, CALIBRACION, VALIDACION
from deteccion.detector_ocular import Camara, dibujar_ojos
from calibracion.calibrador import Calibrador, CapturaPuntos, evaluar
from mirada.estimador_mirada import EstimadorMirada
from heatmap.generador_heatmap import MapaCalor
from interfaz.geometria import encajar, a_canvas, cambio_geometria
from registro import Sesion, guardar_json


class Aplicacion:
    def __init__(self, root, modelo, resultados, camara=0, imagen=None, cfg=Config()):
        self.root, self.modelo, self.resultados, self.cfg = root, Path(modelo), Path(resultados), cfg
        self.worker = self.sesion = self.mapa = self.calibrador = self.estimador = None
        self.captura = self.validacion = self.geometria_cal = None
        self.estado = 'reposo'
        self.cal_id = ''
        self.punto = None
        self.ultimo_frame = None
        self.ultimo_dibujo = 0.
        self.ultimo_preview = 0.
        self.cerrando = False
        self.rect = None
        self.heat_cache = None
        self.cache_t = 0.
        self.metricas = ''
        self.root.title('Seguimiento ocular · prototipo independiente')
        self.root.geometry('1220x820')
        self.root.minsize(980, 700)
        self.root.protocol('WM_DELETE_WINDOW', self.cerrar)
        self.indice = tk.IntVar(value=camara)
        self.ver_punto = tk.BooleanVar(value=False)
        self.ver_calor = tk.BooleanVar(value=True)
        self.exploratorio = tk.BooleanVar(value=False)
        self.mensaje = tk.StringVar(value='1. Abre la cámara. 2. Selecciona una publicidad. 3. Calibra y valida.')
        self.tecnica = tk.StringVar(value='Cámara cerrada')
        self.progreso = tk.StringVar(value='Sin calibración')
        self.reporte = tk.StringVar(value='Validación pendiente. No hay una precisión medida.')
        barra = ttk.Frame(root, padding=6)
        barra.pack(fill='x')
        ttk.Label(barra, text='Cámara:').pack(side='left')
        ttk.Spinbox(barra, from_=0, to=9, width=3, textvariable=self.indice).pack(side='left', padx=4)
        for texto, funcion in [('Abrir cámara', self.abrir_camara), ('Elegir publicidad', self.elegir_imagen),
                                ('Calibrar / reiniciar', self.calibrar), ('Validar', self.validar),
                                ('Repetir punto', self.repetir_punto), ('Cancelar fase', self.cancelar)]:
            ttk.Button(barra, text=texto, command=funcion).pack(side='left', padx=3)
        barra2 = ttk.Frame(root, padding=(6, 0, 6, 6))
        barra2.pack(fill='x')
        for texto, funcion in [('Iniciar seguimiento', self.iniciar), ('Pausar', self.pausar),
                                ('Limpiar mapa', self.limpiar), ('Guardar resultados', self.exportar), ('Cerrar', self.cerrar)]:
            ttk.Button(barra2, text=texto, command=funcion).pack(side='left', padx=3)
        ttk.Checkbutton(barra2, text='Punto (prueba)', variable=self.ver_punto).pack(side='left', padx=5)
        ttk.Checkbutton(barra2, text='Mapa', variable=self.ver_calor).pack(side='left', padx=5)
        tk.Label(root, textvariable=self.mensaje, padx=6, pady=6, height=3, anchor='w', justify='left', wraplength=950).pack(fill='x')
        cuerpo = ttk.Frame(root)
        cuerpo.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(cuerpo, bg='#181c22', highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        panel = ttk.Frame(cuerpo, width=250)
        panel.pack(side='right', fill='y')
        panel.pack_propagate(False)
        scroll = ttk.Scrollbar(panel, orient='vertical')
        scroll.pack(side='right', fill='y')
        area = tk.Canvas(panel, highlightthickness=0, yscrollcommand=scroll.set)
        area.pack(side='left', fill='both', expand=True)
        scroll.configure(command=area.yview)
        lateral = ttk.Frame(area, padding=8)
        contenido = area.create_window(0, 0, window=lateral, anchor='nw')
        lateral.bind('<Configure>', lambda e: area.configure(scrollregion=area.bbox('all')))
        area.bind('<Configure>', lambda e: area.itemconfigure(contenido, width=e.width))
        self.preview = ttk.Label(lateral, text='Vista de cámara')
        self.preview.pack()
        ttk.Label(lateral, textvariable=self.progreso, wraplength=212, padding=(0, 10)).pack(fill='x')
        ttk.Label(lateral, textvariable=self.reporte, wraplength=212).pack(fill='x')
        ttk.Checkbutton(lateral, text='Permitir prueba exploratoria\nsi la validación no cumple',
                        variable=self.exploratorio).pack(anchor='w', pady=12)
        ttk.Label(lateral, text='Mantén la cabeza estable y mira el centro de cada objetivo.\n\n'
                  'Mover o redimensionar la ventana exige recalibrar.\n\n'
                  'El mapa representa tiempo de mirada ESTIMADA; no certifica atención ni fijaciones.',
                  wraplength=212).pack(fill='x')
        ttk.Label(root, textvariable=self.tecnica, padding=6).pack(fill='x')
        self.root.after(30, self.pulso)
        if imagen:
            self.root.after(100, lambda: self.cargar_imagen(Path(imagen)))

    def avisar(self, texto):
        self.mensaje.set(texto)

    def abrir_camara(self):
        if self.worker is not None and self.worker.is_alive():
            self.worker.detener()
            self.invalidar('Cerrando cámara. Pulsa Abrir cámara nuevamente cuando termine.')
            return
        if not self.modelo.is_file():
            messagebox.showerror('Modelo faltante', f'No se encuentra:\n{self.modelo}\nConsulta README.md.')
            return
        try:
            indice = self.indice.get()
        except tk.TclError:
            self.avisar('El índice de cámara debe ser un número entero.')
            return
        self.invalidar('Abriendo cámara; espera la vista previa.')
        self.worker = Camara(indice, self.modelo, self.cfg)
        self.worker.start()

    def elegir_imagen(self):
        ruta = filedialog.askopenfilename(title='Seleccionar publicidad',
                  filetypes=[('Imágenes', '*.png *.jpg *.jpeg *.bmp *.webp'), ('Todos', '*.*')])
        if ruta:
            self.cargar_imagen(Path(ruta))

    def cargar_imagen(self, ruta):
        try:
            with Image.open(ruta) as original:
                imagen = ImageOps.exif_transpose(original).convert('RGB')
                if min(imagen.size) < 64:
                    raise ValueError('Selecciona una imagen de al menos 64 × 64 píxeles.')
            # Guardar automáticamente los resultados anteriores antes de cambiar anuncio.
            if self.sesion:
                self.exportar(silencioso=True)
                self.sesion.cerrar()
            self.invalidar('Publicidad cargada. Ajusta la ventana, abre la cámara y pulsa Calibrar.')
            self.mapa = MapaCalor(imagen, self.cfg)
            self.heat_cache = None
            self.sesion = Sesion(self.resultados, dict(imagen=str(ruta.resolve()),
                 sha256_imagen=hashlib.sha256(ruta.read_bytes()).hexdigest(), dimensiones=imagen.size,
                 config=asdict(self.cfg), metodo='iris relativo + regresión calibrada',
                 modelo=str(self.modelo.resolve()),
                 sha256_modelo=hashlib.sha256(self.modelo.read_bytes()).hexdigest() if self.modelo.is_file() else None,
                 advertencia='Prototipo: la precisión requiere validación por sesión.'))
            self.rect = None
        except Exception as exc:
            messagebox.showerror('No se pudo cargar la publicidad', str(exc))

    def interrumpir(self):
        self.punto = None
        if self.mapa:
            self.mapa.interrumpir()
        if self.estimador:
            self.estimador.reset()

    def invalidar(self, motivo):
        self.interrumpir()
        self.estado = 'reposo'
        self.captura = self.calibrador = self.estimador = self.validacion = self.geometria_cal = None
        self.progreso.set('Sin calibración vigente')
        self.reporte.set('Validación pendiente. No hay una precisión medida.')
        self.exploratorio.set(False)
        self.avisar(motivo)

    def geometria(self):
        if self.mapa is None:
            return None
        rect = encajar(self.mapa.ancho, self.mapa.alto, self.canvas.winfo_width(), self.canvas.winfo_height())
        x, y, w, h = rect
        return (self.canvas.winfo_rootx()+x, self.canvas.winfo_rooty()+y, w, h)

    def requisitos(self):
        if self.mapa is None:
            self.avisar('Selecciona primero una publicidad.')
            return False
        if not self.worker or not self.worker.is_alive() or self.ultimo_frame is None or time.perf_counter()-self.ultimo_frame > 1:
            self.avisar('Abre la cámara y espera a que entregue imágenes.')
            return False
        return True

    def calibrar(self):
        if not self.requisitos():
            return
        self.invalidar('Mira cada objetivo sin mover la cabeza. La captura comienza después de una breve espera.')
        self.geometria_cal = self.geometria()
        self.cal_id = uuid.uuid4().hex[:8]
        self.captura = CapturaPuntos(CALIBRACION, self.cfg)
        self.estado = 'calibracion'
        self.presentar()

    def validar(self):
        if not self.requisitos():
            return
        if self.calibrador is None or self.estado in ('calibracion', 'reintento_calibracion'):
            self.avisar('Completa la calibración primero.')
            return
        self.interrumpir()
        self.validacion = None
        self.exploratorio.set(False)
        self.captura = CapturaPuntos(VALIDACION, self.cfg)
        self.intentos_validacion = 0
        self.rechazos_validacion = {}
        self.estado = 'validacion'
        self.avisar('Mira los objetivos nuevos. Esta prueba no modifica el modelo calibrado.')
        self.presentar()

    def presentar(self):
        self.dibujar(forzar=True)
        self.root.update_idletasks()
        self.captura.presentar(time.perf_counter())

    def repetir_punto(self):
        if self.estado.startswith('reintento_'):
            self.estado = self.estado.removeprefix('reintento_')
            self.presentar()
        else:
            self.avisar('Repetir punto se habilita cuando faltaron muestras en un objetivo.')

    def cancelar(self):
        if self.estado in ('calibracion', 'reintento_calibracion'):
            self.invalidar('Calibración cancelada. Puedes comenzarla nuevamente.')
        else:
            self.pausar()
            self.captura = None
            self.avisar('Fase cancelada; el mapa se conserva.')

    def cerrar_punto(self):
        fase = self.estado
        intentos, aceptadas = self.captura.intentos, len(self.captura.actuales)
        rechazos = dict(self.captura.rechazos)
        self.sesion.evento('captura_punto', fase=fase, punto=self.captura.indice+1,
                           intentos=intentos, aceptadas=aceptadas, rechazos=rechazos)
        if fase == 'validacion':
            self.intentos_validacion += intentos
            for razon, cantidad in rechazos.items():
                self.rechazos_validacion[razon] = self.rechazos_validacion.get(razon, 0)+cantidad
        if not self.captura.aceptar():
            self.estado = 'reintento_'+fase
            self.avisar(f'Punto incompleto: {aceptadas} muestras válidas. Necesitas al menos '
                        f'{self.cfg.muestras_min_punto}, distribuidas durante la captura. '
                        f'Acércate/abre los ojos y pulsa Repetir punto. Rechazos: {rechazos}')
            return
        if self.captura.indice < len(self.captura.puntos):
            self.presentar()
            return
        self.estado = 'reposo'
        muestras = self.captura.muestras
        reintentos = self.captura.reintentos
        self.captura = None
        try:
            if fase == 'calibracion':
                self.calibrador = Calibrador().ajustar(muestras)
                self.estimador = EstimadorMirada(self.calibrador, self.cfg)
                self.calibrador.guardar(self.sesion.carpeta/f'calibracion_{self.cal_id}.json',
                     dict(id=self.cal_id, geometria_pantalla=self.geometria_cal, muestras=len(muestras)))
                guardar_json(self.sesion.carpeta/f'muestras_{self.cal_id}.json', muestras)
                self.progreso.set(f'Calibración completa: {len(muestras)} muestras.\n'
                                  f'Ridge grado {self.calibrador.elegido["grado"]}.')
                self.avisar('Calibración lista. Pulsa Validar para medir el error en puntos nuevos.')
            else:
                predicciones = [self.calibrador.predecir(s['x']) for s in muestras]
                self.validacion = evaluar(predicciones, [s['objetivo'] for s in muestras],
                    [s['grupo'] for s in muestras], self.mapa.ancho, self.mapa.alto,
                    self.intentos_validacion, self.cfg)
                self.validacion.update(rechazos=self.rechazos_validacion, reintentos=reintentos,
                    calibracion=self.cal_id, geometria_pantalla=self.geometria_cal)
                version = time.time_ns()
                guardar_json(self.sesion.carpeta/f'validacion_{self.cal_id}_{version}.json', self.validacion)
                guardar_json(self.sesion.carpeta/f'validacion_muestras_{self.cal_id}_{version}.json',
                             dict(muestras=muestras, predicciones=np.asarray(predicciones).tolist()))
                v = self.validacion
                etiqueta = 'Cumple criterios exploratorios' if v['cumple_criterios'] else 'NO cumple criterios exploratorios'
                self.reporte.set(f'{etiqueta}\n\nError: {v["error_px"]:.1f} px de imagen original\n'
                    f'Error / diagonal: {v["error_normalizado_diagonal"]:.1%}\n'
                    f'Regiones 3×3: {v["acierto_regiones"]:.1%}\n'
                    f'Válidas: {v["muestras_validas"]}/{v["intentos"]}\n'
                    f'Cobertura: {v["cobertura"]:.1%}\n'
                    f'Dispersión RMS: {v["estabilidad_rms_px"]:.1f} px')
                self.progreso.set('Validación terminada')
                self.avisar('Revisa el resultado. Recalibra si el error es alto; puedes habilitar una prueba exploratoria.')
        except Exception as exc:
            if fase == 'calibracion':
                self.calibrador = self.estimador = None
            self.avisar(f'No se completó {fase}: {exc}. Repite la fase.')

    def iniciar(self):
        if not self.requisitos():
            return
        if self.calibrador is None or self.validacion is None or self.estado != 'reposo':
            self.avisar('Completa la calibración y la validación antes de iniciar.')
            return
        if not self.validacion['cumple_criterios'] and not self.exploratorio.get():
            self.avisar('La validación no cumple. Recalibra o marca Permitir prueba exploratoria para continuar con esa limitación.')
            return
        self.interrumpir()
        self.inicio_seguimiento = time.perf_counter()
        self.estado = 'seguimiento'
        self.sesion.evento('inicio_seguimiento', calibracion=self.cal_id,
                          cumple_criterios=self.validacion['cumple_criterios'])
        self.avisar('Seguimiento activo. Mira el anuncio. Pausa antes de moverte o cambiar de persona.')

    def pausar(self):
        estaba = self.estado
        self.estado = 'reposo'
        self.interrumpir()
        if self.sesion and estaba == 'seguimiento':
            self.sesion.evento('pausa', segundos=self.mapa.segundos)
        self.avisar('Pausado. Los datos del mapa se conservan.')

    def limpiar(self):
        if self.mapa:
            self.mapa.limpiar()
            self.heat_cache = None
            if self.sesion:
                self.sesion.evento('mapa_limpiado')
            self.avisar('Mapa reiniciado; el CSV conserva el historial y el evento de limpieza.')

    def exportar(self, silencioso=False):
        if not self.sesion or not self.mapa:
            self.avisar('Carga una publicidad primero.')
            return
        try:
            nombre = 'mapa_'+str(time.time_ns())
            self.mapa.guardar(self.sesion.carpeta, nombre)
            self.mapa.imagen.save(self.sesion.carpeta/'publicidad_original.png')
            self.sesion.evento('exportacion', archivo=nombre+'.png', segundos=self.mapa.segundos,
                               calibracion_vigente=self.cal_id if self.calibrador else None)
            if not silencioso:
                self.avisar(f'Guardado en {self.sesion.carpeta}')
        except Exception as exc:
            self.avisar(f'Error al guardar: {exc}')
            if silencioso:
                raise

    def procesar(self, paquete):
        t, frame, obs, ms, fps = paquete
        self.ultimo_frame = t
        pred_ms = 0.
        if time.perf_counter()-t > .5:
            obs = replace(obs, valida=False, motivo='frame_atrasado')
        self.tecnica.set(f'FPS cámara/proceso: {fps:.1f} | detección: {ms:.1f} ms | '
                         f'{obs.motivo} | tiempo acumulado: {self.mapa.segundos if self.mapa else 0:.2f} s')
        if self.estado in ('calibracion', 'validacion'):
            if self.estado == 'validacion' and obs.valida:
                motivo = self.calibrador.motivo_fuera_rango(obs)
                if motivo:
                    obs = replace(obs, valida=False, motivo=motivo)
            self.captura.agregar(t, obs)
        elif self.estado == 'seguimiento' and t >= self.inicio_seguimiento:
            inicio = time.perf_counter()
            raw, suave, motivo = self.estimador.estimar(obs, t)
            pred_ms = (time.perf_counter()-inicio)*1000
            dt = self.mapa.agregar(suave, t)
            self.punto = suave
            self.sesion.agregar(t, self.cal_id, raw, suave, motivo,
                               (self.mapa.ancho, self.mapa.alto), dt, ms, pred_ms)
            self.tecnica.set(f'FPS cámara/proceso: {fps:.1f} | detección: {ms:.1f} ms | '
                   f'estimación: {pred_ms:.2f} ms | {motivo} | acumulado: {self.mapa.segundos:.2f} s')
        if time.perf_counter()-self.ultimo_preview > .10:
            self.ultimo_preview = time.perf_counter()
            img = Image.fromarray(cv2.cvtColor(dibujar_ojos(frame, obs), cv2.COLOR_BGR2RGB))
            img.thumbnail((212, 160))
            self.foto_camara = ImageTk.PhotoImage(img)
            self.preview.configure(image=self.foto_camara, text='')

    def dibujar(self, forzar=False):
        ahora = time.perf_counter()
        if not forzar and ahora-self.ultimo_dibujo < .10:
            return
        self.ultimo_dibujo = ahora
        self.canvas.delete('all')
        if self.mapa is None:
            self.canvas.create_text(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2,
                                    text='Selecciona una imagen publicitaria', fill='white', font=('Segoe UI', 18))
            return
        self.rect = encajar(self.mapa.ancho, self.mapa.alto, self.canvas.winfo_width(), self.canvas.winfo_height())
        fase = self.estado in ('calibracion', 'validacion', 'reintento_calibracion', 'reintento_validacion')
        if self.ver_calor.get() and not fase:
            if self.heat_cache is None or ahora-self.cache_t > .4:
                self.heat_cache = self.mapa.overlay()
                self.cache_t = ahora
            img = self.heat_cache
        else:
            img = self.mapa.imagen
        x, y, w, h = self.rect
        self.foto_anuncio = ImageTk.PhotoImage(img.resize((w, h), Image.Resampling.BILINEAR))
        self.canvas.create_image(x, y, image=self.foto_anuncio, anchor='nw')
        if fase and self.captura and self.captura.indice < len(self.captura.puntos):
            px, py = a_canvas(self.captura.puntos[self.captura.indice], self.rect)
            self.canvas.create_oval(px-15, py-15, px+15, py+15, fill='white', outline='black', width=3)
            self.canvas.create_oval(px-4, py-4, px+4, py+4, fill='#e92035', outline='black')
        elif self.ver_punto.get() and self.punto is not None:
            px, py = a_canvas(self.punto, self.rect)
            self.canvas.create_oval(px-8, py-8, px+8, py+8, outline='#00ffff', width=3)

    def pulso(self):
        if self.cerrando:
            return
        try:
            if self.geometria_cal is not None and cambio_geometria(self.geometria_cal, self.geometria()):
                if self.sesion:
                    self.sesion.evento('geometria_cambiada', antes=self.geometria_cal, despues=self.geometria())
                self.invalidar('Cambió la posición/tamaño del anuncio. El mapa se conserva; vuelve a calibrar.')
            if self.worker:
                try:
                    self.procesar(self.worker.cola.get_nowait())
                except queue.Empty:
                    pass
                if not self.worker.is_alive():
                    error = self.worker.error
                    self.worker = None
                    self.ultimo_frame = None
                    self.invalidar('Cámara cerrada.' if not error else f'Error de cámara: {error}')
            if self.estado in ('calibracion', 'validacion') and self.captura.inicio is not None:
                restante = max(0., self.cfg.espera_punto_s+self.cfg.captura_punto_s-(time.perf_counter()-self.captura.inicio))
                preparando = time.perf_counter()-self.captura.inicio < self.cfg.espera_punto_s
                self.progreso.set(f'{self.estado.capitalize()}: punto {self.captura.indice+1}/{len(self.captura.puntos)}\n'
                         f'{"Prepárate" if preparando else "Mira el punto"} · {restante:.1f} s\n'
                         f'Muestras válidas: {len(self.captura.actuales)}')
                if self.captura.terminado(time.perf_counter()):
                    self.cerrar_punto()
            self.dibujar()
        except Exception as exc:
            self.pausar()
            self.avisar(f'Error de procesamiento: {exc}. Revisa cámara y repite la fase.')
        self.root.after(20, self.pulso)

    def cerrar(self):
        if self.cerrando:
            return
        self.pausar()
        self.cerrando = True
        if self.worker:
            self.worker.detener()
        self.avisar('Cerrando cámara y guardando resultados…')
        self.esperar_cierre()

    def esperar_cierre(self):
        if self.worker and self.worker.is_alive():
            self.root.after(50, self.esperar_cierre)
            return
        try:
            if self.sesion:
                self.exportar(silencioso=True)
                self.sesion.cerrar()
        except Exception as exc:
            messagebox.showerror('No se guardaron todos los resultados', str(exc))
        finally:
            self.root.destroy()
