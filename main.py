"""Iniciar la prueba local OpenCV + RMN desde la raiz del proyecto."""
import sys

from modelo.rmn import main as ejecutar_rmn


if __name__ == '__main__':
    ejecutar_rmn(sys.argv[1:] or ['camara'])
