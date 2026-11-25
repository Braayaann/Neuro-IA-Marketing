# Primera versión web · Neuro IA Marketing

React + Flask + PostgreSQL. Mantiene la prueba de escritorio `main.py` y reutiliza
`emociones/` y `mirada/calibracion.py`. El portal se inicia con `servidor.py`.

## Abrir en este computador

Las dependencias web, la compilación React y PostgreSQL portable ya están preparados.
Desde PowerShell, en la raíz del repositorio:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\iniciar_web.ps1
```

Mantén esa terminal abierta y entra en **http://localhost:5000**. El acceso inicial
está en **`.local/acceso-inicial.txt`**. La contraseña es aleatoria y solo local;
no aparece en el código ni en Git. Puedes cambiarla en Cuentas.

Si PowerShell bloquea scripts en esa terminal, ejecuta directamente:

```powershell
.\.venv\Scripts\python.exe scripts\postgres_local.py start
.\.venv\Scripts\python.exe servidor.py
```

Para detener el portal: Ctrl+C. Para detener PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts\postgres_local.py stop
```

No necesitas abrir `main.py` al mismo tiempo: puede ocupar la cámara. El portal
pide permiso de cámara al navegador. Usa localhost o HTTPS.

## Qué incluye

- Acceso con hash de contraseña, cookie HttpOnly, protección CSRF y caducidad.
- Administrador: creación, edición, roles y desactivación de cuentas. No puede
  desactivarse a sí mismo ni quitarse su rol.
- Cada usuario gestiona sus anuncios: texto, fondo, imagen JPG/PNG/WEBP y archivo
  reversible. Las imágenes se validan y recodifican; no se aceptan SVG ni HTML.
- Sesiones de 1 a 4 anuncios; dos en columnas, tres o cuatro en cuadrícula 2×2.
  Con tres, el cuarto cuadrante no suma muestras. El orden de selección fija las posiciones.
- Una persona por sesión; cámara seleccionable, vista previa, pantalla completa.
- Calibración de 9 objetivos con ambos iris (468 y 473 de FaceMesh), sus
  posiciones relativas a cada ojo y el ajuste lineal del prototipo.
  Se esperan 0,8 s y se recogen al menos diez
  muestras durante al menos dos segundos por objetivo. Si no hay suficientes
  muestras en catorce segundos, se solicita repetir. Se rechaza un ajuste
  degenerado. El portal web usa un ajuste por sesión y la señal binocular.
- Fotogramas JPEG efímeros de 640 px enviados al servidor local; el servidor
  refleja la imagen igual que `main.py`, detecta hasta dos rostros para rechazar
  escenas con más de una persona y clasifica recortes de al menos 60 px con RMN.
- La mirada se proyecta sobre el área de anuncios; **no mueve el cursor** y el
  mouse físico **no genera observaciones**.
- PostgreSQL conserva calibración, observaciones numéricas y expresión/confianza.
  No se almacenan fotogramas ni vídeo. Las imágenes subidas de anuncios sí se guardan.
- Resultados por sesión: mapa de densidad de muestras, segundos estimados por
  anuncio, expresiones, muestras rechazadas y CSV. Historial con instantáneas del
  contenido: editar un anuncio no modifica sesiones anteriores.
- Se valida propiedad en el backend. El administrador puede consultar todas las
  sesiones; únicamente su dueño puede calibrarlas, iniciarlas o cerrarlas.

## Probar una sesión real

1. Inicia sesión y crea dos anuncios. Puedes usar texto o imágenes.
2. Crea una sesión, selecciona los anuncios y decide si activar RMN.
3. Conecta la cámara. Colócala centrada arriba y sitúa una persona aproximadamente
   a un metro, con iluminación uniforme. No abras simultáneamente la aplicación de escritorio.
4. Calibra en pantalla completa siguiendo los nueve puntos sin mover la cabeza.
5. Inicia la exhibición manteniendo esa geometría y la misma persona.
6. Finaliza la sesión y revisa Resultados. El CSV contiene datos numéricos.

Cambiar de persona exige una sesión y calibración nuevas. Salir de pantalla
completa, ocultar la pestaña o desconectar la cámara interrumpe el análisis y
requiere cerrar o recalibrar. Si cierras el navegador sin finalizar, la sesión
queda abierta en el historial: al reabrirla, finalízala y crea una nueva.

### Cómo se estiman los segundos

Cada muestra se asigna a una región usando coordenadas normalizadas. Se suma el
intervalo entre dos muestras consecutivas válidas **del mismo anuncio** solo si
es mayor que cero y no supera 1,5 s. La primera muestra, los cambios de anuncio,
la ausencia de rostro, varios rostros, ojo cerrado, estimaciones fuera del área,
pausas largas y zonas sin anuncio no añaden tiempo. El reloj de captura usa
`performance.now()` y el servidor comprueba orden, duplicados y tiempo real.

Este cálculo es conservador y aproximado: no es fijación ocular validada. El mapa
representa cantidad de muestras, no segundos por píxel. No se debe interpretar
como preferencia demostrada o emoción interna. Las expresiones se muestran como
salida argmax de RMN; no se han inventado umbrales de confianza ni precisión propia.

## Preparar otro computador Windows

