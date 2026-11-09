"""Crea acceso inicial local; no agrega sesiones, muestras ni resultados ficticios."""
import json
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app
from backend.models import db, User
from sqlalchemy import select
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    email = 'admin@neuroia.local'
    if not db.session.scalar(select(User).where(User.email == email)):
        password = secrets.token_urlsafe(12)
        db.session.add(User(name='Brayan García', email=email, role='admin', password_hash=generate_password_hash(password)))
        db.session.commit()
        path = ROOT / '.local' / 'acceso-inicial.txt'
        path.write_text(f'Acceso LOCAL inicial\nURL: http://localhost:5000\nCorreo: {email}\nContraseña: {password}\n\nCambia la contraseña desde Cuentas. No subir este archivo a Git.\n', encoding='utf-8')
        print('Acceso inicial creado. Consulta .local/acceso-inicial.txt')
    else:
        print('La cuenta inicial ya existe. No se ha cambiado su contraseña.')
