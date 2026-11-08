"""Comparación manual sobre las mismas fijaciones y la misma calibración."""
from copy import deepcopy

import numpy as np

from .calibracion import Calibracion, evaluar
from .captura import CapturaPunto
from .diagnostico import emitir


OBJETIVOS_PRUEBA = [(.18, .22), (.8, .76), (.48, .46), (.2, .78), (.82, .24)]


class Alternativas:
    def __init__(self, original, pantalla):
        self.original = original
        self.pantalla = np.asarray(pantalla)
        self.modelos = {}
        for metodo in ('lineal', 'cuadratico', 'local'):
            try:
                modelo = Calibracion(metodo).ajustar(original.muestras)
            except ValueError:
                continue
            modelo.desplazamiento = original.desplazamiento.copy()
            modelo.ganancia = original.ganancia.copy()
            self.modelos[metodo] = modelo
        self.modelo = self.modelos[original.metodo] = deepcopy(original)

    def mover(self, eje, pixeles):
        self.modelo.desplazamiento[eje] += pixeles/(self.pantalla[eje]-1)

    def escalar(self, eje, cambio):
        self.modelo.ganancia[eje] = np.clip(self.modelo.ganancia[eje]+cambio, .5, 1.5)

    def errores(self, muestras):
        opciones = {'guardado': self.original, **self.modelos}
        return {nombre: evaluar(modelo, muestras, OBJETIVOS_PRUEBA, self.pantalla)
                for nombre, modelo in opciones.items()}


