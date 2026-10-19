# RMN original

Esta versión usa únicamente el checkpoint `benchmarks/resmasking_net` de
[Residual Masking Network](https://huggingface.co/phamquiluan/ResidualMaskingNetwork).
Los pesos están en `modelo/pesos/resmasking_net.pth` y su procedencia y hash
en `modelo/pesos/procedencia.json`. El código de los autores y su licencia
se conservan en `modelo/rmn_autores/`.

## Preparación

Desde la raíz del repositorio `Neuro-IA-Marketing`, en PowerShell:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r modelo\requirements.txt
```

## Probar

```powershell
.\.venv\Scripts\python.exe modelo\rmn.py foto "C:\ruta\foto.jpg"
.\.venv\Scripts\python.exe modelo\rmn.py foto "C:\ruta\rostro.png" --recortado
.\.venv\Scripts\python.exe modelo\rmn.py camara
```

Q o Escape cierra la cámara. `--indice 1` selecciona otra cámara.
No se graba ni se sube video. El detector de esta prueba es OpenCV; MediaPipe todavía
no está integrado aquí. El clasificador conserva las siete categorías del modelo.
Las salidas son expresiones estimadas, no mediciones del estado emocional interno.

El 74,14 % publicado corresponde al benchmark FER2013; no garantiza esa precisión
en la cámara del proyecto. Este programa usa una sola pasada, sin TTA.

## Pesos al clonar el repositorio

El checkpoint de aproximadamente 526 MiB se conserva localmente y está excluido de
Git. El código, la licencia y la procedencia sí pueden subirse a GitHub. Para obtener
los pesos en otro computador, ejecuta desde la raíz del repositorio:

```powershell
Invoke-WebRequest -Uri "https://huggingface.co/phamquiluan/ResidualMaskingNetwork/resolve/main/benchmarks/resmasking_net?download=true" -OutFile ".\modelo\pesos\resmasking_net.pth"
```

Al iniciar, `rmn.py` verifica el SHA-256 antes de cargar el archivo.
El comando de creación del entorno usa el Python disponible en este equipo; en otro
computador con Python 3.12 instalado puede sustituirse por `python -m venv .venv`.

