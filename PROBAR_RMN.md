# Probar RMN original y RMN int8

El original es el checkpoint benchmarks/resmasking_net asociado al 74,14 % publicado.
El archivo se verifica contra el SHA-256 publicado en Hugging Face. Se conservan siete clases.
La versión int8 procede de otro checkpoint; comparar ambos no aísla el efecto de cuantizar.

Desde PowerShell en esta carpeta:

```powershell
.\.venv\Scripts\python.exe comparar_rmn.py comparar
```

Esto usa las mismas 1527 imágenes de validación guardadas. No utiliza test, ni realiza entrenamiento.
La comparación es exploratoria: puede haber solapamiento con FER2013 de preentrenamiento.
Se utiliza una sola pasada por imagen; el procedimiento publicado incluye múltiples transformaciones (TTA).
Por eso esta prueba no es una reproducción del 74,14 % del benchmark.
Los resultados y las matrices se guardan en resultados_preentrenados/RMN_original_vs_int8_... .
La latencia es en CPU e incluye redimensionado e inferencia; excluye lectura, detección y arranque.

Para una foto completa:

```powershell
.\.venv\Scripts\python.exe comparar_rmn.py foto "C:\ruta\foto.jpg"
```

Si la foto ya está recortada para contener solo el rostro, añade --recortado.
Se muestra una estimación de expresión facial, no una medición del estado emocional interno.

Para abrir tu cámara con el original:

```powershell
.\.venv\Scripts\python.exe comparar_rmn.py camara --version original
```

Para probar la versión cuantizada, cambia original por int8. Pulsa Q o Escape para salir.
La cámara no se abre durante la comparación y no se graba ni se sube video.
La prueba de cámara usa un detector frontal sencillo de OpenCV. No es una prueba del sistema completo.

En WSL usa el Python de tu entorno Linux con estas mismas opciones, sin el prefijo .venv de Windows.
