# Neuro IA Marketing — MediaPipe + RMN

Aplicación local en Python para detectar varios rostros con **MediaPipe Tasks Face
Landmarker**, conservar sus 478 landmarks y estimar expresiones con el **RMN original**.
OpenCV captura y muestra el video. Esta etapa no estima mirada ni atención y no
implementa mapas de calor, servidores web o bases de datos.

**Estado actualizado al 22 de octubre de 2026:** pesos originales incorporados y
verificados por SHA256. La aplicación ya carga RMN y clasifica expresiones. Ejecuta
`.\.venv\Scripts\python.exe main.py` desde esta carpeta para probarla con tu cámara.
Consulta [VALIDACION_RMN.md](VALIDACION_RMN.md) para las pruebas con los pesos reales,
los tiempos medidos y las limitaciones. [INTEGRACION.md](INTEGRACION.md) conserva
el informe histórico de la primera etapa, cuando todavía faltaban los pesos.

## Instalar y ejecutar en Windows

Abre **la carpeta de este repositorio** en VS Code. Se verificó el entorno con
Python **3.11.9 x64**. Desde PowerShell, para una instalación nueva:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-rmn.txt
.\.venv\Scripts\python.exe -m pip check
```

No necesitas activar el entorno. Selecciona `.venv\Scripts\python.exe` mediante
**Python: Select Interpreter** de VS Code. Usa siempre el entorno `.venv` de esta misma carpeta del repositorio.

Dependencias directas: MediaPipe 0.10.21, opencv-contrib-python 4.11.0.86, NumPy 1.26.4
y PyTorch 2.14.1+cpu. Las tres primeras permanecen como en la base; PyTorch conserva
la versión CPU del RMN recibido. No se necesitan torchvision, PIL ni Normalize para
la entrada de este clasificador. No instales además `opencv-python` o versiones
`headless`: compartirían `cv2` con `opencv-contrib-python`.

Modelos esperados:

```text
modelos/
├── face_landmarker.task              # Ya incluido
└── rmn_benchmark/
    └── resmasking_net.pth            # Original incorporado y verificado
