# Prueba A/B de mirada — experimental

Primera prueba para una persona a aproximadamente 1 metro, con webcam centrada arriba
del notebook NE160QDM-NZB (2560 × 1600). Este modulo es independiente de OpenCV + RMN:
no lo reemplaza ni modifica sus recortes. Cierra el programa de emociones antes de
abrir la misma camara con esta prueba.

## Ejecutar desde la raiz del repositorio

```powershell
.\.venv\Scripts\python.exe -m mirada.probar
```

Se abre una ventana a pantalla completa con dos anuncios de ejemplo. Puedes cargar
imagenes propias sin cambiar el codigo:

```powershell
.\.venv\Scripts\python.exe -m mirada.probar --anuncio-a "C:\ruta\A.jpg" --anuncio-b "C:\ruta\B.jpg"
```

- Q o Escape: salir y liberar camara.
- V: ver/ocultar la camara, sin grabar. No esta disponible durante la prueba guiada.
- T: prueba guiada de 32 segundos; mira la cruz blanca cuando cambie de anuncio.
  Durante esta prueba se ocultan el punto y la prediccion para no guiar las respuestas.
  Espera un segundo tras cada cambio antes de registrar muestras.

Al terminar imprime cuantas de las 8 pruebas coincidieron por mayoria, incluyendo las
indeterminadas y miradas fuera de pantalla. Un informe JSON en `mirada/resultados/`
incluye cobertura, recuentos por prueba y lecturas. No se guardan fotos ni video.
Las lecturas de video estan correlacionadas: no son espectadores independientes.
No se entrena ni se calibra el modelo con los resultados de cada persona.

## Interpretar la prueba

La etiqueta es una estimacion A, B, FUERA o INDETERMINADA. No es preferencia, agrado
ni una medicion validada de atencion. Aun no se generan porcentajes de audiencia
ni mapas de calor: primero hay que comprobar que las asignaciones sean fiables.

L2CS devuelve direccion de mirada. La conversion a pantalla utiliza la posicion
aproximada de los ojos, un modelo de camara y una distancia fija. `config.json` usa:

- Pantalla publicada de 34.4678 × 21.5424 cm; comprobar el area visible con una regla.
- Distancia estimada de 100 cm y camara a 0.5 cm sobre el area visible.
- FOV horizontal supuesto de 60 grados, NO medido. La camara se supone perpendicular
  al plano de pantalla, con pixeles cuadrados y sin distorsion.

Estas suposiciones pueden producir errores grandes. Mover la persona o inclinar la
pantalla cambia la geometria. La ubicacion de ojos con Haar tambien es aproximada.
No se usan solo el signo del angulo o la posicion de la cabeza para decidir A/B.
Las miradas fuera de pantalla no se fuerzan dentro de los anuncios; una banda central
se marca indeterminada. Si faltan ojos o hay varias personas, tampoco se asigna anuncio.

La prueba debe repetirse con personas diferentes, mirando objetivos conocidos y sin
ajustar parametros a cada participante. A un metro, el ancho de un notebook ocupa
pocos grados: el error del estimador puede ser demasiado grande incluso para A/B.
Si las asignaciones fallan o casi todas se descartan, no presentar un mapa de calor
como resultado valido. Primero medir/calibrar el montaje y reconsiderar su viabilidad.

## Instalar en otro equipo

Con Python 3.12 x64 y el entorno virtual creado:

```powershell
.\.venv\Scripts\python.exe -m pip install -r mirada\requirements.txt
.\.venv\Scripts\python.exe -m mirada.descargar
.\.venv\Scripts\python.exe -m unittest mirada.test_geometria -v
```

El codigo de arquitectura se obtiene del repositorio oficial fijado al commit
`a4d8f7fa5436a2b2b9f088471623b552a85811bd`, con licencia MIT. El enlace Drive oficial
de pesos devolvio 404: se utiliza una copia de terceros `tianfxc/l2cs`, fijada a commit
y SHA-256. Otro repositorio publico publica el mismo hash, pero esto no autentica los
pesos frente al autor. La procedencia queda en `pesos/procedencia.json` y la carga usa
`weights_only=True`. No se atribuye a esta adaptacion la precision del paper.

El preprocesamiento reproduce la demo: BGR a RGB, 224, PIL Resize 448, normalizacion
ImageNet. Se usa ResNet50, 90 bins y conversion de expectativas `bin*4 - 180`.
El localizador de cara/ojos es Haar en lugar de RetinaFace; eso puede afectar resultados.
Los pesos de 96 MB, resultados y entorno estan excluidos de Git.

Fuentes:
- Arquitectura y demo: https://github.com/Ahmednull/L2CS-Net
- Paper: https://arxiv.org/abs/2203.03339
- Copia de pesos: https://huggingface.co/tianfxc/l2cs
- Dimensiones del panel: https://academia.infosquad.com.ar/pantalla/ne160qdm-nzb/
