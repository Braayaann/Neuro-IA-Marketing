# Neuro IA Marketing

Prototipo local para Windows: iris con MediaPipe FaceMesh y expresiones faciales con RMN. Una sola captura de cámara para ambos. No usa L2CS ni estima la mirada mediante ángulos de la cabeza.

## Ejecutar

Desde la raíz del repositorio, en PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

También puedes abrir `ejecutar.bat`. Se abre el HTML del cliente y una vista de cámara.

- `C`: calibrar mirando nueve puntos. Después vuelve a la página del navegador.
- `P`: pausar o reanudar el movimiento del cursor.
- `Q`: salir, incluso cuando el navegador tiene el foco.
- Cierra otras aplicaciones que usen la cámara.

Mantén la pantalla principal, su escala y tu posición durante la sesión. Cada persona debe recalibrar. El ajuste se conserva solo durante la ejecución. La calibración ajusta la conversión de coordenadas; no demuestra precisión. El mapa se borra al recargar la página.

```powershell
# Solo el seguimiento por iris
.\.venv\Scripts\python.exe main.py --modo mirada
# Solo expresiones
.\.venv\Scripts\python.exe main.py --modo emociones
# Conversión directa del ejemplo del cliente, sin ajustar los nueve puntos
.\.venv\Scripts\python.exe main.py --modo mirada --sin-calibracion
# Clic al cerrar el ojo, como en el original (opcional)
.\.venv\Scripts\python.exe main.py --modo mirada --sin-calibracion --clic-parpadeo
# Verificar ambos modelos sin cámara
.\.venv\Scripts\python.exe main.py --diagnostico
```

Para detener el control del cursor también puedes mover el mouse a una esquina (protección de PyAutoGUI). No se guardan fotos ni videos.

## Instalación

Python 3.12 de 64 bits en Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m emociones.recuperar_pesos
```

MediaPipe FaceMesh trae su detector; no necesita el archivo `face_landmarker.task`. Los pesos RMN se guardan en `emociones/pesos/resmasking_net.pth` y quedan fuera de Git, igual que `.venv` y las cachés. La arquitectura en `emociones/rmn_autores` sí es necesaria para cargarlos y conserva la licencia de sus autores.

## Procedencia y límites

`mirada/heatmap.html` deriva del HTML del cliente. `main.py` utiliza su punto de iris 475 y el fotograma reflejado; agrega liberación de cámara, calibración y el clasificador RMN. Los clics se habilitan explícitamente. El HTML limita la acumulación cuando deja de recibir movimientos recientes; el mouse físico también dibuja en el mapa. Es una demostración del cursor, no una medición validada del tiempo de atención. Su diseño e imágenes externas requieren conexión a Internet.

El ajuste usa coordenadas del iris dentro de la cámara, no orientación de cabeza ni un modelo de mirada preentrenado. Mover la cabeza puede alterar la estimación. RMN clasifica expresiones faciales y no demuestra la emoción interna de una persona.

RMN: https://github.com/phamquiluan/ResidualMaskingNetwork
Pesos: https://huggingface.co/phamquiluan/ResidualMaskingNetwork
