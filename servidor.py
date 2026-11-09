"""Sirve el portal React y la API Flask en el mismo origen."""
import os
from backend.app import create_app

app = create_app()

if __name__ == '__main__':
    from waitress import serve
    port = int(os.getenv('PORT', '5000'))
    print(f'Neuro IA Marketing: http://localhost:{port}', flush=True)
    serve(app, host=os.getenv('HOST', '127.0.0.1'), port=port, threads=4)
