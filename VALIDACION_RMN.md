# Validación con los pesos originales — 22 de octubre de 2026

## Estado actual

Se incorporó el checkpoint original y se completaron las pruebas de carga,
preprocesamiento, clasificación, asociación de rostros y lotes con el modelo real.
La aplicación está preparada para ejecutarse con `main.py`, sin `--solo-mediapipe`.
Las limitaciones de cámara, rendimiento y exactitud se detallan abajo.

## Pesos y conservación del original

Archivo recibido desde `Pesos-20261022T054416Z-1-001/Pesos/resmasking_net.pth`:

- Tamaño: **551.635.469 bytes**.
- SHA256 de origen y copia:
  `5bd51cff4ad2f4e5ee34fd9a1fb838ebac606e22bd85475947fd746b749efe87`.
- Destino: `modelos/rmn_benchmark/resmasking_net.pth`.
- Procedencia registrada en `modelos/rmn_benchmark/procedencia.json`.

El hash coincide con el requerido por `rmn.py` original. La copia se cargó con
`weights_only=True` y `load_state_dict(..., strict=True)`, sin claves ausentes o
sobrantes. Se mantuvieron arquitectura, pesos y orden de las siete clases. El archivo
de Descargas quedó intacto. No se descargó, reentrenó ni sustituyó el modelo. Los
checkpoints continúan excluidos por `.gitignore`; no se crearon commits ni publicaciones.

## Pruebas aprobadas

1. **Cargadores independientes:** se ejecutó el constructor original de RMN con su
   código intacto, apuntando en memoria a la ubicación de los mismos pesos. Después
   se liberó esa instancia y se cargó otra con el adaptador integrado. En el mismo
   recorte Haar, las siete probabilidades fueron idénticas: diferencia máxima **0.0**.
2. **Mismo recorte, ambos preprocesamientos:** el comparador capturó la entrada al
   modelo durante `predecir()` original y la comparó con el adaptador. Tensores
   idénticos y salidas equivalentes en los recortes Haar y MediaPipe probados.
3. **0/1/2/3 rostros:** modelo MediaPipe real, recortes, RMN entrenado y bucle real de
   `ejecutar_video()`, sustituyendo únicamente la cámara por una captura de imagen
   en memoria. Se detectaron y clasificaron respectivamente 0/1/2/3 rostros, con 478
   landmarks por cara. No se invoca inferencia cuando no hay caras.
4. **Lotes 1/2/3:** equivalencia frente a inferencias individuales. Mayor diferencia
   absoluta observada: **5,82e-10**, en lote 3. No hubo cambios de clase en estos casos.
5. **Interfaz:** se renderizó y revisó una vista con tres recortes y sus predicciones
   reales, landmarks, cajas y panel. Está rotulada como prueba estática; no es una
   captura de webcam ni simula un FPS medido.
6. **Regresión:** las **18 pruebas automatizadas** volvieron a pasar, incluidos
   cámara fallida, modelos ausentes, checkpoint incorrecto, recortes inválidos,
   cambio de orden de personas, M/R/Q y liberación de recursos.

Imagen de referencia: `grace_hopper.jpg`, incluida en la instalación existente de
Matplotlib. Las composiciones usan copias del mismo retrato y un lienzo fijo de
1023 × 400. No son tres personas distintas ni un conjunto de emociones etiquetadas.
Se usaron imágenes temporales, eliminadas al terminar, y se guardó voluntariamente
una vista mediante `--vista`. El guardado de cámara sigue desactivado por defecto.

## Comparación del recorte original e integrado

En la imagen completa de 512 × 600:

| Origen del recorte | Tamaño | Clase RMN | Probabilidad softmax |
| --- | --- | --- | --- |
| Haar original | 222 × 222 | Neutral | 0,97991335 |
| MediaPipe con margen | 243 × 243 | Neutral | 0,99852055 |

La diferencia máxima entre sus vectores de probabilidades fue **0,0186072**. El mismo
recorte, en cambio, produce exactamente la misma salida por ambas implementaciones.
Esto separa la influencia del encuadre de un posible error de preprocesamiento.

En las composiciones, todos los pares correspondieron a la misma clase; el mayor
cambio en una probabilidad por usar otro recorte fue **0,0722465**. No se ajustó el
margen para favorecer esta única fotografía. Una probabilidad mayor no demuestra
mayor exactitud, ni mide directamente la emoción de la persona. La conservación
de exactitud en otras expresiones requiere imágenes representativas etiquetadas.

## Rendimiento observado en CPU

