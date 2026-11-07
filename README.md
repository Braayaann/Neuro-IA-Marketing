# Neuro IA Marketing

Prototipo local para Windows: seguimiento de mirada con iris binocular de MediaPipe o con L2CS-Net/Gaze360 preentrenado, y expresiones faciales con RMN. Una sola captura de cámara para todos los módulos. La orientación de cabeza solo genera avisos; no sustituye a la mirada.

El seguimiento usa los centros de ambos iris (468 y 473) respecto a las comisuras de cada ojo. Normaliza ambos ejes por el ancho del ojo y mide la posición vertical respecto al punto medio de las comisuras, para que la apertura de los párpados no cambie directamente la señal. Los párpados solo permiten comprobar la apertura mínima. Promedia las coordenadas relativas de ambos iris y utiliza esa señal en la calibración de nueve puntos. La cámara muestra un punto amarillo en cada iris cuando ambos ojos son utilizables. Solo se admite una persona para el seguimiento.

## Ejecutar

Desde la raíz del repositorio, en PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

También puedes abrir `ejecutar.bat`. Se abre el HTML del cliente y una vista de cámara.

- `C`: calibrar mirando nueve puntos y comprobar cinco puntos nuevos. Amarillo: preparación (1,2 s); verde: captura (2,4 s con iris; 4 s con L2CS). Mantén la mirada en el punto durante ambas etapas. Después vuelve a la página del navegador.
- `P`: pausar o reanudar el movimiento del cursor.
- `S`: activar o desactivar el suavizado durante la misma sesión, incluso desde el navegador. La cámara muestra su estado.
- `Q`: salir, incluso cuando el navegador tiene el foco.
- Cierra otras aplicaciones que usen la cámara.

Mantén la pantalla principal, su escala y tu posición durante la sesión. Cada persona debe recalibrar. El ajuste se conserva solo durante la ejecución. La calibración ajusta la conversión de coordenadas; no demuestra precisión. El mapa se borra al recargar la página.

Cada punto exige al menos 20 muestras estables, detección válida en el 75% de los fotogramas de captura y estabilidad en al menos el 80% de las muestras válidas. Se descartan las muestras alejadas de la mediana más de 0,012 en horizontal o 0,008 en vertical (unidades relativas al ancho del ojo). Las muestras aceptadas deben cubrir al menos 1,4 s y cinco de seis intervalos de la captura; también se comprueba que no haya un desplazamiento excesivo entre el inicio y el final. Son umbrales iniciales que requieren prueba con cámara.

Con L2CS se aplican los mismos controles a las dos salidas angulares, con tolerancia de 3 grados por componente y captura de 4 segundos para reunir suficientes muestras en CPU. No se mezclan señales ni calibraciones entre estimadores.

Si falla alguna condición, se repite el mismo punto y se muestra el motivo y el número de intento. Puedes pulsar C para empezar de nuevo o Q para salir. La señal permanece sin suavizar durante la captura. Estabilidad no equivale a precisión: el sistema no comprueba por sí solo que estés mirando el objetivo.

Con los nueve puntos se ajustan una transformación lineal y otra cuadrática regularizada (ridge de 0,01 en coordenadas estandarizadas, sin penalizar el intercepto). Después se capturan cinco posiciones distintas para comparar sus errores en píxeles. `--ajuste auto` elige la cuadrática solo si reduce el error medio al menos 5 píxeles y un 5%; en otro caso conserva la lineal. Si no puede calcular la cuadrática, mantiene la lineal. Estos cinco puntos se usan para seleccionar el ajuste: su error es una comprobación de selección, no una evaluación final independiente ni una garantía de precisión.

Puedes forzar `--ajuste lineal` o `--ajuste cuadratico` para comparar sesiones. La terminal registra los errores de ambos, el método seleccionado y sus parámetros; las predicciones fuera de pantalla no se recortan para calcular el error.

