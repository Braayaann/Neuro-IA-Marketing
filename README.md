# Neuro IA Marketing

Dos modulos independientes para el prototipo local:

- **emociones/**: deteccion de rostros con OpenCV y clasificacion de expresiones
  mediante RMN preentrenado en PyTorch.
- **mirada/**: estimacion experimental A/B con L2CS-Net, suavizado temporal,
  segundos por anuncio y vista de calor por zonas. La geometria es aproximada y
  las asignaciones deben comprobarse en el montaje.

## Preparacion

Utiliza Python 3.12 x64 y abre una terminal en la raiz del repositorio.
Con `.venv` ya creado:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si no existe el entorno, crealo con `python -m venv .venv` usando Python 3.12.
En el equipo donde se preparo el proyecto tambien esta disponible:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
```

## Expresiones faciales

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe main.py foto "C:\ruta\foto.jpg"
```

Q o Escape cierra la camara. `main.py` llama al mismo programa de `emociones/rmn.py`.
Para recuperar los pesos en un clon nuevo:

```powershell
.\.venv\Scripts\python.exe emociones\recuperar_pesos.py
```

Consulta [emociones/README.md](emociones/README.md) para opciones, procedencia y limites.

## Prueba de mirada A/B

Cierra primero el programa que este usando la camara.

```powershell
.\.venv\Scripts\python.exe -m mirada.descargar
.\.venv\Scripts\python.exe -m mirada.probar
```

H alterna el calor por zonas; R guarda y reinicia la sesion; T inicia una prueba
guiada de 32 segundos; V muestra la camara; Q o Escape guarda el resumen y sale.
Los porcentajes A/B corresponden al tiempo asignado; la cobertura muestra cuanto
del tiempo total pudo asignarse. No se considera preferencia.
Consulta [mirada/README.md](mirada/README.md) para configuracion e interpretacion.

## Archivos locales y Git

Los pesos de `emociones/pesos/` y `mirada/pesos/`, `.venv`, caches y resultados no se
suben a Git. Sus archivos de procedencia, licencias y scripts de recuperacion si se
conservan en el repositorio. Los scripts verifican el SHA-256 de los pesos.

No se graba ni se sube video. Las expresiones estimadas no indican por si solas la
emocion interna o el agrado por un anuncio; las estimaciones de mirada tampoco
demuestran preferencia. La prueba A/B aun no es una medicion validada de atencion.
