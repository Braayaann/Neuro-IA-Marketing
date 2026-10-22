# Neuro IA Marketing — primera versión

> Documento histórico. La versión integrada y sus instrucciones actuales están en
> [README.md](README.md). La copia anterior a la integración está en
> `referencias/mediapipe_original/`.

Prototipo local de aprendizaje: abre una cámara, detecta hasta cinco rostros y dibuja
los 478 landmarks del modelo Face Landmarker, incluidos ojos e iris. Utiliza la API
moderna MediaPipe Tasks en modo **VIDEO**, con OpenCV para capturar y mostrar video.

No clasifica expresiones ni estima atención o mirada. Tampoco incorpora RMN, recortes,
mapas de calor, almacenamiento de imágenes, Flask, MySQL o React. Los números de rostro
se asignan de nuevo en cada fotograma; **no identifican personas de forma persistente**.

## 1. Preparar Windows y VS Code

Recomendado: **Python 3.11 de 64 bits (Windows x64)** desde https://www.python.org/downloads/.
Las versiones fijadas también admiten Python 3.12 x64. Para esta base utiliza 3.11;
no presupongas que este conjunto de dependencias funciona con Python 3.13 o posterior.
Son versiones estables fijadas para reproducir el entorno, no necesariamente las últimas.

Descomprime el proyecto y abre la carpeta `neuro-ia-marketing` en VS Code.
En su terminal PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación, puedes trabajar sin activarla:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

En VS Code, ejecuta **Python: Select Interpreter** y elige `.venv\Scripts\python.exe`.
En una terminal CMD la activación equivalente es `.venv\Scripts\activate.bat`.

`opencv-contrib-python` proporciona `cv2` y es una dependencia de esta versión de
MediaPipe. No instales además `opencv-python` ni variantes `headless` en este entorno:
comparten el mismo módulo y pueden producir conflictos. Se necesita soporte de ventanas.

## 2. Modelo oficial

El ZIP incluye `modelos/face_landmarker.task`, descargado de Google/MediaPipe.
Para obtenerlo de nuevo, ejecuta desde la carpeta del proyecto:

```powershell
New-Item -ItemType Directory -Force -Path .\modelos | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" -OutFile ".\modelos\face_landmarker.task"
```

La descarga es el modelo oficial, no una página HTML. Mantén el nombre `.task`.
La ruta `latest` puede actualizarse en el futuro; conserva la copia incluida si quieres
repetir pruebas con exactamente el mismo modelo. El modelo pertenece a sus autores;
consulta su documentación y condiciones en los enlaces oficiales al final.

## 3. Ejecutar y probar

Con el entorno virtual activo, desde la carpeta del proyecto:

```powershell
python main.py
```

1. Permite el acceso de las aplicaciones de escritorio a la cámara en Windows.
2. Acerca tu rostro: deben aparecer puntos verdes, puntos de iris amarillos, un
   rectángulo y una etiqueta `Rostro 1`.
3. Añade otras personas al encuadre y verifica el contador (hasta cinco rostros).
4. Presiona **M** con la ventana enfocada: alterna los puntos sin detener la detección.
5. Presiona **Q** para salir; también puedes cerrar la ventana o usar Ctrl+C en terminal.

La cámara y el detector se liberan al finalizar, incluso ante los errores controlados.
Los FPS empiezan en cero y se actualizan aproximadamente cada medio segundo. Miden el
ritmo del ciclo completo (captura, detección y visualización), no solo la inferencia.
La resolución mostrada corresponde al fotograma real: la cámara puede ignorar la solicitada.

## 4. Configurar

Modifica `config.py`, guarda y reinicia. Solo **M** modifica una opción durante la ejecución.

| Parámetro | Inicial | Para qué sirve |
| --- | --- | --- |
| `INDICE_CAMARA` | `0` | Cámara predeterminada; prueba `1` si tienes otra. |
| `ANCHO_CAPTURA`, `ALTO_CAPTURA` | `640`, `480` | Resolución solicitada en píxeles. |
| `MAX_ROSTROS` | `5` | Máximo de rostros procesados. |
| `CONFIANZA_DETECCION` | `0.5` | Confianza mínima para detectar un rostro. |
| `CONFIANZA_PRESENCIA` | `0.5` | Confianza mínima de presencia facial del modelo de landmarks. |
| `CONFIANZA_SEGUIMIENTO` | `0.5` | Confianza mínima del seguimiento interno de MediaPipe. |
| `MOSTRAR_LANDMARKS` | `True` | Puntos visibles al iniciar; M alterna su visualización. |
| `MOSTRAR_RECTANGULOS` | `True` | Dibujar el límite de los landmarks de cada rostro. |
| `RUTA_MODELO` | `modelos/face_landmarker.task` | Ruta resuelta desde la ubicación de `config.py`. |
| `NOMBRE_VENTANA` | Nombre del prototipo | Título de la ventana. |

