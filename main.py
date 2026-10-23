"""Entrada comun: emociones MediaPipe/RMN y mirada L2CS con una sola camara."""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Ejemplos: python main.py | python main.py --modo emociones | "
               "python main.py --modo mirada --anuncio-a A.jpg --anuncio-b B.jpg. "
               "Las opciones restantes se pasan al modulo seleccionado.")
    parser.add_argument('--modo', choices=('todo', 'emociones', 'mirada'), default='todo',
                        help='todo: emociones y mirada simultaneas (predeterminado)')
    args, restantes = parser.parse_known_args(argv)
    # Mantener la instruccion anterior para probar solo el detector facial.
    modo = 'emociones' if '--solo-mediapipe' in restantes else args.modo
    try:
        if modo == 'emociones':
            from emociones.aplicacion import main as ejecutar
            return ejecutar(restantes)
        from mirada.probar import main as ejecutar
        if modo == 'mirada':
            return ejecutar(restantes)
        from emociones.sesion import SesionEmociones
        # El modulo de mirada posee la unica VideoCapture y comparte cada frame.
        return ejecutar(restantes, fabrica_emociones=SesionEmociones)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        print(f"No se pudo iniciar: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