```powershell
# Solo el seguimiento por iris
.\.venv\Scripts\python.exe main.py --modo mirada
# Modelo preentrenado y selección de ajuste por comprobación (pesos ya instalados localmente)
.\.venv\Scripts\python.exe main.py --modo mirada --estimador l2cs --ajuste auto
# Forzar ajuste cuadrático con el mismo modelo
.\.venv\Scripts\python.exe main.py --modo mirada --estimador l2cs --ajuste cuadratico
# Comparación con el método anterior
.\.venv\Scripts\python.exe main.py --modo mirada --estimador iris --ajuste lineal
# Comparar comenzando sin suavizado (también puedes pulsar S)
.\.venv\Scripts\python.exe main.py --modo mirada --sin-suavizado
# Solo expresiones
.\.venv\Scripts\python.exe main.py --modo emociones
# Conversión directa de la señal relativa de ambos ojos, sin ajustar los nueve puntos
.\.venv\Scripts\python.exe main.py --modo mirada --sin-calibracion
# Clic al cerrar el ojo, como en el original (opcional)
.\.venv\Scripts\python.exe main.py --modo mirada --sin-calibracion --clic-parpadeo
# Verificar ambos modelos sin cámara
.\.venv\Scripts\python.exe main.py --diagnostico
# Verificar también L2CS, sin cámara
.\.venv\Scripts\python.exe main.py --estimador l2cs --diagnostico
```

Para detener el control del cursor también puedes mover el mouse a una esquina (protección de PyAutoGUI). No se guardan fotos ni videos.

El suavizado adaptativo One Euro está activado por defecto y se aplica a la señal seleccionada (promedio binocular o ángulos L2CS) antes de convertirla a pantalla. La calibración sigue capturando muestras sin filtrar. El filtro se reinicia al perder una muestra válida, pausar, recalibrar, alternarlo o recibir muestras separadas por más de 0,5 segundos. Los puntos amarillos de la cámara muestran las detecciones originales del iris, sin suavizar, también al utilizar L2CS.

