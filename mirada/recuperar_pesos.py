"""Descarga explícita y verificada de la copia registrada de L2CS/Gaze360."""
import argparse
import shutil
from urllib.request import urlopen

from .l2cs import PESOS, verificar_pesos

URL = 'https://huggingface.co/tianfxc/l2cs/resolve/424a499580d1217b57f8f1f3c2a5582c30cd6610/L2CSNet_gaze360.pkl'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verificar', action='store_true')
    args = parser.parse_args()
    if PESOS.exists() or args.verificar:
        verificar_pesos()
    else:
        PESOS.parent.mkdir(parents=True, exist_ok=True)
        temporal = PESOS.with_suffix('.pkl.part')
        print('Descargando L2CS/Gaze360 (91,4 MiB)...', flush=True)
        try:
            with urlopen(URL, timeout=90) as respuesta, temporal.open('wb') as archivo:
                shutil.copyfileobj(respuesta, archivo, 1024*1024)
            verificar_pesos(temporal)
            if PESOS.exists():
                raise FileExistsError('El destino apareció durante la descarga; no se sobrescribe.')
            temporal.replace(PESOS)
        finally:
            temporal.unlink(missing_ok=True)
    print('L2CS/Gaze360 presente y SHA-256 correcto:', PESOS)


if __name__ == '__main__':
    main()
