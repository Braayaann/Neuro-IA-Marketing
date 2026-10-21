"""Obtener arquitectura fijada y copia publica de pesos L2CS-Net para el prototipo."""
from pathlib import Path
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json

BASE = Path(__file__).resolve().parent
COMMIT = 'a4d8f7fa5436a2b2b9f088471623b552a85811bd'
SHA = '8a7f3480d868dd48261e1d59f915b0ef0bb33ea12ea00938fb2168f212080665'
URL = 'https://huggingface.co/tianfxc/l2cs/resolve/424a499580d1217b57f8f1f3c2a5582c30cd6610/L2CSNet_gaze360.pkl?download=true'


def sha256(path):
    with path.open('rb') as archivo:
        return hashlib.file_digest(archivo, 'sha256').hexdigest()


def main():
    fuentes = BASE / 'l2cs_autores'
    pesos = BASE / 'pesos'
    fuentes.mkdir(exist_ok=True)
    pesos.mkdir(exist_ok=True)
    for remoto, local in [('l2cs/model.py', 'model.py'), ('LICENSE', 'LICENSE')]:
        destino = fuentes / local
        if not destino.exists():
            with urlopen(f'https://raw.githubusercontent.com/Ahmednull/L2CS-Net/{COMMIT}/{remoto}', timeout=60) as respuesta:
                destino.write_bytes(respuesta.read())
    destino = pesos / 'L2CSNet_gaze360.pkl'
    if not destino.exists():
        total = 95849977
        bloque = 8 * 1024 * 1024
        def obtener(inicio):
            fin = min(total - 1, inicio + bloque - 1)
            peticion = Request(URL, headers={'Range': f'bytes={inicio}-{fin}'})
            with urlopen(peticion, timeout=90) as respuesta:
                contenido = respuesta.read()
                if respuesta.status != 206 or respuesta.headers.get('Content-Range') != f'bytes {inicio}-{fin}/{total}':
                    raise RuntimeError('El servidor no entrego el rango solicitado.')
            if len(contenido) != fin - inicio + 1:
                raise RuntimeError('Descarga incompleta.')
            return inicio, contenido
        parcial = pesos / 'L2CSNet_gaze360.pkl.part'
        with ThreadPoolExecutor(max_workers=4) as pool, parcial.open('wb') as archivo:
            tareas = [pool.submit(obtener, i) for i in range(0, total, bloque)]
            recibido = 0
            for tarea in as_completed(tareas):
                inicio, contenido = tarea.result()
                archivo.seek(inicio)
                archivo.write(contenido)
                recibido += len(contenido)
                print(f'Descarga L2CS: {recibido * 100 // total}%', flush=True)
        if sha256(parcial) != SHA:
            raise RuntimeError('SHA-256 incorrecto. No se acepta la descarga.')
        parcial.replace(destino)
    if sha256(destino) != SHA:
        raise RuntimeError('Los pesos locales no coinciden con la copia documentada.')
    (pesos / 'procedencia.json').write_text(json.dumps({
        'arquitectura': 'https://github.com/Ahmednull/L2CS-Net',
        'commit_codigo': COMMIT, 'pesos_url': URL, 'sha256': SHA,
        'fuente': 'Copia de terceros tianfxc/l2cs; enlace Drive del README oficial devolvio 404.',
        'verificacion': 'Mismo SHA publicado tambien en dorni/SpeakerVid-5M-data-curation-models. No es autenticacion del autor.',
        'sha256_codigo': sha256(fuentes / 'model.py'),
    }, indent=2), encoding='utf-8')
    (fuentes / 'PROCEDENCIA.md').write_text(
        f'Arquitectura L2CS-Net copiada sin modificar de Ahmednull/L2CS-Net, commit {COMMIT}.\n'
        'Archivo original: l2cs/model.py. Licencia MIT adjunta.\n'
        'El cargador y la geometria del prototipo son adaptaciones locales; se usa Haar, no RetinaFace.\n', encoding='utf-8')
    print('Pesos L2CS descargados y SHA-256 verificado.', flush=True)


if __name__ == '__main__':
    main()
