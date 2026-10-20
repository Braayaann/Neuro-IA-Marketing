# Neuro IA Marketing — OpenCV + RMN

El programa local detecta caras con el detector frontal Haar de OpenCV y clasifica
sus expresiones con el checkpoint original de Residual Masking Network, en PyTorch.
Se utiliza directamente el recorrido de `modelo/rmn.py`, sin MediaPipe, landmarks
ni recortes adicionales. `main.py` es un acceso al mismo programa desde la raíz.

## Ejecutar

Desde la raíz del repositorio, con las dependencias instaladas:

```powershell
.\.venv\Scripts\python.exe main.py
```

Q o Escape cierra la cámara. También puedes elegir otra cámara o probar una imagen:

```powershell
.\.venv\Scripts\python.exe main.py camara --indice 1
.\.venv\Scripts\python.exe main.py foto "C:\ruta\foto.jpg"
.\.venv\Scripts\python.exe main.py foto "C:\ruta\rostro.png" --recortado
```

`modelo/README.md` contiene la instalación, la descarga de los pesos y la procedencia.
No se graba ni se sube video. Se conservan las siete categorías originales de RMN.
Las salidas son expresiones faciales estimadas, no mediciones de emoción interna,
atención, mirada o agrado por el anuncio. No hay identificación de personas.

El 74,14 % publicado pertenece al benchmark FER2013 y no garantiza ese resultado en
la cámara del proyecto. Debe comprobarse con el entorno y las personas de uso real.
