> Documento historico anterior a la integracion. Para rutas y comandos actuales, consulta ../README.md.

# Inspección, integración y verificación — 21 de octubre de 2026

> Informe histórico de la primera etapa. El 22 de octubre se incorporaron los pesos
> originales y se completaron las pruebas que dependían de ellos. El estado vigente
> y las mediciones con RMN están en [VALIDACION_RMN.md](VALIDACION_RMN.md).

## Inspección previa

El directorio de trabajo contenía dos proyectos ya descomprimidos. No se encontró un
ZIP dentro de ellos; por ello no hubo archivo que extraer. Antes de modificar la base
se copiaron sus archivos a `referencias/mediapipe_original/` y el proyecto RMN a
`referencias/rmn_original/`. La carpeta hermana `Neuro-IA-Marketing-modeloIA` quedó
intacta. Se verificaron por SHA256 los 11 archivos originales RMN y sus copias; el
código incorporado a `emociones/rmn_autores/` es idéntico al recibido. Los hashes
están en `referencias/verificacion_originales.json`.

**Proyecto A:** `main.py` abre una sola cámara con `cv2.VideoCapture`, solicita la
resolución de `config.py`, convierte BGR a RGB y utiliza la API moderna
`vision.FaceLandmarker` en modo `VIDEO`. Los timestamps se hacen estrictamente
crecientes. Sus coordenadas normalizadas se convierten a píxeles para dibujar puntos,
iris, cajas mínimas, contador y FPS. M/Q alternan puntos y cierran. MediaPipe, OpenCV
contrib y NumPy eran sus dependencias directas. Esta implementación se mantuvo como
base; no se reemplazó por `mp.solutions.face_mesh`.

**Proyecto B:** `rmn.py` carga el checkpoint con `torch.load(..., weights_only=True,
map_location='cpu')`, exige un SHA256 fijo y acepta `checkpoint['net']` o un state
dict directo. Retira el prefijo `module.` si está en todas las claves. Reconoce la
cabeza lineal `fc.weight` o `fc.1.weight` con dropout, ambas de forma `(7, 512)`, y
usa carga estricta. La arquitectura es ResNet con bloques BasicBlock `[3,4,6,3]` y
cuatro módulos de masking de profundidades 4/3/2/1; las máscaras modulan las
características mediante `x * (1 + m)`. Se preservaron fuentes, procedencia y licencia
MIT. No se invoca la variante ResMasking50 que descargaría pesos de ImageNet.

La detección original de RMN usa Haar de OpenCV:
`haarcascade_frontalface_default.xml`, escala 1.1, cinco vecinos, mínimo 60 × 60.
Recorta directamente `imagen[y:y+h, x:x+w]`, sin margen adicional, y convierte BGR
a gris, resize bilineal 224², tres canales idénticos, float32 / 255, NCHW. No usa
normalización ImageNet, torchvision, aumento de datos ni TTA. Softmax convierte
siete logits en probabilidades. Orden: Enojo, Disgusto, Miedo, Alegria, Tristeza,
Sorpresa, Neutral. Inferencia original en CPU con cuatro hilos, eval e inference_mode.

**Pesos ausentes:** el README RMN mencionaba `modelos/rmn_benchmark/resmasking_net.pth`
y `procedencia.json`, pero ninguno estaba incluido. No se encontraron checkpoints
en los proyectos ni en la búsqueda adicional de Documentos. El único modelo presente
es `face_landmarker.task`. Se informó esta ausencia antes de intentar cargar RMN y
se solicitó la ubicación del original. No se descargaron ni sustituyeron pesos.

## Decisiones de integración

- Se reutilizan captura, Tasks VIDEO, timestamps, controles M/Q, landmarks completos
  y liberación de recursos de la base. La interfaz añade expresión, probabilidad,
  recorte efectivo y tiempos en un panel debajo del video.
- Se reutilizan literalmente arquitectura y clases de RMN; se adapta su cargador
  para aceptar una ruta configurable y CPU/CUDA. Los dos modelos se cargan una sola
  vez, antes de abrir la cámara. R suspende/reanuda inferencia sin recargar pesos.
- El margen de 10 % y el cuadrado buscan aproximar el encuadre de Haar sin deformar
  la cara. **No son equivalentes por definición al detector original**. Deben
  calibrarse con las mismas imágenes y predicciones de referencia.
- Se conserva la imagen original BGR para clasificar y se dibuja al final. Las
  coordenadas de una entrada MediaPipe reducida se proyectan a la resolución original.
- Los recortes inválidos se descartan conservando sus índices. No hay seguimiento
  de identidad ni reutilización de predicciones de otro frame.