```

Los pesos ya están en esa ubicación en esta copia local. Si trasladas el proyecto
mediante Git, cópialos por separado porque los checkpoints están ignorados. También
puedes ajustar `RUTA_RMN` en `config.py`. Se comprueba el mismo SHA256 que exigía `rmn.py`:

```text
5bd51cff4ad2f4e5ee34fd9a1fb838ebac606e22bd85475947fd746b749efe87
```

Un archivo diferente se rechaza antes de cargarlo. La aplicación no descarga pesos,
no entrena, no modifica checkpoints y no utiliza pesos aleatorios como alternativa.

Ejecutar la integración:

```powershell
.\.venv\Scripts\python.exe main.py
```

Ejecutar solo MediaPipe, sin pesos RMN ni necesidad de instalar PyTorch:

```powershell
.\.venv\Scripts\python.exe main.py --solo-mediapipe
```

## Controles y pantalla

| Tecla | Acción |
| --- | --- |
| Q | Cerrar y liberar cámara y detector. |
| M | Mostrar/ocultar todos los landmarks; iris en amarillo. |
| R | Alternar RMN si fue cargado al iniciar. No vuelve a cargarlo. |

También puedes cerrar la ventana o usar Ctrl+C. Una sola conexión a la cámara atiende
la aplicación. Las etiquetas muestran la clase y su probabilidad softmax. **Esto no
mide la emoción interna de una persona ni garantiza que la expresión sea correcta.**
El número de rostro es una posición en el fotograma, no una identidad persistente.

Rectángulo azul: límites de landmarks. Amarillo: recorte cuadrado que recibe RMN.
Un recorte rechazado muestra el motivo. El panel debajo del video muestra rostros,
resolución, FPS y tiempos del fotograma anterior; los FPS promedian los últimos 30
ciclos completados. No se atribuyen predicciones de un frame anterior a otra persona.

## Cómo fluye un fotograma

1. OpenCV lee una imagen **BGR uint8** de la cámara a la resolución disponible.
2. Para MediaPipe se hace una copia en **RGB** y, opcionalmente, se reduce su tamaño.
   `detect_for_video()` recibe timestamps estrictamente crecientes en milisegundos.
   La aplicación conserva el resultado completo, incluidas las coordenadas `x/y/z`.
3. Las coordenadas normalizadas se multiplican por las dimensiones del BGR original.
   Se comprueba que ojos, nariz y boca estén dentro de la imagen, que el rostro no sea
   demasiado pequeño y que una proporción suficiente de su caja esté visible.
4. Se toma un cuadrado alrededor del rostro con margen configurable. Cerca del borde
   se desplaza el cuadrado dentro de la imagen, sin estirarlo ni inventar píxeles.
   Si no cabe, se omite la clasificación. Los puntos no detectan toda oclusión:
   una mano sobre la boca o una cara de perfil todavía puede producir una mala entrada.
5. Se replica **exactamente** `rmn.py`: BGR → gris; resize 224 × 224 con
   `INTER_LINEAR`; repetir el gris tres veces; `float32 / 255.0`; tensor **N × 3 ×
   224 × 224**. No se aplican normalizaciones por media/desviación ni conversiones
   RGB adicionales. El resize original se conserva; el cuadrado previo evita deformar
   innecesariamente la cara.
6. RMN, cargado una vez con sus pesos originales, ejecuta `eval()` y
   `torch.inference_mode()`. Softmax por fila entrega siete probabilidades.
7. Una lista explícita de índices vincula cada salida con su recorte y sus landmarks,
   incluso cuando se descarta un rostro intermedio. Finalmente se dibuja sobre una
   copia del frame. Los textos y puntos nunca entran al clasificador.

Orden verificado en el código original:

| Índice | Identificador original / etiqueta |
| --- | --- |
| 0 | Enojo (ira) |
| 1 | Disgusto |
| 2 | Miedo |
| 3 | Alegria |
| 4 | Tristeza |
| 5 | Sorpresa |
| 6 | Neutral |

La fuente estándar de OpenCV no dibuja tildes; por eso la pantalla usa `Alegria`.

## Configuración

Edita `config.py` y reinicia. Valores iniciales:

| Parámetro | Valor | Uso |
| --- | --- | --- |
| `INDICE_CAMARA` | 0 | Probar 1 si corresponde a otra cámara. |
| `ANCHO_CAPTURA`, `ALTO_CAPTURA` | 640, 480 | Resolución solicitada; el dispositivo puede entregar otra. |
| `MAX_ROSTROS` | 5 | Máximo para MediaPipe. |
| `CONFIANZA_DETECCION/PRESENCIA/SEGUIMIENTO` | 0.5 cada una | Umbrales de Face Landmarker. |
| `MOSTRAR_LANDMARKS` | True | Dibujo inicial; M lo alterna. |
| `MOSTRAR_RECTANGULOS` | True | Cajas de landmarks y de recorte. |
| `NOMBRE_VENTANA` | Nombre del prototipo | Título de OpenCV. |
| `RUTA_MODELO`, `RUTA_RMN` | rutas en `modelos/` | Independientes de la carpeta desde la que se ejecuta Python. |
| `RMN_ACTIVO` | True | False arranca sin cargar RMN; R no puede cargarlo después. |
| `DISPOSITIVO_RMN` | auto | CPU o CUDA si está disponible; `cuda` falla explícitamente si no está disponible. |
| `HILOS_RMN` | 4 | Mismo número de hilos que el original. |
| `TAMANO_LOTE_RMN` | 1 | Procesa individualmente como el original. Probar 2/3 con la validación antes de cambiarlo. |
| `MARGEN_ROSTRO` | 0.10 | 10 % por lado del mayor tamaño de landmarks, antes de formar el cuadrado. |
| `MINIMO_ROSTRO` | 60 | Menor dimensión de landmarks en píxeles originales; no es exactamente el umbral Haar. |
| `FRACCION_VISIBLE` | 0.85 | Mínima fracción de la caja de landmarks dentro del frame. |
| `ANCHO_PROCESAMIENTO` | 0 | 0 conserva la entrada; p. ej. 480 reduce solo MediaPipe, manteniendo la proporción. |
| `GUARDAR_RECORTES` | False | Depuración voluntaria: PNG del recorte y NPY del tensor exacto. |
| `CARPETA_RECORTES` | `depuracion/` | Subcarpeta nueva por ejecución. |
| `MAX_RECORTES` | 20 | Máximo por ejecución, no por persona. |
| `INTERVALO_RECORTES` | 60 | Frecuencia de frames donde se permite guardar. |

El margen de 10 % es una hipótesis de partida, **no una calibración que garantice
equivalencia con Haar**. Compáralo sobre tus imágenes antes de ajustarlo. El modo de
menor resolución puede perder rostros pequeños; se deja desactivado. Los lotes
pueden consumir más memoria y no necesariamente acelerar CPU; el valor inicial es 1.

`requirements-rmn.txt` instala CPU. Para CUDA se requiere una GPU compatible y una
distribución PyTorch compatible con su controlador; sigue el selector oficial de
PyTorch en un entorno separado y conserva el resto de versiones. No se verificó CUDA
en esta entrega. `auto` no instala controladores ni cambia paquetes.

## Validar y medir

Pruebas automatizadas, sin webcam ni checkpoint, con torch instalado:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s pruebas -v
```

