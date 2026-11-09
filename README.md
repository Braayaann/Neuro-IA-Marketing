# Neuro IA Marketing

## Primera versión web

Portal React, API Flask y PostgreSQL. Incluye cuentas, anuncios, sesiones, calibración de mirada con ambos iris, clasificación de expresiones RMN y resultados con mapa de calor y exportación CSV.

Desde PowerShell en la raíz del repositorio:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_web.ps1
```

Abre [http://localhost:5000](http://localhost:5000). Las credenciales iniciales se guardan en `.local/acceso-inicial.txt`. Consulta [preparación, uso y despliegue](docs/APLICACION_WEB.md) para instalar la aplicación en otro equipo.

## Prototipo de escritorio

Prototipo local para Windows con seguimiento de mirada por iris binocular de MediaPipe o L2CS-Net/Gaze360 y expresiones faciales con RMN. Todos los módulos comparten una cámara.

El seguimiento normaliza los centros de ambos iris (468 y 473) por el ancho de cada ojo y mide la altura respecto al punto medio de sus comisuras. Comprueba la apertura, el ancho en píxeles y la posición del iris respecto a comisuras y párpados. En modo iris también descarta cambios aislados en la diferencia entre ambos ojos antes de utilizar el promedio binocular. La cámara muestra los centros detectados en amarillo. Solo se admite una persona para el seguimiento.

## Ejecutar

Desde la raíz del repositorio, en PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

También puedes abrir `ejecutar.bat`. Se abre el HTML del cliente y una vista de cámara.

- `C`: calibrar mirando nueve puntos y comprobar cinco puntos nuevos. Amarillo: preparación (1,2 s); verde: captura (2,4 s con iris; 4 s con L2CS). Mantén la mirada en el punto durante ambas etapas. Después vuelve a la página del navegador.
- `V` comprueba un perfil activo en cuatro puntos. Estima un desplazamiento común con los tres primeros y solo lo guarda si es consistente, moderado y reduce el error en el cuarto. Consulta `[NEURO] control_rapido` para ver las diferencias por punto.
- `M` abre el comparador a pantalla completa sobre el perfil cargado. Puedes usar el mouse físico para pulsar los botones. Mira las cruces y observa el círculo amarillo. Selecciona Lineal, Cuadrático o Local. Cada opción conserva sus propios ajustes mientras el panel está abierto.
- Las flechas desplazan la estimación en pasos de 2, 10 o 30 píxeles. Usa Ancho y Alto para ampliar o reducir el recorrido alrededor del centro en pasos de 2 %. Si el centro coincide y la estimación se queda corta al mirar hacia ambos bordes, aumenta el recorrido de ese eje.
- **Medir 5 puntos** compara todas las opciones y el perfil guardado con las mismas cinco fijaciones. El panel muestra el error medio en píxeles. Si editas los ajustes, los valores se recalculan con esas muestras. Repite la medición para confirmarlo con nuevas fijaciones. **Guardar selección** activa el método y los valores visibles para las siguientes sesiones. **Cancelar** descarta la edición.
- `P`: pausar o reanudar el movimiento del cursor.
- `S`: activar o desactivar el suavizado durante la misma sesión, incluso desde el navegador. La cámara muestra su estado.
- `Q`: salir, incluso cuando el navegador tiene el foco.
- Cierra otras aplicaciones que usen la cámara.

El perfil se guarda en `resultados/calibraciones` por estimador, método solicitado, índice de cámara y resolución de pantalla. Se recupera al volver a abrir el programa con esa configuración. Está pensado para una persona con la misma instalación. Si cambias de persona, pulsa C. Si vuelves otro día y notas un desvío, prueba primero V. El mapa se borra al recargar la página.

Cada punto exige al menos 20 muestras estables, detección válida en el 75% de los fotogramas de captura y estabilidad en al menos el 80% de las muestras válidas. Se descartan las muestras alejadas de la mediana más de 0,012 en horizontal o 0,008 en vertical (unidades relativas al ancho del ojo). Las muestras aceptadas deben cubrir al menos 1,4 s y cinco de seis intervalos de la captura; también se comprueba que no haya un desplazamiento excesivo entre el inicio y el final. Son umbrales iniciales que requieren prueba con cámara.

Con L2CS se aplican los mismos controles a las dos salidas angulares, con tolerancia de 3 grados por componente y captura de 4 segundos para reunir suficientes muestras en CPU. No se mezclan señales ni calibraciones entre estimadores.

Si falla alguna condición, se repite el mismo punto y se muestra el motivo y el número de intento. Puedes pulsar C para empezar de nuevo o Q para salir. La señal permanece sin suavizar durante la captura. Estabilidad no equivale a precisión: el sistema no comprueba por sí solo que estés mirando el objetivo.

Con los nueve puntos se entrenan los ajustes lineal y cuadrático. El modo automático de iris también prueba una corrección local que pondera los residuos del ajuste lineal por proximidad a las muestras de calibración. La selección usa cinco objetivos nuevos. Parte del lineal y evalúa primero el cuadrático y después el local. Cada candidato debe mejorar el error medio en al menos 5 píxeles y un 5 % respecto al elegido hasta entonces. Se tolera un aumento máximo de 5 píxeles en el peor objetivo. Estos cinco puntos sirven para seleccionar el ajuste. Una medición independiente requiere otras fijaciones.

Durante C y V en modo iris se comprueba la estabilidad de la postura dentro de cada fijación. Tras el tiempo de preparación se comparan las posturas medianas de los tercios de ese punto que tengan al menos tres mediciones. Una variación superior a 8 grados, un 15 % de ancho facial en posición o un 15 % en escala pide repetir ese punto. Cada intento toma su propia referencia. Si falta información de postura, siguen aplicándose los controles oculares.

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

El ajuste usa la señal del estimador seleccionado. Mover o girar la cabeza todavía puede alterar la estimación. `--sin-calibracion` solo se admite con iris y utiliza directamente la señal relativa. RMN clasifica expresiones faciales.

RMN: https://github.com/phamquiluan/ResidualMaskingNetwork
Pesos: https://huggingface.co/phamquiluan/ResidualMaskingNetwork
