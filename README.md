# Neuro IA Marketing

Prototipo local con un punto de entrada y tres modos:

| Comando | Funcion |
| --- | --- |
| `python main.py` | Mirada L2CS + expresiones MediaPipe/RMN, compartiendo una camara |
| `python main.py --modo emociones` | Camara con deteccion facial MediaPipe y clasificacion RMN |
| `python main.py --modo mirada` | Dos anuncios con estimacion de mirada, tiempos y calor por zonas |

Los comandos se ejecutan desde la raiz del repositorio. En Windows puedes usar
`.\.venv\Scripts\python.exe` en lugar de `python` para seleccionar el entorno correcto.
El modo conjunto esta preparado inicialmente para una persona; el modo emociones
conserva el soporte de varios rostros de la integracion original.

## Instalar

Python 3.12 x64:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Se usa un solo proveedor de cv2: opencv-contrib-python. Si el entorno anterior
tiene opencv-python, desinstalalo antes de instalar los requisitos. Los pesos
no se incluyen en Git; este equipo ya los tiene en sus carpetas locales.

```powershell
.\.venv\Scripts\python.exe emociones\recuperar_pesos.py
.\.venv\Scripts\python.exe -m mirada.descargar
```

MediaPipe necesita `emociones/pesos/face_landmarker.task`. Si clonas el repositorio,
descarga ese archivo con `python -m emociones.descargar_detector`.

## Probar ambos modelos

```powershell
.\.venv\Scripts\python.exe main.py
```

Se muestran dos anuncios de ejemplo y la expresion estimada de la persona. Para
usar tus imagenes:

```powershell
.\.venv\Scripts\python.exe main.py --anuncio-a "C:\ruta\A.jpg" --anuncio-b "C:\ruta\B.jpg"
```

- H: mostrar u ocultar calor agregado por anuncio.
- V: vista de camara con expresiones; no graba.
- R: guardar y reiniciar los tiempos de mirada.
- T: prueba guiada A/B de 32 segundos; oculta predicciones durante los objetivos.
- Q o Escape: guardar el resumen y salir.

En el modo solo emociones, M alterna los puntos faciales y R alterna RMN.
Los porcentajes de clase RMN son salidas del clasificador, no una exactitud medida.
Los porcentajes A/B se calculan sobre el tiempo asignado; la cobertura muestra
cuanto del tiempo total se pudo asignar. Fuera de pantalla y sin asignacion
se registran por separado. No se graban fotos ni video por defecto.

## Configuracion y carpetas

- `main.py`: selecciona el modo; no contiene implementaciones duplicadas.
- `emociones/`: aplicacion MediaPipe/RMN, adaptador para frames compartidos,
  clasificador OpenCV original para comparacion y pesos en `pesos/`.
- `mirada/`: L2CS, geometria, suavizado, interfaz A/B y resultados locales.
- `config.py`: opciones de MediaPipe/RMN y ruta de sus pesos.
- `mirada/config.json`: pantalla, distancia estimada y camara de los modos mirada/todo.
- `utilidades/`: recortes y mediciones del modulo facial.
- `pruebas/`: pruebas de integracion; `referencias/`: codigo de comparacion original.
- `docs/`: informes de integracion anteriores y procedencia; sus rutas y comandos
  son historicos. Esta guia es la referencia para la estructura actual.

El modo conjunto usa el indice y resolucion de `mirada/config.json` para la unica
camara. MediaPipe recibe esos mismos fotogramas; su configuracion de captura en
`config.py` solo se utiliza al ejecutar el modo emociones.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s pruebas -v
.\.venv\Scripts\python.exe -m unittest mirada.test_geometria mirada.test_seguimiento -v
```

Los parametros de mirada son aproximados. El mapa es por zonas, no por pixeles,
y debe comprobarse en el montaje real. Mirar un anuncio no demuestra preferencia;
la expresion clasificada tampoco demuestra el estado emocional interno.
`.venv`, pesos, caches y resultados permanecen excluidos de Git.