Cubren igualdad exacta del preprocesamiento respecto al `predecir()` original,
asociación con múltiples rostros, descarte de recortes, orden variable, BGR/RGB,
timestamps, controles, modelos ausentes y liberación de cámara. Las pruebas de
inferencia usan un **doble de prueba**, no RMN entrenado: verifican el cableado.

Prueba del modelo MediaPipe real sobre un retrato local (genera composiciones en
memoria de cero, una, dos y tres caras; no guarda imágenes salvo `--vista`):

```powershell
.\.venv\Scripts\python.exe pruebas\comprobar_mediapipe.py "C:\fotos\retrato.jpg" --salida resultados\mediapipe.json
```

Comparación del recorte original Haar y el integrado, sin checkpoint:

```powershell
.\.venv\Scripts\python.exe validar_integracion.py "C:\fotos\uno.jpg" "C:\fotos\varios.jpg" --solo-recortes --salida resultados\recortes.json
```

Con los pesos originales, quita `--solo-recortes`:

```powershell
.\.venv\Scripts\python.exe validar_integracion.py "C:\fotos\uno.jpg" "C:\fotos\varios.jpg" --repeticiones 10 --lotes 1 2 3 --salida resultados\comparacion.json
```

El informe contiene cajas, tamaños, formato y rango del tensor, todas las
probabilidades y cambios de clase. Compara **el mismo recorte** a través del método
original y del adaptador; verifica igualdad exacta de tensores y tolerancias float32
en las salidas. Después compara **recortes distintos del mismo rostro**, emparejados
por solapamiento y sin asociaciones ambiguas. Los rostros sin pareja quedan listados.

El comparador trabaja en CPU para reproducir `rmn.py`. Ambos métodos comparten el
modelo ya cargado y verificado: no duplica su memoria ni valida de forma independiente
el cargador original. La arquitectura copiada y su licencia permanecen intactas.
La prueba adicional siguiente sí ejecuta los dos cargadores de manera independiente,
comprueba sus salidas, evalúa 0/1/2/3 rostros y lotes 1/2/3, y ejercita el bucle real
de la aplicación sustituyendo solo la cámara por imágenes estáticas en memoria:

```powershell
.\.venv\Scripts\python.exe pruebas\comprobar_rmn_real.py "C:\fotos\retrato.jpg" --salida resultados\rmn_real.json
```

Requiere los pesos y una foto con un rostro frontal. No evalúa exactitud sobre un
conjunto etiquetado. Usa `--vista resultados\vista.png` si quieres guardar una vista
con las predicciones; no guarda fotos por defecto.

Para ejecutar además el programa original sin modificarlo, indica su ruta y coloca
el mismo checkpoint en su carpeta `modelos/rmn_benchmark/`:

```powershell
.\.venv\Scripts\python.exe referencias\rmn_original\rmn.py foto "C:\fotos\uno.jpg"
```

Para inspección visual voluntaria añade `--guardar-recortes resultados\recortes` al
comparador. Los PNG y NPY contienen imágenes faciales y permanecen hasta que los
borres. La aplicación normal no guarda nada con `GUARDAR_RECORTES=False`.

Medir cámara y ventana durante 300 fotogramas:

```powershell
.\.venv\Scripts\python.exe main.py --solo-mediapipe --max-fotogramas 300 --mediciones resultados\solo_mp.json
.\.venv\Scripts\python.exe main.py --max-fotogramas 300 --mediciones resultados\integrado.json
```

