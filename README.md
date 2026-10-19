# RMN original

Esta versión usa únicamente el checkpoint `benchmarks/resmasking_net` de
[Residual Masking Network](https://huggingface.co/phamquiluan/ResidualMaskingNetwork).
Los pesos están en `modelos/rmn_benchmark/resmasking_net.pth` y su procedencia y hash
en `modelos/rmn_benchmark/procedencia.json`. El código de los autores y su licencia
se conservan en `rmn_autores/`.

## Preparación

Desde esta carpeta en PowerShell, con Python 3.12 instalado:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Probar

```powershell
.\.venv\Scripts\python.exe rmn.py foto "C:\ruta\foto.jpg"
.\.venv\Scripts\python.exe rmn.py foto "C:\ruta\rostro.png" --recortado
.\.venv\Scripts\python.exe rmn.py camara
```

Q o Escape cierra la cámara. `--indice 1` selecciona otra cámara.
No se graba ni se sube video. El detector de esta prueba es OpenCV; MediaPipe todavía
no está integrado aquí. El clasificador conserva las siete categorías del modelo.
Las salidas son expresiones estimadas, no mediciones del estado emocional interno.

El 74,14 % publicado corresponde al benchmark FER2013; no garantiza esa precisión
en la cámara del proyecto. Este programa usa una sola pasada, sin TTA.

