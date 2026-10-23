"""Descargar el detector oficial MediaPipe Face Landmarker para un clon nuevo."""
from pathlib import Path
from urllib.request import urlopen
import os
import zipfile

URL = ('https://storage.googleapis.com/mediapipe-models/face_landmarker/'
       'face_landmarker/float16/1/face_landmarker.task')


def main():
    destino = Path(__file__).resolve().parent / 'pesos' / 'face_landmarker.task'
    destino.parent.mkdir(exist_ok=True)
    if destino.exists():
        print('Detector existente:', destino)
        return
    temporal = destino.with_suffix('.task.part')
    try:
        with urlopen(URL, timeout=60) as respuesta, temporal.open('wb') as archivo:
            while bloque := respuesta.read(1024*1024):
                archivo.write(bloque)
        # El bundle oficial es un ZIP con los modelos TFLite necesarios.
        if not zipfile.is_zipfile(temporal):
            raise ValueError('La descarga no contiene un bundle MediaPipe valido.')
        os.replace(temporal, destino)
    finally:
        temporal.unlink(missing_ok=True)
    print('Detector descargado:', destino)


if __name__ == '__main__':
    main()