- La inferencia por lotes es opcional y parte de 1. El comparador puede comprobar
  tolerancias y tiempos de lotes 1/2/3 sobre las mismas caras. No se adoptó batching
  mayor sin medir el modelo real.
- El guardado está desactivado por defecto; al activarlo se limita por cantidad y
  frecuencia. No hay almacenamiento o envío de video.

Se evaluó Haar como referencia de recorte en `validar_integracion.py`. Ejecutarlo
además de MediaPipe añade un segundo detector y exige asociar sus cajas. En el
retrato de 512 × 600 usado aquí, Haar tardó una mediana de **11,51 ms** y MediaPipe
**9,74 ms**, cada uno medido por separado, diez repeticiones tras calentamiento.
Los 11,51 ms dan una estimación del costo adicional en esa imagen; no son una
medición conjunta ni un costo universal. Sin pesos no se puede determinar si Haar
conserva mejor las clases. Se dejó en la herramienta de comparación, sin ejecutarlo
en cada frame de cámara. Si los datos futuros favorecen Haar, esa evidencia puede
justificar incorporarlo al flujo, con el costo de detección y asociación medido.

## Archivos modificados y creados

Modificados en la aplicación: `main.py`, `config.py`, `requirements.txt` y una nota
de documento histórico en `READMEv2.md`.

Creados: `README.md`, este informe, `requirements-rmn.txt`, `.gitignore`,
`validar_integracion.py`, paquetes `emociones/` y `utilidades/`, dos scripts de
pruebas, copias en `referencias/` y el archivo de verificación de fuentes. En la
carpeta superior se añadieron un README de entrada y un `.gitignore` para excluir
también el entorno virtual superior. La estructura completa y los comandos están
en el README de la aplicación.

## Comprobaciones realizadas

Entorno: Windows, Python 3.11.9 x64, MediaPipe 0.10.21, OpenCV 4.11.0 (paquete
4.11.0.86), NumPy 1.26.4, PyTorch 2.14.1+cpu. CPU identificada por el sistema como
AMD64 Family 25 Model 97 Stepping 2. `torch.cuda.is_available()` devolvió False.
Se ejecutó además la arquitectura original `resmasking_dropout1` en el dispositivo
`meta` de PyTorch: una entrada `(3,3,224,224)` produjo forma `(3,7)`, con 137.796.423
parámetros. Esto verifica compatibilidad estructural con lotes sin reservar pesos
reales; no produce probabilidades ni mide su velocidad. Solo los parámetros float32
ocuparían aproximadamente 551 MB decimales, además de activaciones y checkpoint.
Se consultó el índice oficial e instaló el PyTorch CPU indicado por el proyecto
original en el entorno de la aplicación. `pip check` no encontró incompatibilidades.

