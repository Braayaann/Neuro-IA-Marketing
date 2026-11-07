# Neuro IA Marketing

Prototipo local para Windows: iris con MediaPipe FaceMesh y expresiones faciales con RMN. Una sola captura de cámara para ambos. No usa L2CS ni estima la mirada mediante ángulos de la cabeza.

El seguimiento usa los centros de ambos iris (468 y 473) respecto a las comisuras de cada ojo. Normaliza ambos ejes por el ancho del ojo y mide la posición vertical respecto al punto medio de las comisuras, para que la apertura de los párpados no cambie directamente la señal. Los párpados solo permiten comprobar la apertura mínima. Promedia las coordenadas relativas de ambos iris y utiliza esa señal en la calibración de nueve puntos. La cámara muestra un punto amarillo en cada iris cuando ambos ojos son utilizables. Solo se admite una persona para el seguimiento.

## Ejecutar

Desde la raíz del repositorio, en PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

También puedes abrir `ejecutar.bat`. Se abre el HTML del cliente y una vista de cámara.

- `C`: calibrar mirando nueve puntos. Amarillo: preparación (1,2 s); verde: captura (2,4 s). Mantén la mirada en el punto durante ambas etapas. Después vuelve a la página del navegador.
- `P`: pausar o reanudar el movimiento del cursor.
- `S`: activar o desactivar el suavizado durante la misma sesión, incluso desde el navegador. La cámara muestra su estado.
- `Q`: salir, incluso cuando el navegador tiene el foco.
- Cierra otras aplicaciones que usen la cámara.

Mantén la pantalla principal, su escala y tu posición durante la sesión. Cada persona debe recalibrar. El ajuste se conserva solo durante la ejecución. La calibración ajusta la conversión de coordenadas; no demuestra precisión. El mapa se borra al recargar la página.

Cada punto exige al menos 20 muestras estables, detección válida en el 75% de los fotogramas de captura y estabilidad en al menos el 80% de las muestras válidas. Se descartan las muestras alejadas de la mediana más de 0,012 en horizontal o 0,008 en vertical (unidades relativas al ancho del ojo). Las muestras aceptadas deben cubrir al menos 1,4 s y cinco de seis intervalos de la captura; también se comprueba que no haya un desplazamiento excesivo entre el inicio y el final. Son umbrales iniciales que requieren prueba con cámara.

Si falla alguna condición, se repite el mismo punto y se muestra el motivo y el número de intento. Puedes pulsar C para empezar de nuevo o Q para salir. La señal permanece sin suavizar durante la captura y la transformación lineal de nueve puntos no cambia. Estabilidad no equivale a precisión: el sistema no comprueba por sí solo que estés mirando el objetivo.

```powershell
# Solo el seguimiento por iris
.\.venv\Scripts\python.exe main.py --modo mirada
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
```

Para detener el control del cursor también puedes mover el mouse a una esquina (protección de PyAutoGUI). No se guardan fotos ni videos.

El suavizado adaptativo One Euro está activado por defecto y se aplica al promedio binocular antes de convertirlo a pantalla. La calibración sigue capturando muestras sin filtrar. El filtro se reinicia al perder una muestra válida, pausar, recalibrar, alternarlo o recibir muestras separadas por más de 0,5 segundos. Los puntos amarillos de la cámara muestran las detecciones originales, sin suavizar.

Su configuración inicial es corte mínimo de 1 Hz, beta de 10 y corte de velocidad de 1 Hz, con tiempos reales entre muestras. Son valores de partida que requieren prueba con cámara. El filtro introduce retraso, no garantiza inmovilidad, no rechaza saltos aislados ni corrige desvíos de calibración. Referencia del algoritmo: [One Euro, Casiez et al.](https://gery.casiez.net/1euro/).

## Instalación

Python 3.12 de 64 bits en Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m emociones.recuperar_pesos
```

MediaPipe FaceMesh trae su detector; no necesita el archivo `face_landmarker.task`. Los pesos RMN se guardan en `emociones/pesos/resmasking_net.pth` y quedan fuera de Git, igual que `.venv` y las cachés. La arquitectura en `emociones/rmn_autores` sí es necesaria para cargarlos y conserva la licencia de sus autores.

## Procedencia y límites

`mirada/heatmap.html` deriva del HTML del cliente. `main.py` conserva el fotograma reflejado e incorpora seguimiento binocular relativo, liberación de cámara, calibración y el clasificador RMN. Los clics se habilitan explícitamente. El HTML limita la acumulación cuando deja de recibir movimientos recientes; el mouse físico también dibuja en el mapa. Es una demostración del cursor, no una medición validada del tiempo de atención. Su diseño e imágenes externas requieren conexión a Internet.

El ajuste usa el promedio de las posiciones de ambos iris relativas a sus ojos, no orientación de cabeza ni un modelo de mirada preentrenado. Debes volver a calibrar al iniciar: la nueva señal sustituye a las coordenadas absolutas del iris. Este cambio reduce la dependencia directa del desplazamiento del rostro en la imagen, pero mover o girar la cabeza todavía puede alterar la estimación. `--sin-calibracion` utiliza directamente la señal relativa, no reproduce la conversión original del cliente ni garantiza cubrir la pantalla. RMN clasifica expresiones faciales y no demuestra la emoción interna de una persona.

RMN: https://github.com/phamquiluan/ResidualMaskingNetwork
Pesos: https://huggingface.co/phamquiluan/ResidualMaskingNetwork
