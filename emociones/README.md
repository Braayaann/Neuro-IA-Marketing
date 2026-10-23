# Expresiones faciales

Desde la raiz del repositorio, con las dependencias de requirements.txt instaladas:

```powershell
.\.venv\Scripts\python.exe main.py --modo emociones
```

Este modo usa MediaPipe para localizar rostros y RMN para clasificar sus expresiones.
M muestra u oculta landmarks, R alterna RMN y Q/Escape cierra la camara.
Para ejecutar emociones y mirada simultaneamente usa `python main.py`.

## Pesos

- `emociones/pesos/resmasking_net.pth`: clasificador RMN, aproximadamente 526 MiB.
- `emociones/pesos/face_landmarker.task`: detector MediaPipe.
- `config.py` en la raiz: rutas, configuracion y parametros del recorte.

Recuperacion en un clon nuevo:

```powershell
.\.venv\Scripts\python.exe emociones\recuperar_pesos.py
.\.venv\Scripts\python.exe -m emociones.descargar_detector
```

El recuperador de RMN verifica el SHA-256 antes de aceptar el archivo.
Agrega `--verificar` para verificar RMN sin red. Los pesos estan excluidos de Git.

## Comparacion con OpenCV original

`rmn.py` conserva el recorte Haar original como alternativa para comparar con
el recorte MediaPipe. El modo integrado utiliza `rmn_detector.py`.

```powershell
.\.venv\Scripts\python.exe emociones\rmn.py camara
.\.venv\Scripts\python.exe emociones\rmn.py foto "C:\ruta\foto.jpg"
```

## Procedencia

Checkpoint `benchmarks/resmasking_net` de
[Residual Masking Network](https://huggingface.co/phamquiluan/ResidualMaskingNetwork).
Su procedencia y hash estan en `pesos/procedencia.json`. Arquitectura y licencia
MIT de los autores conservadas en `rmn_autores/`.

Se mantienen las siete clases originales. El 74.14% publicado corresponde al
benchmark FER2013 y no es una exactitud medida con esta camara. Las salidas son
expresiones estimadas, no mediciones del estado emocional interno.
No se graba ni se sube video por defecto.