SHA256 del modelo MediaPipe utilizado:
`64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.

**18 pruebas automatizadas aprobadas** (`python -m unittest discover -s pruebas -v`):

- Igualdad exacta de los tensores entregados al método `predecir()` original y al
  adaptador, sobre imágenes sintéticas BGR y grises de diferentes dimensiones.
- Igualdad de salidas sobre el mismo tensor con una red de contrato explícita;
  ejecución sin gradientes, lotes, orden de salidas y probabilidades finitas.
- Coeficientes BGR→gris y escala 0–1; rechazo de imágenes vacías, float ya normalizado
  y canales inválidos; checkpoints ausentes o con SHA256 incorrecto.
- Recorte cuadrado con píxeles originales, desplazamiento en bordes, mínimo de
  tamaño, puntos fuera de imagen, NaN y ausencia de espacio suficiente.
- Índices conservados al descartar el rostro intermedio; cambio de orden de caras
  sin reutilizar etiquetas; emparejamiento geométrico y rechazo de ambigüedad.
- Guardado apagado, intervalo y límite; tensor NPY idéntico al preprocesado.
- Timestamps estrictos, M/R/Q simulados, frame sin rostros, resolución reducida y
  conversión RGB solo para MediaPipe.
- Cámara que no abre, fallo de lectura, cierre del detector/cámara y modelos
  ausentes detectados antes de abrir la cámara.

Las salidas de la red de contrato **no son predicciones de RMN**. En una prueba de
lote apareció una diferencia float32 de 1,19e-7 por la reducción vectorizada; la
comprobación usa tolerancia absoluta 1e-6 y relativa 1e-5. El tensor de entrada sí se
exige idéntico bit a bit. No se interpretó esa diferencia como pérdida de precisión.

**MediaPipe real:** se utilizó `grace_hopper.jpg`, ejemplo ya presente en Matplotlib,
sin descargar fotografías. Se generaron en memoria un fondo negro y composiciones
con una, dos y tres copias del retrato. Todos los casos usaron un lienzo de
**1023 × 400**; cada retrato mide 341 × 400. Máximo de cinco rostros y umbrales 0.5.
Un detector nuevo por caso, un calentamiento y diez mediciones:

| Rostros esperados | Detectados | Recortes válidos | Mediana MediaPipe, resolución original | Entrada reducida a ancho 480 |
| --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 1,98 ms | 2,85 ms |
| 1 | 1 | 1 | 9,02 ms | 9,47 ms |
| 2 | 2 | 2 | 14,71 ms | 16,17 ms |
| 3 | 3 | 3 | 20,81 ms | 21,81 ms |

Cada rostro tuvo 478 landmarks y un tensor válido `(1, 3, 224, 224)`. Se revisó
visualmente la imagen de tres rostros con puntos, cajas y etiquetas «Sin pesos RMN».
La numeración sigue el orden de MediaPipe, que no necesariamente va de izquierda a
derecha. Son composiciones estáticas del mismo retrato: no demuestran detección con
personas distintas en movimiento. Estos tiempos incluyen conversión/preparación de
entrada para MediaPipe; **no incluyen RMN, captura o ventanas ni equivalen a FPS de
cámara**. La comparación breve de resoluciones no mostró beneficio que justifique
reducir por defecto; no establece una conclusión general de rendimiento.

**Comparación de recortes real, sin RMN:** en el retrato de 512 × 600, MediaPipe
recortó `(141,111)–(384,354)`, 243 × 243; Haar recortó `(155,105)–(377,327)`,
222 × 222. IoU: 0,7942. Tras el mismo preprocesamiento, diferencia absoluta media
entre tensores: **0,17073** en escala 0–1. Son entradas visualmente diferentes; no
se puede deducir de esa distancia cuál clasificaría mejor. Ambos tensores tuvieron
tres canales iguales, float32 y tamaño correcto.

Archivos de evidencia locales (ignorados por Git): `resultados/mediapipe_real.json`,
`mediapipe_480.json`, `comparacion_recortes.json` y `vista_prueba.png`. La vista se
guardó con la opción explícita `--vista`; no proviene de la cámara del usuario.

## Estado de las pruebas solicitadas

| Prueba | Estado |
| --- | --- |
| A — MediaPipe independiente | Verificado con modelo real y fotos estáticas, incluidos 0/1/2/3 rostros. |
| B — RMN independiente | Pendiente: checkpoint e imágenes con resultados esperados ausentes. |
| C — Integración con un rostro | Detección, recorte y tensor reales verificados; clasificación entrenada pendiente. |
| D — Múltiples rostros | Tres recortes reales y asociación de salidas simuladas verificados; varias personas en cámara pendiente. |
| E — Predicciones | Tensor idéntico al original verificado; comparación de probabilidades RMN lista para ejecutar al proporcionar pesos. |
| F — Rendimiento | Tiempos estáticos de MediaPipe/Haar medidos; RMN, conjunto y FPS de webcam pendientes. |
| G — Errores | Pruebas aprobadas para no rostros, cámara, modelos, checkpoint distinto y recortes inválidos. |

La prueba real de cámara (`--solo-mediapipe --sin-ventana --max-fotogramas 30`)
terminó con «Camera index out of range / No se pudo abrir la cámara 0». No se obtuvo
video. No se comprobó una ventana interactiva con cámara ni GPU. No hay cifras de
FPS completos, exactitud o mejora de RMN en esta entrega.

## Problemas prevenidos y pendientes

Se evitó la colisión de dos paquetes OpenCV al no instalar el `opencv-python` del
segundo requirements sobre `opencv-contrib-python`. Se eliminaron como posibles
fuentes de diferencias la doble conversión RGB, la doble normalización, el orden
incorrecto de clases y el dibujo antes de clasificar. Se añadió la asociación por
índice para que descartar un rostro no desplace las etiquetas. Se conservaron los
pesos y la arquitectura originales como único contrato aceptado.

La lentitud de la integración anterior no se puede diagnosticar definitivamente
sin su ejecución. Causas a investigar con las métricas: inferencias RMN seriales por
cada rostro, costo de landmarks y dibujo, uso de CPU y competencia entre hilos,
resolución y latencia de cámara. Recargar modelos, duplicar detectores o inferir con
gradientes no ocurre en la nueva aplicación.

Falta recibir el checkpoint exacto, ejecutar el comparador con fotos de referencia
y validar la cámara del usuario. El margen y el umbral de tamaño son parámetros
de partida. No se declara mejora ni empeoramiento de precisión. Para una comparación
de exactitud se necesitan imágenes representativas, etiquetas de referencia y una
evaluación separada del tiempo y de la equivalencia numérica.