Requiere Python 3.12 de 64 bits y Node.js LTS (22.12+). En la raíz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m emociones.recuperar_pesos
.\preparar_web.ps1
.\iniciar_web.ps1
```

`preparar_web.ps1` instala las dependencias web, descarga PostgreSQL portable
17.6 para Windows desde el paquete npm `@embedded-postgres/windows-x64`, verifica
su integridad, crea una contraseña aleatoria, aplica Alembic, crea el acceso
inicial y compila React. No registra servicios de Windows ni requiere administrador.
El binario, datos y credenciales quedan fuera de Git. Mantiene las licencias
incluidas en el paquete descargado. No se instala ningún modelo nuevo de mirada.

### PostgreSQL existente / Docker / WSL

También puedes usar tu propio PostgreSQL 17+. Define `DATABASE_URL` en `.env`,
por ejemplo `postgresql+psycopg://usuario:clave@localhost:5432/neuroia`. Para Docker,
define primero `POSTGRES_PASSWORD` y una `DATABASE_URL` con la misma clave:

```powershell
docker compose up -d db
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m flask --app backend.app:create_app create-admin
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe servidor.py
```

En Linux/WSL usa `python` desde el entorno virtual y PostgreSQL del sistema o
Docker. El instalador portable incluido es específico para Windows.

## Desarrollo y pruebas

```powershell
# API + frontend compilado, puerto 5000
.\.venv\Scripts\python.exe servidor.py
# Frontend con recarga, en una segunda terminal (proxy /api -> puerto 5000)
cd frontend
npm run dev
```

Pruebas, con PostgreSQL iniciado:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m alembic check
```

Desde `frontend`, `npm test` ejecuta cuatro pruebas de formularios y navegación
con DOM simulado; `npm run build` genera la versión que sirve Flask. No sustituyen
una revisión visual en navegador ni la prueba de calibración con una persona real.

Las seis pruebas utilizan bases PostgreSQL efímeras `neuroia_test_<uuid>` y las
eliminan al terminar. Necesitan un usuario con permiso `CREATEDB`; no pruebes con
un usuario de producción. Puedes definir `TEST_DATABASE_URL` independiente. Las
pruebas simulan **la salida de visión** para comprobar la lógica de la API, la
calibración y los intervalos; no miden precisión facial ni de mirada.

La base principal queda sin anuncios, sesiones ni resultados ficticios. El único
registro de preparación es la cuenta administradora local. El script de acceso
no cambia una contraseña existente cuando se vuelve a ejecutar.

## Base de datos

Migración versionada: `backend/migrations/versions/001_schema.sql` y Alembic.
No se crean tablas silenciosamente al abrir el servidor. La cuenta de base de
datos del instalador portable es solo para desarrollo local.

```mermaid
erDiagram
    users ||--o{ ads : posee
    users ||--o{ studies : organiza
    studies ||--|{ study_ads : incluye
    ads ||--o{ study_ads : referencia
    studies ||--o| calibrations : calibra
    studies ||--o{ observations : registra
    study_ads ||--o{ observations : recibe
```

Las métricas se calculan a partir de observaciones; no se mantienen contadores
duplicados que puedan quedar desincronizados. Las secuencias por sesión son
únicas y el registro usa bloqueo de fila para impedir duplicados concurrentes.

## PythonAnywhere

Se incluye `backend/wsgi.py` compatible con WSGI. React se compila previamente
y Flask sirve `frontend/dist` desde el mismo dominio; no necesita un servidor Node
en producción. Requiere un plan que permita PostgreSQL propio o externo.

1. Configura un entorno Python compatible, instala dependencias web y de visión
   y copia los pesos fuera de Git. La versión de MediaPipe usada requiere Python 3.12.
2. Configura `DATABASE_URL`, una `SECRET_KEY` aleatoria estable y
   `APP_ENV=production` en `.env` protegido. `VISION_ENABLED=1` solo si el servidor
   puede cargar MediaPipe y RMN. No incluyas `.local/` ni el servidor PostgreSQL portable.
3. Aplica `python -m alembic upgrade head` y crea la cuenta con el comando Flask
   `create-admin`, que solicita la contraseña sin guardarla en texto plano.
4. En el WSGI de PythonAnywhere, añade la ruta del repositorio a `sys.path` e importa
   `from backend.wsgi import application`. Nunca ejecutes `app.run()` allí.
5. Usa HTTPS y verifica límite de CPU, memoria, tamaño de pesos e inferencia con
   fotogramas reales antes de comprometer latencia o FPS. La carga de RMN puede
   consumir mucha memoria por worker; empieza con uno y valida recursos.

La cámara pertenece al navegador del visitante, no a PythonAnywhere. En local,
los JPEG se envían únicamente al servidor local; al desplegar, se enviarían al
servidor remoto por HTTPS para procesarlos. Esta modalidad y sus condiciones se
deben acordar con el cliente antes de usarla con público. Esta entrega **no está
desplegada** ni afirma compatibilidad de recursos comprobada en PythonAnywhere.

El límite básico de intentos de acceso es por IP y proceso; para producción con
múltiples workers debe sustituirse por un almacén compartido / limitador del proxy.
La página limita una exhibición a cuatro horas; no incluye recuperación de contraseña,
envío de correo, múltiples espectadores, validación clínica de expresiones ni
seguimiento sin calibración. Requiere copia de seguridad de PostgreSQL y de las
imágenes de anuncios para conservar un historial completo.

Referencias: [Flask](https://flask.palletsprojects.com/),
[PostgreSQL en PythonAnywhere](https://help.pythonanywhere.com/pages/Postgres),
[Flask en PythonAnywhere](https://help.pythonanywhere.com/pages/Flask),
[RMN](https://github.com/phamquiluan/ResidualMaskingNetwork).
