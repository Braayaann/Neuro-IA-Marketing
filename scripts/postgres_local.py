"""PostgreSQL real portable para Windows, limitado a 127.0.0.1:55432.

Instala binarios bajo .tools y datos/credenciales locales bajo .local (ignorados).
No requiere permisos de administrador ni modifica servicios de Windows.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / '.tools' / 'postgres'
DATA = ROOT / '.local' / 'postgres'
VERSION = '17.6.0-beta.15'


def binary(name):
    paths = list(TOOLS.rglob(name+'.exe')) if TOOLS.exists() else []
    if not paths:
        raise RuntimeError('Ejecuta primero: python scripts/postgres_local.py install')
    return paths[0]


def run(*args, **kw):
    return subprocess.run([str(a) for a in args], check=True, **kw)


def install():
    if TOOLS.exists() and list(TOOLS.rglob('pg_ctl.exe')):
        print('PostgreSQL portable ya está instalado.')
        return
    if sys.platform != 'win32':
        raise RuntimeError('Este instalador portable es para Windows. En Linux/WSL usa Docker o PostgreSQL del sistema.')
    meta = json.load(urllib.request.urlopen('https://registry.npmjs.org/@embedded-postgres/windows-x64/'+VERSION))
    TOOLS.mkdir(parents=True, exist_ok=True)
    archive = TOOLS / 'package.tgz'
    print('Descargando PostgreSQL portable…')
    urllib.request.urlretrieve(meta['dist']['tarball'], archive)
    # Verifica la integridad publicada en el registro npm antes de extraer.
    import hashlib, base64
    algorithm, expected = meta['dist']['integrity'].split('-', 1)
    actual = base64.b64encode(hashlib.new(algorithm, archive.read_bytes()).digest()).decode()
    if actual != expected:
        raise RuntimeError('Integridad de PostgreSQL incorrecta.')
    with tarfile.open(archive) as source:
        source.extractall(TOOLS, filter='data')
    print('Binarios instalados:', binary('pg_ctl').parent)


def settings():
    path = ROOT / '.local' / 'postgres-settings.json'
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({'password': secrets.token_hex(24)}), encoding='utf-8')
    return json.loads(path.read_text(encoding='utf-8'))


def start():
    import psycopg
    cfg = settings()
    pw = ROOT / '.local' / 'pg-password'
    if not (DATA / 'PG_VERSION').exists():
        pw.write_text(cfg['password'], encoding='ascii')
        try:
            run(binary('initdb'), '-D', DATA, '-U', 'neuro', '--pwfile='+str(pw),
                '--auth-host=scram-sha-256', '--auth-local=scram-sha-256', '--encoding=UTF8', '--locale=C')
        finally:
            pw.unlink(missing_ok=True)
    status = subprocess.run([str(binary('pg_ctl')), '-D', str(DATA), 'status'], capture_output=True, timeout=10)
    if status.returncode:
        run(binary('pg_ctl'), '-D', DATA, '-l', ROOT/'.local/postgres.log',
            '-o', '-h 127.0.0.1 -p 55432', '-w', '-t', '20', 'start',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with psycopg.connect(host='127.0.0.1', port=55432, user='neuro', password=cfg['password'],
                         dbname='postgres', autocommit=True, connect_timeout=5) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = 'neuroia'").fetchone():
            conn.execute('CREATE DATABASE neuroia')
    env = ROOT / '.env'
    url = f"postgresql+psycopg://neuro:{cfg['password']}@127.0.0.1:55432/neuroia"
    if not env.exists():
        env.write_text(f'DATABASE_URL={url}\nAPP_ENV=development\nVISION_ENABLED=1\n', encoding='utf-8')
    print('PostgreSQL listo en 127.0.0.1:55432. Credenciales guardadas en .env y .local (fuera de Git).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'start', 'stop', 'status'])
    args = parser.parse_args()
    if args.command == 'install':
        install()
    elif args.command == 'start':
        start()
    else:
        run(binary('pg_ctl'), '-D', DATA, args.command)