Los umbrales deben estar entre 0 y 1. Subirlos exige mayor confianza, pero puede perder
rostros. Si el equipo va lento, prueba `MAX_ROSTROS = 1` y una resolución menor. Detectar
cinco rostros no garantiza un FPS concreto. MediaPipe solo aplica su suavizado de
landmarks cuando `num_faces` es 1; con cinco puedes observar más vibración de los puntos.

## 5. Archivos

```text
neuro-ia-marketing/
├── main.py
├── config.py
├── requirements.txt
├── README.md
└── modelos/
    └── face_landmarker.task
```

- `main.py`: validación, cámara, detección, dibujo, teclado y liberación de recursos.
- `config.py`: parámetros para experimentar.
- `requirements.txt`: versiones de las tres dependencias directas.
- `README.md`: instalación y uso.
- `modelos/face_landmarker.task`: modelo de Google cargado por MediaPipe.

## 6. Cómo funciona el procesamiento

1. `validar_configuracion()` comprueba modelo, dimensiones, cámara y umbrales.
2. `crear_detector()` configura Face Landmarker en CPU y modo VIDEO. Desactiva las
   salidas opcionales de blendshapes y matrices porque esta etapa no las necesita.
3. `abrir_camara()` abre OpenCV y solicita la resolución configurada.
4. `ejecutar_video()` lee cada frame y asigna un timestamp en milisegundos desde un reloj
   monotónico. `max(anterior + 1, transcurrido)` garantiza tiempos estrictamente crecientes.
5. `detectar_rostros()` convierte **BGR → RGB**, crea `mp.Image` y llama
   `detect_for_video()`. Se conserva el frame original BGR para OpenCV.
6. `dibujar_rostros()` convierte las coordenadas normalizadas a píxeles, limita los puntos
   a la imagen y dibuja sobre una copia. Dibuja todos los puntos disponibles, con otro
   color para los índices 468–477 de los iris. No construye una malla de conexiones.
7. Se superponen contador, FPS y resolución; se atienden M/Q y el cierre de la ventana.
8. El contexto del detector y el bloque `finally` cierran los recursos.

### Base para futuras etapas

Dentro de `ejecutar_video()`, `resultado.face_landmarks` es una lista por rostro.
Cada punto conserva `x`, `y` y `z` de MediaPipe; `x` e `y` son coordenadas normalizadas.
`obtener_puntos_y_limites()` entrega coordenadas en píxeles y `(x1, y1, x2, y2)` con
extremos inclusivos. El rectángulo delimita los landmarks visibles, no añade margen.
`fotograma` conserva la imagen original sin dibujos. Estos datos quedan accesibles
para añadir una etapa posterior sin cambiar la captura. **No se realizan recortes todavía**.
La coordenada `z` no equivale a una distancia física calibrada.

El seguimiento interno de MediaPipe optimiza la detección entre frames; no convierte
las etiquetas de esta aplicación en identidades estables ni constituye estimación de mirada.

## 7. Problemas comunes

- **No se abre la cámara:** prueba la app Cámara de Windows, revisa los permisos,
  cierra aplicaciones que la ocupen y prueba otro `INDICE_CAMARA`.
- **No llega video:** revisa la conexión. El programa informa el error y libera la cámara;
  ejecútalo de nuevo cuando esté disponible.
- **Modelo ausente o inválido:** comprueba la ruta y repite la descarga oficial.
- **`ModuleNotFoundError`:** selecciona el entorno correcto e instala `requirements.txt`
  usando el `python -m pip` de ese mismo entorno.
- **Problemas instalando:** comprueba `python --version` y que sea Python x64 3.11/3.12.
  Para evitar conflictos con proyectos previos, crea un entorno virtual nuevo.
- **Pocos FPS o puntos inestables:** mejora la iluminación y reduce la resolución o el
  máximo de rostros. Ocultarlos con M reduce el dibujo, pero no la inferencia.

## 8. Verificación de esta entrega

Se instaló el conjunto de dependencias en un entorno aislado con Python 3.12 en Linux
y se ejecutó el modelo real sobre una imagen sin rostros, un retrato y una composición
de dos retratos: se obtuvieron respectivamente 0, 1 y 2 rostros, con 478 landmarks por
rostro. También se probaron mediante simulación M/Q, los timestamps estrictamente
crecientes, los errores de cámara y la liberación de recursos. Se comprobó la resolución
de dependencias para Windows x64/Python 3.11, sin instalarlas en un equipo Windows.

No se dispone aquí de una cámara física ni de Windows: la ventana, los permisos, los
FPS reales y la captura con varias personas deben verificarse en tu computador con
los pasos de la sección 3.

## Referencias oficiales

- Guía de Face Landmarker para Python:
  https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python
- Modelo, características y descarga:
  https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- Instalación de MediaPipe Tasks:
  https://ai.google.dev/edge/mediapipe/solutions/setup_python
- Versiones utilizadas:
  https://pypi.org/project/mediapipe/0.10.21/
  https://pypi.org/project/opencv-contrib-python/4.11.0.86/
  https://pypi.org/project/numpy/1.26.4/
