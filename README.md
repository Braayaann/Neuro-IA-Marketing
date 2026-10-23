# Neuro IA Marketing

Ejecuta desde esta carpeta, usando Python 3.12 y el entorno .venv:

```powershell
.\.venv\Scripts\python.exe main.py
```

- Ambos modelos: main.py
- Solo expresiones MediaPipe + RMN: main.py --modo emociones
- Solo mirada L2CS: main.py --modo mirada

El modo conjunto comparte una camara y esta preparado para una persona.
H muestra calor por anuncio, V muestra la camara, R guarda/reinicia tiempos,
T inicia la prueba guiada y Q/Escape guarda el resumen y cierra.
En modo emociones, M alterna los puntos faciales y R alterna RMN.

## Instalar en otro equipo

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe emociones\recuperar_pesos.py
.\.venv\Scripts\python.exe -m emociones.descargar_detector
.\.venv\Scripts\python.exe -m mirada.descargar
```

## Archivos necesarios

- main.py: entrada comun.
- config.py: parametros y pesos de expresiones.
- emociones/: MediaPipe, RMN, pesos y descargadores.
- mirada/: L2CS, configuracion de pantalla, suavizado e interfaz.
- utilidades/: recortes y mediciones que utiliza la aplicacion.
- requirements.txt: todas las dependencias.
- .gitignore: excluye entorno, pesos, caches y resultados.

Los directorios rmn_autores y l2cs_autores contienen las arquitecturas que
necesitan los pesos para ejecutarse. Se conservan sus licencias y procedencia.
El modo conjunto usa la camara indicada en mirada/config.json; el modo
emociones usa config.py. Los pesos de este equipo permanecen en sus carpetas.

Los porcentajes A/B describen tiempo de mirada estimado, no preferencia.
La expresion clasificada no demuestra el estado emocional interno.
No se graba video por defecto. Los resumenes quedan en mirada/resultados/.