Windows, Python 3.11.9, PyTorch 2.14.1+cpu, cuatro hilos, OpenCV 4.11.0 y MediaPipe
0.10.21. `torch.cuda.is_available()` devolvió False. Medianas de cinco repeticiones
tras calentamiento; no se incluye la carga de modelos, cámara ni ventanas:

| Rostros | Solo MediaPipe | Haar + RMN original | MediaPipe + RMN, lote 1 | Lote 2 | Lote 3 |
| --- | --- | --- | --- | --- | --- |
| 1 | 9,12 ms | 209,28 ms | 214,54 ms | 218,81 ms | 202,34 ms |
| 2 | 15,56 ms | 284,33 ms | 297,67 ms | 236,23 ms | 346,67 ms |
| 3 | 25,58 ms | 627,98 ms | 636,51 ms | 589,23 ms | 532,18 ms |

Con una cara el lote efectivo siempre es 1. Con dos caras, tanto el límite 2 como
el 3 ejecutan un lote de 2. Las diferencias entre esas mediciones muestran variación
del tiempo en CPU durante la prueba; no deben atribuirse al límite configurado.

La inferencia RMN aislada, con tensor ya preparado y lote 1, tuvo medianas de
138,83 / 410,37 / 613,51 ms para 1/2/3 rostros, medidas en otra fase de la prueba.
No se deben restar estas cifras de las columnas anteriores para deducir sobrecostos:
son mediciones separadas, con variación de carga/caché del equipo.

El bucle real de la aplicación, con captura en memoria y sin ventana, registró
medias de 156,77 / 432,42 / 638,18 ms por ciclo para 1/2/3 caras. Sus tasas derivadas
son 6,38 / 2,31 / 1,57 ciclos por segundo, **no FPS de webcam**. En esa ejecución la
mayor parte del tiempo corresponde a RMN, no al recorte ni al preprocesamiento.

Se conserva `TAMANO_LOTE_RMN = 1`: reproduce la ejecución original y limita memoria.
El lote 3 fue más rápido para tres caras en esta prueba, pero una medición breve no
justifica cambiar el valor para todos los equipos. Los lotes siguen configurables
y se verificó que no alteraran las clases de estas entradas. No se redujo la entrada
de RMN, no se aplicó precisión reducida y no se reutilizaron etiquetas entre frames.

## Cámara y límites de validación

La ejecución desde el entorno aislado cargó RMN correctamente en CPU y terminó al
intentar abrir la cámara 0. Al ejecutar fuera del aislamiento **sí abrió la cámara**,
capturó diez fotogramas y terminó correctamente. No hubo rostros detectados en ese
encuadre. El promedio fue 17,06 FPS sin ventana, con 56,24 ms de captura y 2,36 ms de
MediaPipe por frame. RMN estaba cargado pero no ejecutó inferencia porque no había
caras: estos FPS no representan el rendimiento clasificando personas. No se
guardaron imágenes ni video. Evidencia: `resultados/camara_rmn_acceso_directo.json`.

La prueba posterior **con ventana normal** también terminó con código 0: treinta
fotogramas, 23,80 FPS, 26,87 ms de captura, 2,35 ms de MediaPipe y 12,76 ms de
visualización por ciclo. Tampoco hubo caras detectadas en ese encuadre. Se ejercitaron
`namedWindow`, dibujo del panel, `imshow`, `waitKey`, cierre y liberación de cámara;
el límite de treinta frames cerró la aplicación automáticamente. Evidencia:
`resultados/camara_ventana_rmn.json`. La diferencia frente a la prueba de diez frames
no demuestra una mejora por activar la ventana: son muestras cortas de captura real.

La evaluación de exactitud sobre las siete expresiones y la validación con varias
personas en movimiento requieren pruebas del usuario con cámara y referencias
etiquetadas. No se afirma que haya mejorado la precisión ni se aplica a esta cámara
el porcentaje de FER2013 mencionado en la ficha del modelo.

## Reproducir las comprobaciones

Desde `neuro-ia-marketing`, con los pesos ya presentes:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s pruebas -v
.\.venv\Scripts\python.exe pruebas\comprobar_rmn_real.py .venv\Lib\site-packages\matplotlib\mpl-data\sample_data\grace_hopper.jpg --repeticiones 5 --salida resultados\validacion_rmn_completa.json
.\.venv\Scripts\python.exe main.py
```

Evidencia local: `resultados/rmn_real_un_rostro.json`,
`resultados/validacion_rmn_completa.json` y `resultados/vista_rmn_real.png`.
El código reproducible de la nueva prueba es `pruebas/comprobar_rmn_real.py`.
Las copias originales en `referencias/` no se modificaron.