class PanelComparacion:
    def __init__(self, original, pantalla, opciones_captura):
        import tkinter as tk
        from tkinter import ttk

        self.alternativas = Alternativas(original, pantalla)
        self.opciones_captura = opciones_captura
        self.accion = None
        self.muestras = []
        self.captura = None
        self.midiendo = False
        self.raiz = tk.Tk()
        self.raiz.title('Comparar mirada')
        self.raiz.attributes('-fullscreen', True)
        self.raiz.protocol('WM_DELETE_WINDOW', lambda: self.terminar('cancelar'))
        self.raiz.bind('<Escape>', lambda _: self.terminar('cancelar'))
        self.lienzo = tk.Canvas(self.raiz, bg='#17212b', highlightthickness=0)
        self.lienzo.pack(fill='both', expand=True)
        self.controles = ttk.Frame(self.raiz, padding=6)
        self.controles.place(relx=.5, y=0, anchor='n')
        self.metodo = tk.StringVar(value=original.metodo)
        self.paso = tk.IntVar(value=10)
        self.botones_edicion = []
        fila = ttk.Frame(self.controles)
        fila.pack()
        for nombre in ('guardado', *self.alternativas.modelos):
            ttk.Radiobutton(fila, text=nombre.capitalize(), value=nombre, variable=self.metodo,
                            command=self.seleccionar).pack(side='left')
        for paso in (2, 10, 30):
            ttk.Radiobutton(fila, text=f'{paso} px', value=paso, variable=self.paso).pack(side='left')
        fila = ttk.Frame(self.controles)
        fila.pack()
        for texto, eje, signo in [('←', 0, -1), ('→', 0, 1), ('↑', 1, -1), ('↓', 1, 1)]:
            boton = ttk.Button(fila, text=texto, width=4, command=lambda e=eje, s=signo: self.mover(e, s))
            boton.pack(side='left')
            self.botones_edicion.append(boton)
        for texto, eje, signo in [('Ancho −', 0, -1), ('Ancho +', 0, 1), ('Alto −', 1, -1), ('Alto +', 1, 1)]:
            boton = ttk.Button(fila, text=texto, command=lambda e=eje, s=signo: self.escalar(e, s))
            boton.pack(side='left')
            self.botones_edicion.append(boton)
        self.estado = tk.StringVar()
        ttk.Label(self.controles, textvariable=self.estado).pack()
        fila = ttk.Frame(self.controles)
        fila.pack()
        for texto, accion in [('Medir 5 puntos', self.medir), ('Guardar selección', lambda: self.terminar('guardar')),
                              ('Cancelar', lambda: self.terminar('cancelar'))]:
            boton = ttk.Button(fila, text=texto, command=accion)
            boton.pack(side='left')
            if texto == 'Guardar selección':
                self.botones_edicion.append(boton)
        self.raiz.update_idletasks()
        self.raiz.lift()
        self.raiz.focus_force()
        self.refrescar()

    def terminar(self, accion):
        self.accion = accion

    def seleccionar(self):
        guardado = self.metodo.get() == 'guardado'
        self.alternativas.modelo = self.alternativas.original if guardado else self.alternativas.modelos[self.metodo.get()]
        for boton in self.botones_edicion:
            boton.state(['disabled' if guardado else '!disabled'])
        self.refrescar()

    def mover(self, eje, signo):
        self.alternativas.mover(eje, signo*self.paso.get())
        self.refrescar()

    def escalar(self, eje, signo):
        self.alternativas.escalar(eje, signo*.02)
        self.refrescar()

    def refrescar(self):
        modelo = self.alternativas.modelo
        x, y = modelo.desplazamiento*(self.alternativas.pantalla-1)
        gx, gy = modelo.ganancia
        texto = f'Desfase X {x:+.0f} px   Y {y:+.0f} px     Ancho {gx:.0%}   Alto {gy:.0%}'
        if len(self.muestras) == len(OBJETIVOS_PRUEBA):
            errores = self.alternativas.errores(self.muestras)
            texto += '\nError medio (px): ' + '   '.join(
                f'{nombre} {datos["error_medio_px"]:.0f}' for nombre, datos in errores.items())
        self.estado.set(texto)

    def medir(self):
        self.muestras.clear()
        self.captura = None
        self.midiendo = True
        self.controles.place_forget()

    def actualizar(self, cruda, filtrada, postura, ahora):
        self.raiz.update()
        if self.accion:
            return
        lienzo = self.lienzo
        ancho, alto = lienzo.winfo_width()-1, lienzo.winfo_height()-1
        lienzo.delete('all')
        if self.midiendo:
            if self.captura is None:
                self.captura = CapturaPunto(ahora, **self.opciones_captura)
            indice = len(self.muestras)
            objetivos = [OBJETIVOS_PRUEBA[indice]]
            resultado = self.captura.actualizar(cruda, ahora, postura)
            fase, restante = self.captura.estado(ahora)
            texto = f'Mira el punto {indice+1}/5   {fase}   {restante:.1f} s'
            if resultado is not None:
                if resultado.posicion is not None:
                    self.muestras.append(resultado.posicion)
                else:
                    print(f'Punto {indice+1}: {resultado.motivo}')
                self.captura = None
                if len(self.muestras) == len(OBJETIVOS_PRUEBA):
                    self.midiendo = False
                    emitir('comparacion_medida', metricas=self.alternativas.errores(self.muestras))
                    self.controles.place(relx=.5, y=0, anchor='n')
                    self.refrescar()
        else:
            objetivos = OBJETIVOS_PRUEBA
            texto = 'Mira una cruz. El círculo amarillo indica la estimación.' if filtrada is not None else 'Sin señal de mirada'
            if filtrada is not None:
                x, y = self.alternativas.modelo.predecir(filtrada)*[ancho, alto]
                if 0 <= x <= ancho and 0 <= y <= alto:
                    lienzo.create_oval(x-8, y-8, x+8, y+8, outline='#ffda52', width=3)
                else:
                    texto = 'Estimación fuera de la pantalla'
        for x, y in objetivos:
            x, y = x*ancho, y*alto
            lienzo.create_line(x-7, y, x+7, y, fill='white', width=2)
            lienzo.create_line(x, y-7, x, y+7, fill='white', width=2)
        lienzo.create_text(ancho/2, alto-25, text=texto, fill='white')

    def cerrar(self):
        self.raiz.destroy()
