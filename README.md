# Neuro IA Marketing — Seguimiento ocular

Esta rama contiene únicamente el módulo de mirada estimada, calibración y mapas de calor. El código se ejecuta desde la raíz del repositorio. El módulo de emociones permanece en feature/integracion-mediapipe-rmn.

## Ejecutar en este equipo

Abrir ejecutar.bat o usar PowerShell desde esta carpeta:

```powershell
.\.venv\Scripts\python.exe main.py
```

Se abre http://127.0.0.1:8765/. No se debe abrir el HTML directamente. Si el puerto está ocupado:

```powershell
.\.venv\Scripts\python.exe main.py --puerto 8767
```

1. Iniciar cámara y mantener fija la ventana y su zoom.
2. Iniciar calibración y mirar los nueve objetivos.
3. Validar con nueve objetivos diferentes.
4. Revisar la comparación R/A/B. El seguimiento solo se habilita si el modelo seleccionado cumple los criterios.
5. Iniciar seguimiento, pausar y guardar el mapa.
6. Detener cámara y cerrar el servidor con Ctrl+C.

Los mapas de R, A, B y mouse se conservan por separado. La demostración con mouse no mide mirada. Cambiar la geometría de la ventana obliga a recalibrar. Los resultados se guardan localmente en resultados, sin fotos ni video de cámara por defecto. Es un prototipo experimental y requiere validación humana de su precisión.

## Instalación en otro equipo

Requiere Python 3.11 de 64 bits. Desde la raíz del repositorio:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force modelos | Out-Null
Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' -OutFile 'modelos/face_landmarker.task'
.\.venv\Scripts\python.exe main.py --diagnostico
```

El modelo MediaPipe se descarga por separado y queda ignorado por Git. Su SHA256 esperado es 64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff. La procedencia se explica en modelos/PROCEDENCIA.md. No se necesitan los pesos RMN.

## Carpetas necesarias

- calibracion ajusta y compara los modelos R/A/B.
- deteccion obtiene las características oculares y la orientación de cabeza con MediaPipe.
- mirada transforma y filtra las estimaciones.
- heatmap acumula y dibuja los mapas.
- interfaz contiene el servidor, los controles y el HTML en interfaz/web/heatmap.html.
- modelos contiene el archivo MediaPipe descargado y su procedencia.

El entorno .venv, las cachés, los pesos y resultados quedan fuera del commit. Las pruebas y los respaldos de desarrollo se conservan en la copia original del módulo, fuera de esta rama.