Su configuración inicial es corte mínimo de 1 Hz, beta de 10 y corte de velocidad de 1 Hz, con tiempos reales entre muestras. Son valores de partida que requieren prueba con cámara. El filtro introduce retraso, no garantiza inmovilidad, no rechaza saltos aislados ni corrige desvíos de calibración. Referencia del algoritmo: [One Euro, Casiez et al.](https://gery.casiez.net/1euro/).

## Postura y datos para revisar las pruebas

La vista de cámara muestra `POSTURA SIMILAR`, `POSTURA CAMBIO`, `SIN REFERENCIA` o `SIN POSTURA`. La referencia es la mediana de las posturas de los puntos aceptados de la última calibración. Cambiar más de 8 grados, desplazar el centro más de un 15% del ancho de referencia del rostro o cambiar su ancho aparente más de un 15% activa el aviso. Estos umbrales son iniciales. El aviso no mueve, bloquea ni corrige el cursor.

La orientación se estima con `solvePnP`, un rostro genérico y parámetros aproximados de cámara. Los ángulos no están validados físicamente y no representan la dirección de los ojos. El tamaño aparente no es una distancia en centímetros.

La terminal emite líneas JSON con prefijo `[NEURO]`: configuración inicial, inicio de calibración, resultado de cada punto, parámetros del ajuste y un resumen de seguimiento cada dos segundos. Puedes copiar desde `inicio` hasta los resúmenes de la prueba y pegarlos en el chat. Indica también qué estabas mirando y si moviste la cabeza o cambiaste la luz.

- `ojos`: posiciones relativas de los iris 468 y 473, en ese orden; `iris`: su promedio sin suavizar.
- `dispersion_iris`: desviación estándar de la señal sin suavizar en los últimos dos segundos; incluye los movimientos voluntarios.
- `estimador`, `senal` y `dispersion_senal`: identificador y señal activa sin suavizar; promedio ocular para iris o dos ángulos en radianes para L2CS. `unidades_senal` se declara en el evento `inicio`. El orden angular sigue las dos cabezas del modelo original; no son los ángulos de cabeza de `postura`.
- `senal_valida_pct`: porcentaje de fotogramas con señal del estimador seleccionado. Puede diferir de `validas_pct`, que sigue midiendo los iris.
- `fps` y `validas_pct`: tasa del bucle y porcentaje de fotogramas con señal ocular válida en ese intervalo.
- `postura` y `referencia_postura`: `[pitch, yaw, roll, centro_x, centro_y, ancho]`; grados aproximados y coordenadas normalizadas de imagen.
- `delta_postura`: diferencias angulares, desplazamientos x/y en anchos de rostro de referencia y cambio proporcional de ancho.
- `estimacion_px`: última predicción utilizada por el seguimiento, con el suavizado seleccionado. Puede quedar fuera de pantalla; `dentro_pantalla` lo indica. Es `null` si el seguimiento está pausado, calibrando o sin señal/ajuste.
- `brillo_frame`: promedio de gris de toda la imagen (0–255). Es una referencia contextual, no una medición de iluminación de los ojos ni de lux.

Los eventos `punto_validacion` y `validacion_lista` registran los objetivos de comprobación y los errores de selección de cada ajuste. Los resúmenes de seguimiento libre no conocen dónde miras realmente. No se guardan imágenes ni videos, ni se crean archivos de registro automáticamente.

## Modelo preentrenado de mirada

`--estimador l2cs` utiliza [L2CS-Net/Gaze360](https://github.com/Ahmednull/L2CS-Net), ResNet50 con dos cabezas de 90 clases. Reutiliza MediaPipe para localizar un único rostro y comprobar que ambos ojos sean utilizables. El recorte se entrega sin espejo al modelo. Sus ángulos pasan por la misma calibración personal y comprobación de pantalla; todavía no se utiliza geometría física cámara-pantalla ni compensación de cabeza. `--sin-calibracion` se rechaza con L2CS porque los ángulos no son coordenadas de pantalla.

El estimador predeterminado sigue siendo `iris`, para conservar la comparación y la ejecución sin cargar torch. L2CS solo se carga cuando lo seleccionas y no descarga archivos al iniciar. Puedes elegir `--dispositivo-mirada cuda` si instalas un PyTorch compatible con CUDA; las dependencias actuales son CPU.

L2CS puede reducir los FPS. Una prueba local de cinco inferencias tras calentamiento, con entrada sintética, promedió aproximadamente 88 ms por inferencia en CPU; no mide el bucle completo ni garantiza 15 FPS. Comprueba `fps` en tus registros, especialmente al ejecutar también RMN. Los pesos preentrenados no garantizan menor error con tu cámara: compara las sesiones y los puntos de comprobación.

## Instalación

Python 3.12 de 64 bits en Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m emociones.recuperar_pesos
# Solo si vas a usar L2CS en una instalación nueva
.\.venv\Scripts\python.exe -m mirada.recuperar_pesos
```

MediaPipe FaceMesh trae su detector; no necesita el archivo `face_landmarker.task`. Los pesos RMN se guardan en `emociones/pesos/resmasking_net.pth` y quedan fuera de Git, igual que `.venv` y las cachés. La arquitectura en `emociones/rmn_autores` sí es necesaria para cargarlos y conserva la licencia de sus autores.

Los pesos de mirada se guardan en `mirada/pesos/L2CSNet_gaze360.pkl` (95,8 MB decimales), excluidos de Git. `python -m mirada.recuperar_pesos --verificar` comprueba su SHA-256. El enlace original de los autores devolvió 404, por lo que se utiliza una copia pública fijada a una revisión de Hugging Face; `mirada/pesos/procedencia.json` identifica la copia y su hash. No se verificó identidad binaria contra el original inaccesible. La carga utiliza `weights_only=True` y comprueba todas las claves de la arquitectura.

## Procedencia y límites

`mirada/heatmap.html` deriva del HTML del cliente. `main.py` conserva el fotograma reflejado e incorpora seguimiento binocular relativo, liberación de cámara, calibración y el clasificador RMN. Los clics se habilitan explícitamente. El HTML limita la acumulación cuando deja de recibir movimientos recientes; el mouse físico también dibuja en el mapa. Es una demostración del cursor, no una medición validada del tiempo de atención. Su diseño e imágenes externas requieren conexión a Internet.

El ajuste usa la señal del estimador seleccionado. Debes volver a calibrar al iniciar y al cambiar de estimador. Mover o girar la cabeza todavía puede alterar la estimación. `--sin-calibracion` solo se admite con iris: utiliza directamente la señal relativa, no reproduce la conversión original del cliente ni garantiza cubrir la pantalla. RMN clasifica expresiones faciales y no demuestra la emoción interna de una persona.

RMN: https://github.com/phamquiluan/ResidualMaskingNetwork
Pesos: https://huggingface.co/phamquiluan/ResidualMaskingNetwork