Repite con una, dos y tres personas, misma luz, encuadre, cámara y configuración.
Usa R para observar el costo de RMN dentro de una misma ejecución. Los resúmenes se
separan por modo, rostros detectados y rostros clasificados. Incluyen captura,
MediaPipe, recorte/preprocesamiento/transferencia, RMN/softmax/retorno a CPU,
depuración y visualización (`imshow`/`waitKey` incluidos). CUDA se sincroniza en los
límites de preparación e inferencia. Excluyen la carga de modelos; incluyen el primer
frame. No debes comparar estos promedios con medianas calentadas sin advertirlo.

`--sin-ventana --max-fotogramas 300` omite el dibujo y la ventana para diagnosticar;
sus tiempos no representan la experiencia con pantalla. El comparador de fotos
informa medianas tras calentamiento de MediaPipe, Haar, Haar+RMN original y la
integración con diferentes lotes. **No son FPS de webcam.** Usa fotos distintas y con
etiquetas conocidas para evaluar exactitud; una coincidencia numérica no basta.

## Estructura

```text
neuro-ia-marketing/
├── main.py                         # Captura, Tasks VIDEO, asociación y pantalla
├── config.py
├── requirements.txt               # Base MediaPipe/OpenCV/NumPy
├── requirements-rmn.txt           # PyTorch CPU original
├── README.md
├── READMEv2.md                    # Referencia histórica de la primera versión
├── INTEGRACION.md                 # Inspección y resultados de esta entrega
├── VALIDACION_RMN.md              # Verificación posterior con pesos originales
├── validar_integracion.py         # Comparaciones y tiempos con imágenes locales
├── emociones/
│   ├── rmn_detector.py            # Carga verificada, preprocesamiento e inferencia
│   └── rmn_autores/               # Arquitectura original y licencia, sin cambios
├── utilidades/
│   ├── procesamiento_imagen.py    # Recorte y depuración optativa
│   └── rendimiento.py            # Resúmenes numéricos
├── pruebas/
│   ├── test_integracion.py
│   ├── comprobar_mediapipe.py
│   └── comprobar_rmn_real.py
├── referencias/
│   ├── mediapipe_original/        # Copia previa a la integración
│   └── rmn_original/              # Copia intacta recibida, sin checkpoint
└── modelos/
    ├── face_landmarker.task
    └── rmn_benchmark/             # Checkpoint original y procedencia
```

Los directorios opcionales `resultados/` y `depuracion/`, los entornos, cachés y pesos
grandes están ignorados por Git. No se crearon commits, fusiones ni publicaciones.

## Errores y límites actuales

- **Faltan pesos:** se informa antes de abrir la cámara; usa `--solo-mediapipe` o
  proporciona el checkpoint correcto. No cambies el hash para aceptar pesos distintos.
- **Cámara inaccesible:** revisa Windows → Privacidad y seguridad → Cámara, cierra
  otras aplicaciones que la usen y verifica `INDICE_CAMARA`.
- **Un rostro queda sin clase:** revisa el motivo, la luz, el tamaño y la oclusión.
  Los landmarks solos no permiten garantizar que el rostro esté completo.
- **Baja fluidez:** revisa los tiempos por etapa antes de reducir resolución, lote o
  máximo de rostros. M ahorra dibujo, no inferencia de landmarks.
- **Predicciones diferentes:** compara primero mismo recorte/mismo tensor; después
  Haar frente a MediaPipe. El origen del recorte es una variable real, no solo estética.
- No hay identidad persistente, suavizado temporal de clases ni clasificación salteada.
  Cada frame usa sus propias predicciones para evitar atribuirlas a otra persona.
- Se verificó la equivalencia numérica con RMN original y se midieron tiempos en CPU.
  Falta una evaluación de exactitud con imágenes etiquetadas representativas. La prueba
  con cámara depende del dispositivo disponible; consulta el informe actualizado.

## Referencias

- Arquitectura y licencia incluidas en `emociones/rmn_autores/PROCEDENCIA.md` y `LICENSE`.
- [MediaPipe Face Landmarker para Python](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python).
- [PyTorch inference_mode](https://docs.pytorch.org/docs/2.14/generated/torch.autograd.grad_mode.inference_mode.html):
  evita el seguimiento de gradientes; `eval()` se aplica por separado.
- [PyTorch CUDA synchronize](https://docs.pytorch.org/docs/2.14/generated/torch.cuda.synchronize.html):
  espera las operaciones del dispositivo para delimitar mediciones.
