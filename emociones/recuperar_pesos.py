"""Recuperar el checkpoint RMN elegido y verificar su integridad."""
from pathlib import Path
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import time

BASE = Path(__file__).resolve().parent
SHA256 = '5bd51cff4ad2f4e5ee34fd9a1fb838ebac606e22bd85475947fd746b749efe87'
URL = 'https://huggingface.co/phamquiluan/ResidualMaskingNetwork/resolve/main/benchmarks/resmasking_net?download=true'
TOTAL = 551635469


def verificar(ruta):
    with ruta.open('rb') as archivo:
        if hashlib.file_digest(archivo, 'sha256').hexdigest() != SHA256:
            raise ValueError(f'SHA-256 incorrecto: {ruta}. No se acepta este archivo.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verificar', action='store_true', help='Solo comprobar el archivo local, sin descargar.')
    args = parser.parse_args()
    destino = BASE / 'pesos' / 'resmasking_net.pth'
    if destino.exists():
        verificar(destino)
        print('RMN original presente y SHA-256 correcto:', destino)
        return
    if args.verificar:
        raise FileNotFoundError(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = BASE.parent / '.tmp' / 'recuperacion_rmn'
    temporal.mkdir(parents=True, exist_ok=True)
    parcial = temporal / 'resmasking_net.pth.part'
    bloque = 8 * 1024 * 1024

    def obtener(inicio):
        fin = min(TOTAL - 1, inicio + bloque - 1)
        for intento in range(4):
            try:
                solicitud = Request(URL, headers={'Range': f'bytes={inicio}-{fin}'})
                with urlopen(solicitud, timeout=90) as respuesta:
                    if respuesta.status != 206 or respuesta.headers.get('Content-Range') != f'bytes {inicio}-{fin}/{TOTAL}':
                        raise RuntimeError('El servidor no entrego el rango solicitado.')
                    contenido = respuesta.read()
                if len(contenido) != fin - inicio + 1:
                    raise RuntimeError('Bloque incompleto.')
                return inicio, contenido
            except Exception:
                if intento == 3:
                    raise
                time.sleep(1)

    print('Descargando RMN original (526 MiB)...', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool, parcial.open('wb') as archivo:
        tareas = [pool.submit(obtener, i) for i in range(0, TOTAL, bloque)]
        recibido, progreso = 0, -1
        for tarea in as_completed(tareas):
            inicio, contenido = tarea.result()
            archivo.seek(inicio)
            archivo.write(contenido)
            recibido += len(contenido)
            porcentaje = recibido * 100 // TOTAL
            if porcentaje // 10 > progreso:
                print(f'Descarga: {porcentaje}%', flush=True)
                progreso = porcentaje // 10
    verificar(parcial)
    if destino.exists():
        raise FileExistsError('Aparecio un archivo en la ruta destino; se conserva sin sobrescribir.')
    parcial.replace(destino)
    print('RMN original recuperado y SHA-256 correcto:', destino)


if __name__ == '__main__':
    main()
