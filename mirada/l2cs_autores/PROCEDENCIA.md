# Adaptación L2CS-Net

Autores: Ahmed Abdelrahman y colaboradores. Repositorio: https://github.com/Ahmednull/L2CS-Net

Revisión de referencia: `a4d8f7fa5436a2b2b9f088471623b552a85811bd`.

Se consultaron `l2cs/model.py`, `l2cs/pipeline.py`, `l2cs/utils.py` y `train.py` de la rama main para implementar `mirada/l2cs.py`. Se conserva la licencia MIT de los autores. La red se construye sobre ResNet50 de torchvision, con dos cabezas de 90 clases y la capa vestigial del checkpoint; no descarga pesos ImageNet.

Se reproduce el preprocesamiento de la demo: BGR a RGB, OpenCV 224x224, PIL Resize(448), tensor e ImageNet Normalize. Se conserva el orden de las cabezas (fc_yaw_gaze, fc_pitch_gaze). El código original usa nombres pitch/yaw inconsistentes entre arquitectura, entrenamiento y visualización; aquí se registran como salida 0 y salida 1 en radianes, sin inferir un punto físico de pantalla.

Diferencias: se reutiliza MediaPipe para recortar el rostro en vez de RetinaFace, con margen del 10%; se deshace el espejo del recorte antes de inferir. Es una adaptación que necesita validación con la cámara real. La calibración personal aprende su relación con la pantalla; no se aplica una conversión angular fija ni se incorpora geometría física de la instalación.

Los pesos proceden de una copia pública fijada a una revisión de Hugging Face; su origen y hash están en `../pesos/procedencia.json`. El hash verifica esta copia, no acredita identidad con los pesos originales cuyo enlace no estaba disponible. No se utiliza pickle sin restricciones.

Verificación local: ambas arquitecturas cargaron el mismo checkpoint de forma estricta y produjeron logits idénticos (diferencia máxima 0 en ambas cabezas) para la misma entrada sintética RGB preprocesada. Esto comprueba equivalencia de implementación en esa prueba, no precisión real ni equivalencia del detector facial adaptado con RetinaFace.
