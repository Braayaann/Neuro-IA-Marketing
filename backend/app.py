import csv
import io
import json
import math
import os
import re
import secrets
import threading
import time
from collections import Counter
from functools import wraps
from pathlib import Path
from uuid import uuid4

import click
from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, request, send_file, send_from_directory, session
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from .models import Ad, Calibration, Observation, Study, StudyAd, User, db, utcnow
from .vision import Vision

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    if os.getenv('APP_ENV') == 'production' and not os.getenv('DATABASE_URL'):
        raise RuntimeError('Configura DATABASE_URL en producción.')
    secret_file = ROOT / '.local' / 'secret-key'
    secret = os.getenv('SECRET_KEY')
    if not secret:
        if os.getenv('APP_ENV') == 'production':
            raise RuntimeError('Configura SECRET_KEY en producción.')
        secret_file.parent.mkdir(exist_ok=True)
        if not secret_file.exists():
            secret_file.write_text(secrets.token_hex(32), encoding='ascii')
        secret = secret_file.read_text(encoding='ascii')
    app.config.update(
        SECRET_KEY=secret,
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'postgresql+psycopg://neuro:neuro@127.0.0.1:55432/neuroia'),
        SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True, 'connect_args': {'connect_timeout': 5}},
        MAX_CONTENT_LENGTH=6*1024*1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('APP_ENV') == 'production',
        PERMANENT_SESSION_LIFETIME=28800,
        UPLOAD_DIR=str(ROOT / '.local' / 'uploads'),
        VISION_ENABLED=os.getenv('VISION_ENABLED', '1') == '1',
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    app.extensions['vision'] = Vision(Path(os.getenv('RUTA_RMN', ROOT/'emociones/pesos/resmasking_net.pth')))
    Path(app.config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    login_attempts = {}
    login_lock = threading.Lock()

    def problem(message, code=400):
        abort(code, description=message)

    def payload():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            problem('Se esperaba un objeto JSON.')
        return value

    def string(data, key, length, required=True):
        v = data.get(key, '')
        if not isinstance(v, str) or len(v.strip()) > length or (required and not v.strip()):
            problem(f'Campo inválido: {key}.')
        return v.strip()

    def integer(v, name, lo=0, hi=1000000000):
        if type(v) is not int or not lo <= v <= hi:
            problem(f'Valor inválido: {name}.')
        return v

    def allowed(study, write=False):
        if study is None:
            abort(404)
        if study.owner_id != g.user.id and (write or g.user.role != 'admin'):
            abort(403)
        return study

    def get_study(sid, lock=False, write=False):
        q = select(Study).where(Study.id == sid)
        if lock:
            q = q.with_for_update(of=Study)
        return allowed(db.session.scalar(q), write)

    def auth(fn):
        @wraps(fn)
        def wrapped(*a, **kw):
            if not g.user:
                abort(401)
            return fn(*a, **kw)
        return wrapped

    @app.before_request
    def before():
        if request.path.startswith('/api/'):
            g.user = db.session.get(User, session.get('uid')) if session.get('uid') else None
            if g.user and not g.user.active:
                session.clear()
                g.user = None
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                supplied = request.headers.get('X-CSRF-Token', '')
                if not session.get('csrf') or not secrets.compare_digest(supplied, session['csrf']):
                    problem('La sesión de seguridad expiró. Recarga la página.', 403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=()'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(error=error.description), error.code
        return error

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error='El registro ya existe o está relacionado con otros datos.'), 409

    @app.errorhandler(OperationalError)
    def database_error(error):
        db.session.rollback()
        app.logger.error('Conexión PostgreSQL no disponible.')
        return jsonify(error='PostgreSQL no está disponible. Inicia la base de datos.'), 503

    @app.get('/api/health')
    def health():
        db.session.execute(text('SELECT 1'))
        return jsonify(database='postgresql', ok=True)

    @app.get('/api/auth/me')
    def me():
        session.setdefault('csrf', secrets.token_urlsafe(32))
        return jsonify(user=g.user.public() if g.user else None, csrf=session['csrf'])

    @app.post('/api/auth/login')
    def login():
        data = payload()
        email = string(data, 'email', 254).lower()
        password = data.get('password')
        if not isinstance(password, str) or not 1 <= len(password) <= 256:
            problem('Contraseña inválida.')
        key = request.remote_addr or 'unknown'
        now = time.monotonic()
        with login_lock:
            attempts = [t for t in login_attempts.get(key, []) if now-t < 300]
            if len(attempts) >= 10:
                problem('Demasiados intentos. Espera cinco minutos antes de volver a ingresar.', 429)
            login_attempts[key] = attempts + [now]
        user = db.session.scalar(select(User).where(User.email == email))
        # Hash ficticio para reducir diferencias evidentes entre cuentas existentes e inexistentes.
        hashed = user.password_hash if user else 'scrypt:32768:8:1$none$' + '0'*128
        if not check_password_hash(hashed, password) or not user or not user.active:
            problem('Correo o contraseña incorrectos.', 401)
        with login_lock:
            login_attempts.pop(key, None)
        session.clear()
        session.update(uid=user.id, csrf=secrets.token_urlsafe(32))
        session.permanent = True
        return jsonify(user=user.public(), csrf=session['csrf'])

    @app.post('/api/auth/logout')
    @auth
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get('/api/users')
    @auth
    def users():
        if g.user.role != 'admin':
            abort(403)
        return jsonify([u.public() for u in db.session.scalars(select(User).order_by(User.id))])

    @app.route('/api/users', methods=['POST'])
    @app.route('/api/users/<int:uid>', methods=['PATCH'])
    @auth
    def save_user(uid=None):
        if g.user.role != 'admin':
            abort(403)
        data = payload()
        u = db.get_or_404(User, uid) if uid else User()
        name = string(data, 'name', 100)
        email = string(data, 'email', 254).lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            problem('Correo inválido.')
        role = data.get('role', 'owner')
        active = data.get('active', True)
        if role not in ('admin', 'owner') or type(active) is not bool:
            problem('Rol o estado inválido.')
        # Administrador no puede quitarse su propio acceso.
        if uid == g.user.id and (not active or role != 'admin'):
            problem('No puedes desactivar tu propia cuenta ni quitarte el rol administrador.')
        password = data.get('password', '')
        if not isinstance(password, str) or (password and not 10 <= len(password) <= 256):
            problem('Usa una contraseña de 10 a 256 caracteres.')
        if not uid and not password:
            problem('La contraseña inicial es obligatoria.')
        if password:
            u.password_hash = generate_password_hash(password)
        u.name, u.email, u.role, u.active = name, email, role, active
        db.session.add(u)
        db.session.commit()
        return jsonify(u.public()), 200 if uid else 201

    @app.get('/api/ads')
    @auth
    def ads():
        return jsonify([a.public() for a in db.session.scalars(
            select(Ad).where(Ad.owner_id == g.user.id).order_by(Ad.created_at.desc()))])

    @app.route('/api/ads', methods=['POST'])
    @app.route('/api/ads/<int:aid>', methods=['PATCH'])
    @auth
    def save_ad(aid=None):
        data = payload()
        ad = db.get_or_404(Ad, aid) if aid else Ad(owner_id=g.user.id)
        if ad.owner_id != g.user.id:
            abort(403)
        ad.title = string(data, 'title', 140)
        ad.description = string(data, 'description', 500, False)
        color = data.get('color', '#c7f36b')
        active = data.get('active', True)
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color) or type(active) is not bool:
            problem('Color o estado inválido.')
        ad.color, ad.active = color, active
        db.session.add(ad)
        db.session.commit()
        return jsonify(ad.public()), 200 if aid else 201

    @app.post('/api/ads/<int:aid>/image')
    @auth
    def upload(aid):
        ad = db.get_or_404(Ad, aid)
        if ad.owner_id != g.user.id:
            abort(403)
        f = request.files.get('image')
        if not f:
            problem('Selecciona una imagen.')
        try:
            with Image.open(f.stream) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width*image.height > 20000000:
                    problem('Usa JPG, PNG o WEBP de hasta 20 megapíxeles.')
                image = image.convert('RGB')
                image.thumbnail((1920, 1920))
                filename = uuid4().hex + '.jpg'
                image.save(Path(app.config['UPLOAD_DIR']) / filename, 'JPEG', quality=90)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            problem('Archivo de imagen inválido.')
        ad.image = filename
        db.session.commit()
        return jsonify(ad.public())

    @app.get('/api/media/<filename>')
    @auth
    def media(filename):
        if not re.fullmatch(r'[a-f0-9]{32}\.jpg', filename):
            abort(404)
        owned = db.session.scalar(select(Ad.id).where(Ad.image == filename, Ad.owner_id == g.user.id))
        history = db.session.scalar(select(StudyAd.id).join(Study).where(StudyAd.image == filename, Study.owner_id == g.user.id))
        if g.user.role != 'admin' and not (owned or history):
            abort(403)
        return send_from_directory(app.config['UPLOAD_DIR'], filename)

    @app.get('/api/studies')
    @auth
    def studies():
        q = select(Study).order_by(Study.created_at.desc())
        if g.user.role != 'admin':
            q = q.where(Study.owner_id == g.user.id)
        return jsonify([s.public() for s in db.session.scalars(q).unique()])

    @app.post('/api/studies')
    @auth
    def create_study():
        data = payload()
        ids = data.get('ad_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 4 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
            problem('Selecciona de uno a cuatro anuncios diferentes.')
        selected = list(db.session.scalars(select(Ad).where(Ad.id.in_(ids), Ad.owner_id == g.user.id, Ad.active.is_(True))))
        if len(selected) != len(ids):
            problem('Uno de los anuncios no está disponible.', 403)
        emotions = data.get('with_emotions', True)
        if type(emotions) is not bool:
            problem('Modo de expresiones inválido.')
        s = Study(owner_id=g.user.id, name=string(data, 'name', 140), with_emotions=emotions)
        db.session.add(s)
        db.session.flush()
        for position, aid in enumerate(ids):
            a = next(a for a in selected if a.id == aid)
            db.session.add(StudyAd(study_id=s.id, ad_id=a.id, position=position, title=a.title,
                                   description=a.description, color=a.color, image=a.image))
        db.session.commit()
        return jsonify(s.public()), 201

    @app.get('/api/studies/<int:sid>')
    @auth
    def study(sid):
        return jsonify(get_study(sid).public())

    @app.get('/api/vision/status')
    @auth
    def vision_status():
        import importlib.util
        return jsonify(enabled=app.config['VISION_ENABLED'],
                       mediapipe=bool(importlib.util.find_spec('mediapipe')),
                       torch=bool(importlib.util.find_spec('torch')),
                       weights=app.extensions['vision'].weights.is_file())

    @app.post('/api/studies/<int:sid>/calibration/start')
    @auth
    def calibration_start(sid):
        s = get_study(sid, lock=True, write=True)
        if s.status not in ('draft', 'ready', 'calibrating'):
            problem('Esta sesión ya comenzó o finalizó.', 409)
        data = payload()
        s.screen_width = integer(data.get('width'), 'ancho', 320, 10000)
        s.screen_height = integer(data.get('height'), 'alto', 240, 10000)
        s.camera_id = string(data, 'camera_id', 300, False)
        c = s.calibration
        if c is None:
            c = Calibration(study_id=s.id)
            db.session.add(c)
        c.samples, c.coefficients, c.mean, c.scale, c.completed_at = {}, None, None, None, None
        s.status = 'calibrating'
        db.session.commit()
        return jsonify(ok=True)

    def analyze_frame(s, emotions=False):
        if not app.config['VISION_ENABLED']:
            problem('La captura está deshabilitada en este servidor.', 503)
        f = request.files.get('frame')
        if not f:
            problem('Falta el fotograma de cámara.')
        raw = f.read(600001)
        if len(raw) > 600000:
            problem('Fotograma demasiado grande.', 413)
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.format != 'JPEG' or max(im.size) > 1280:
                    problem('Se esperaba un fotograma JPEG de hasta 1280 píxeles.')
                im.verify()
            return app.extensions['vision'].analyze(raw, emotions)
        except (ImportError, FileNotFoundError, RuntimeError) as e:
            app.logger.warning('Visión no disponible: %s', type(e).__name__)
            problem('No se pudo cargar MediaPipe o RMN. Revisa dependencias y pesos en el servidor.', 503)
        except (ValueError, OSError, UnidentifiedImageError):
            problem('No se pudo analizar el fotograma.')

    @app.post('/api/studies/<int:sid>/calibration/sample')
    @auth
    def calibration_sample(sid):
        s = get_study(sid, lock=True, write=True)
        if s.status != 'calibrating' or not s.calibration:
            problem('Inicia primero la calibración.', 409)
        try:
            target = int(request.form.get('target', '-1'))
        except ValueError:
            problem('Punto inválido.')
        integer(target, 'punto', 0, 8)
        result = analyze_frame(s)
        c = s.calibration
        samples = dict(c.samples)
        current = list(samples.get(str(target), []))
        if result['iris'] is not None and len(current) < 80:
            current.append(result['iris'])
        samples[str(target)] = current
        c.samples = samples
        db.session.commit()
        return jsonify(count=len(current), reason=result['reason'])

    @app.post('/api/studies/<int:sid>/calibration/finish')
    @auth
    def calibration_finish(sid):
        import numpy as np
        from mirada.calibracion import Calibracion
        s = get_study(sid, lock=True, write=True)
        c = s.calibration
        if s.status != 'calibrating' or not c:
            problem('Inicia primero la calibración.', 409)
        if any(len(c.samples.get(str(i), [])) < 10 for i in range(9)):
            problem('Faltan muestras: se necesitan al menos diez por punto.')
        try:
            fit = Calibracion(metodo='lineal').ajustar(
                [np.median(c.samples[str(i)], axis=0) for i in range(9)])
        except ValueError as e:
            problem(str(e))
        c.mean, c.scale, c.coefficients = fit.media.tolist(), fit.escala.tolist(), fit.coeficientes.tolist()
        c.completed_at = utcnow()
        s.status = 'ready'
        db.session.commit()
        return jsonify(s.public())

    @app.post('/api/studies/<int:sid>/start')
    @auth
    def start(sid):
        s = get_study(sid, lock=True, write=True)
        if s.status != 'ready' or not s.calibration or not s.calibration.coefficients:
            problem('Completa la calibración antes de comenzar.', 409)
        s.status, s.started_at = 'running', utcnow()
        db.session.commit()
        return jsonify(s.public())

    @app.post('/api/studies/<int:sid>/observations')
    @auth
    def observe(sid):
        import numpy as np
        s = get_study(sid, lock=True, write=True)
        if s.status != 'running':
            problem('La sesión no está en curso.', 409)
        try:
            seq = int(request.form.get('seq', '-1'))
            elapsed = float(request.form.get('elapsed', 'nan'))
        except ValueError:
            problem('Secuencia o tiempo inválidos.')
        integer(seq, 'secuencia')
        if not math.isfinite(elapsed) or not 0 <= elapsed <= 14400:
            problem('Tiempo de sesión inválido. Máximo cuatro horas.')
        if seq <= s.last_seq or (s.last_elapsed is not None and elapsed <= s.last_elapsed):
            problem('La muestra ya fue procesada o está fuera de orden.', 409)
        # El tiempo declarado por el navegador tampoco puede superar el tiempo real de sesión.
        if elapsed > (utcnow() - s.started_at).total_seconds() + 3:
            problem('El tiempo no coincide con el inicio de la sesión.')
        result = analyze_frame(s, s.with_emotions)
        x = y = None
        slot = None
        reason = result['reason']
        if result['iris'] is not None:
            c = s.calibration
            xy = np.r_[1., (np.array(result['iris'])-c.mean)/c.scale] @ np.array(c.coefficients)
            if np.isfinite(xy).all() and ((xy >= 0) & (xy <= 1)).all():
                x, y = map(float, xy)
                n = len(s.slots)
                position = 0 if n == 1 else min(int(x*2), 1) if n == 2 else min(int(y*2), 1)*2+min(int(x*2), 1)
                # Con tres anuncios, el cuarto cuadrante queda fuera de contenido.
                slot = next((a for a in s.slots if a.position == position), None)
                if slot is None:
                    reason = 'sin_anuncio'
            else:
                reason = 'fuera_de_pantalla'
        valid = slot is not None
        dt = elapsed - s.last_elapsed if s.last_elapsed is not None else 0
        # Solo intervalos cortos, consecutivos y en el mismo anuncio; no cuenta pérdidas/pausas.
        dwell = dt if valid and slot.id == s.last_ad_id and 0 < dt <= 1.5 else 0
        ob = Observation(study_id=s.id, study_ad_id=slot.id if slot else None, seq=seq, elapsed=elapsed,
                         x=x, y=y, valid=valid, reason=reason, emotion=result['emotion'],
                         confidence=result['confidence'], estimated_seconds=dwell)
        db.session.add(ob)
        s.last_seq, s.last_elapsed, s.last_ad_id = seq, elapsed, slot.id if slot else None
        db.session.commit()
        return jsonify(x=x, y=y, valid=valid, reason=reason, ad_id=slot.id if slot else None,
                       emotion=ob.emotion, confidence=ob.confidence, estimated_seconds=dwell)

    @app.post('/api/studies/<int:sid>/stop')
    @auth
    def stop(sid):
        s = get_study(sid, lock=True, write=True)
        if s.status in ('completed', 'cancelled'):
            return jsonify(s.public())
        s.status = 'completed' if s.started_at else 'cancelled'
        s.ended_at = utcnow()
        db.session.commit()
        return jsonify(s.public())

    def result(s):
        observations = list(db.session.scalars(select(Observation).where(Observation.study_id == s.id).order_by(Observation.seq)))
        total = sum(o.estimated_seconds for o in observations)
        ads = []
        for a in s.slots:
            rows = [o for o in observations if o.study_ad_id == a.id]
            seconds = sum(o.estimated_seconds for o in rows)
            ads.append(dict(**a.public(), seconds=round(seconds, 2), samples=len(rows),
                            share=round(seconds/total*100, 1) if total else 0,
                            emotions=dict(Counter(o.emotion for o in rows if o.emotion))))
        valid = sum(o.valid for o in observations)
        return dict(study=s.public(), ads=ads, total_samples=len(observations), valid_samples=valid,
                    valid_ratio=round(valid/len(observations)*100, 1) if observations else 0,
                    estimated_seconds=round(total, 2),
                    emotions=dict(Counter(o.emotion for o in observations if o.emotion)),
                    rejected=dict(Counter(o.reason for o in observations if not o.valid)),
                    # Límite de puntos para visualización; totales calculados sobre todos los registros.
                    points=[dict(x=o.x, y=o.y) for o in observations if o.valid][::max(1, valid//2000)],
                    warning='Estimación de mirada calibrada. No demuestra preferencia, atención exacta ni emoción interna.')

    @app.get('/api/studies/<int:sid>/results')
    @auth
    def results(sid):
        return jsonify(result(get_study(sid)))

    @app.get('/api/studies/<int:sid>/export.csv')
    @auth
    def export(sid):
        s = get_study(sid)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['secuencia', 'segundos_desde_inicio', 'anuncio_id', 'x_normalizada', 'y_normalizada', 'valida', 'motivo', 'expresion', 'confianza', 'segundos_estimados'])
        for o in db.session.scalars(select(Observation).where(Observation.study_id == sid).order_by(Observation.seq)):
            writer.writerow([o.seq, o.elapsed, o.study_ad_id, o.x, o.y, o.valid, o.reason, o.emotion, o.confidence, o.estimated_seconds])
        return send_file(io.BytesIO(buffer.getvalue().encode('utf-8-sig')), mimetype='text/csv',
                         as_attachment=True, download_name=f'neuroia-sesion-{s.id}.csv')

    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt=True, default='Sergio')
    @click.password_option()
    def create_admin(email, name, password):
        if len(password) < 10:
            raise click.ClickException('La contraseña debe tener al menos diez caracteres.')
        if db.session.scalar(select(User).where(User.email == email.lower())):
            raise click.ClickException('La cuenta ya existe.')
        db.session.add(User(email=email.lower(), name=name, role='admin', password_hash=generate_password_hash(password)))
        db.session.commit()
        click.echo('Administrador creado.')

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path=''):
        if path.startswith('api/'):
            abort(404)
        dist = ROOT / 'frontend' / 'dist'
        if path and (dist/path).is_file() and (dist/path).resolve().is_relative_to(dist.resolve()):
            return send_from_directory(dist, path)
        if not (dist/'index.html').exists():
            return 'Compila primero el frontend: cd frontend && npm install && npm run build', 503
        return send_from_directory(dist, 'index.html')

    return app
