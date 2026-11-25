# PythonAnywhere con SQLite
La base predeterminada se guarda en .local/neuroia.sqlite.
Usa Python 3.12 y un virtualenv. Instala backend/requirements.txt y numpy.
Compila React con npm ci y npm run build en frontend o sube frontend/dist.
Configura el virtualenv en Web. En WSGI agrega el repositorio a sys.path
e importa application desde backend.wsgi. Configura SECRET_KEY y APP_ENV=production.
Inicializa con python -m flask --app servidor init-db.
Crea el administrador con python -m flask --app servidor create-admin.
Los pesos RMN quedan fuera de Git. Para analizar mirada debes instalar
MediaPipe y OpenCV compatibles. Las expresiones requieren PyTorch y sus pesos.
Respalda .local/neuroia.sqlite y los anuncios de .local/uploads.
SQLite permite una demo de baja concurrencia. DATABASE_URL permite mantener
PostgreSQL en instalaciones existentes. Sus datos requieren exportacion e
importacion si se desea trasladarlos a SQLite.
