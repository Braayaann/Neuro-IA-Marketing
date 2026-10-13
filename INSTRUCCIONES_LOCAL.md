# Ejecutar en VS Code

1. Abre la carpeta Neuro-IA-Marketing y el archivo Entrenamiento_NeuroIA.ipynb.
2. Pulsa Seleccionar kernel → Entornos de Python → .venv (Python 3.12).
3. Ejecuta las celdas en orden. La sección 4 inicia el entrenamiento real.
4. Los archivos se guardan en modelos/CNN_fecha_hora. mejor_modelo.keras es el modelo elegido por validación; clases.json conserva el orden de sus salidas.

TensorFlow está configurado para CPU en Windows nativo. No se han iniciado las 30 épocas.

Para reinstalar las dependencias, desde la terminal PowerShell del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No hace falta activar el entorno ni cambiar la política de PowerShell.
El entorno usa Python 3.12 incluido en Codex como intérprete base. Si se elimina ese runtime, se debe recrear .venv con otra instalación de Python 3.12.
