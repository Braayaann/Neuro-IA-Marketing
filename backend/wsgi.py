"""Punto WSGI de PythonAnywhere. No inicia servidores ni abre cámaras al importar."""
from backend.app import create_app

application = create_app()
