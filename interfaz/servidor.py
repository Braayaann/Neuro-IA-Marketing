"""HTTP exclusivamente en loopback. Sin CORS, depurador ni acceso al backend principal."""
import secrets
from pathlib import Path
import threading
import webbrowser

from flask import Flask, Response, jsonify, request
from werkzeug.serving import make_server, WSGIRequestHandler
from interfaz.servicio_web import Servicio


def crear_app(servicio, token=None):
    web = Path(__file__).resolve().parent/'web'
    app = Flask(__name__, static_folder=str(web), static_url_path='/static')
    app.config['MAX_CONTENT_LENGTH'] = 1024*1024
    token = token or secrets.token_urlsafe(32)

    @app.before_request
    def local():
        if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
            return jsonify(error='Solo localhost'), 403
        if request.path.startswith('/api/') and request.headers.get('X-Session-Token') != token:
            return jsonify(error='Abre la página local del servidor'), 403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://images.unsplash.com; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.get('/')
    def index():
        return Response((web/'heatmap.html').read_text(encoding='utf-8').replace('__TOKEN__', token), mimetype='text/html')

    @app.post('/api/<accion>')
    def api(accion):
        datos = request.get_json()
        try:
            with servicio.lock:
                servicio.latido(datos)
                if accion == 'comando':
                    servicio.comando(datos['accion'], datos)
                elif accion == 'objetivo':
                    servicio.confirmar_objetivo(datos)
                elif accion == 'mouse':
                    servicio.mouse(datos)
                elif accion == 'dibujo':
                    servicio.confirmar_dibujo(datos)
                elif accion != 'estado':
                    return jsonify(error='Ruta desconocida'), 404
                return jsonify(servicio.snapshot())
        except (ValueError, KeyError, TypeError) as exc:
            return jsonify(error=str(exc)), 400

    @app.get('/api/mapa.png')
    def mapa():
        with servicio.lock:
            if servicio.geometria is None:
                return Response(status=204)
            modo = request.args.get('modo', servicio.modo)
            if modo not in servicio.mapas:
                return Response(status=400)
            mapa = servicio.mapas[modo]
            if modo == 'ocular':
                modelo = request.args.get('modelo', servicio.seleccion)
                if modelo not in servicio.mapas_por_modelo:
                    return Response(status=400)
                mapa = servicio.mapas_por_modelo[modelo]
            return Response(mapa.png(servicio.geometria), mimetype='image/png')

    return app


def ejecutar(modelo, resultados, camara=0, puerto=8765, abrir=True):
    servicio = Servicio(modelo, resultados)
    app = crear_app(servicio)
    # El servidor no abre una cámara hasta que el usuario pulsa el control HTML.
    class RegistroBreve(WSGIRequestHandler):
        def log_request(self, code='-', size='-'):
            if str(code).startswith(('4', '5')):
                super().log_request(code, size)
    servidor = make_server('127.0.0.1', puerto, app, threaded=True, request_handler=RegistroBreve)
    url = f'http://127.0.0.1:{puerto}/?camara={camara}'
    print(f'Interfaz local: {url}\nCierra el servidor con Ctrl+C. No abras el HTML con doble clic.', flush=True)
    servicio.iniciar_hilo()
    if abrir:
        threading.Timer(.7, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        servicio.cerrar()
