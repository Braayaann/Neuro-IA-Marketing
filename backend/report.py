"""Reporte imprimible de una sesión a partir del mismo resumen que usa Resultados."""

import io
import math
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph


WIDTH, HEIGHT = A4
MARGIN = 48
CONTENT = WIDTH - 2 * MARGIN
INK = '#20392f'
MUTED = '#52665b'
GREEN = '#377450'
PALE = '#e9f0eb'


def number(value):
    return f'{value:.2f}'.rstrip('0').rstrip('.').replace('.', ',')


def paragraph(pdf, text, top, size=11, bold=False, color=INK, x=MARGIN, width=CONTENT):
    style = ParagraphStyle('report', fontName='Helvetica-Bold' if bold else 'Helvetica',
                           fontSize=size, leading=size * 1.25, textColor=HexColor(color))
    block = Paragraph(escape(str(text)), style)
    _, height = block.wrap(width, HEIGHT)
    block.drawOn(pdf, x, top - height)
    return top - height


def page_header(pdf, section, page, total):
    paragraph(pdf, 'NEURO IA MARKETING', HEIGHT - 34, 10, True, GREEN)
    pdf.setFillColor(MUTED)
    pdf.setFont('Helvetica', 9)
    pdf.drawRightString(WIDTH - MARGIN, HEIGHT - 44, section)
    pdf.setStrokeColor(PALE)
    pdf.line(MARGIN, HEIGHT - 56, WIDTH - MARGIN, HEIGHT - 56)
    pdf.line(MARGIN, 43, WIDTH - MARGIN, 43)
    pdf.drawString(MARGIN, 28, 'Reporte de sesión')
    pdf.drawRightString(WIDTH - MARGIN, 28, f'{page} / {total}')


def summary(pdf, data):
    study, ads = data['study'], data['ads']
    y = paragraph(pdf, study['name'], HEIGHT - 79, 24, True)
    date = datetime.fromisoformat(study['created_at']).astimezone().strftime('%d/%m/%Y')
    y = paragraph(pdf, f'Sesión {study["id"]}   ·   {date}', y - 7, color=MUTED)
    y = paragraph(pdf, f'{data["valid_samples"]} de {data["total_samples"]} muestras válidas',
                  y - 25, 16, True)
    y = paragraph(pdf, 'Cada muestra válida indica que la mirada pudo asignarse a un anuncio.',
                  y - 6, color=MUTED)
    y = paragraph(pdf, 'Tiempo estimado de mirada por anuncio', y - 30, 15, True) - 14
    maximum = max((ad['seconds'] for ad in ads), default=0)
    for ad in ads:
        label = f'{number(ad["seconds"])} s' if ad['samples'] else 'Sin muestras válidas'
        bottom = paragraph(pdf, f'{ad["position"] + 1}.  {ad["title"]}', y, bold=True, width=CONTENT - 135)
        pdf.setFillColor(INK)
        pdf.setFont('Helvetica', 11)
        pdf.drawRightString(WIDTH - MARGIN, y - 11, label)
        pdf.setFillColor(PALE)
        pdf.rect(MARGIN, bottom - 15, CONTENT, 8, stroke=0, fill=1)
        if ad['seconds'] > 0:
            pdf.setFillColor(GREEN)
            pdf.rect(MARGIN, bottom - 15, CONTENT * ad['seconds'] / maximum, 8, stroke=0, fill=1)
        y = bottom - 30
    if maximum and sum(bool(ad['samples']) for ad in ads) > 1:
        # Los números identifican los mismos anuncios que las páginas individuales.
        leaders = [str(ad['position'] + 1) for ad in ads if ad['seconds'] == maximum]
        if len(leaders) == 1:
            title = next(ad['title'] for ad in ads if ad['seconds'] == maximum)
            message = f'{title} reunió el mayor tiempo estimado de mirada ({number(maximum)} s).'
        else:
            message = f'Empate entre los anuncios {", ".join(leaders)}, con {number(maximum)} s cada uno.'
        y = paragraph(pdf, message, y - 4, 12, True, GREEN)
    elif data['valid_samples'] and not maximum:
        y = paragraph(pdf, 'Hubo muestras válidas con 0 segundos estimados.', y - 4)
    y = paragraph(pdf, 'El tiempo de mirada se estima entre muestras válidas consecutivas del mismo '
              'anuncio, separadas por hasta 1,5 segundos. Una muestra aislada aporta 0 segundos.',
              y - 19, color=MUTED)
    if ads and y > 160:
        y = paragraph(pdf, 'Distribución durante la exhibición', y - 18, bold=True) - 8
        cols = study['layout_columns']
        rows = math.ceil(len(study['slots']) / cols)
        for i in range(cols * rows):
            left, top = MARGIN + (i % cols) * 60, y - (i // cols) * 24
            pdf.setFillColor(PALE if i < len(ads) else '#eeeeee')
            pdf.rect(left, top - 21, 57, 21, fill=1, stroke=0)
            pdf.setFillColor(INK)
            pdf.setFont('Helvetica', 9)
            pdf.drawCentredString(left + 28, top - 14, f'Anuncio {i+1}' if i < len(ads) else 'Vacío')


def gaze_map(pdf, study, ad, uploads, top):
    columns = study['layout_columns']
    rows = math.ceil(len(study['slots']) / columns)
    aspect = ((study['screen_width'] or 1200) / columns) / ((study['screen_height'] or 800) / rows)
    w = min(CONTENT, 224 * aspect)
    h = w / aspect
    x, y = (WIDTH - w) / 2, top - h
    pdf.saveState()
    clip = pdf.beginPath()
    clip.rect(x, y, w, h)
    pdf.clipPath(clip, stroke=0)
    pdf.setFillColor('#000000' if ad['image_url'] else ad['color'])
    pdf.rect(x, y, w, h, stroke=0, fill=1)
    if ad['image_url']:
        image = uploads / Path(ad['image_url']).name
        if image.is_file():
            pdf.drawImage(ImageReader(str(image)), x, y, w, h, preserveAspectRatio=True, anchor='c')
        else:
            paragraph(pdf, 'Imagen no disponible', top - h / 4, 9, color='#ffffff', x=x+3, width=w-6)
    else:
        paragraph(pdf, ad['title'], top - h / 4, 10, True, x=x+3, width=max(1, w-6))
    for color, weight in [('#ffffff', 1.7), (INK, .6)]:
        pdf.setStrokeColor(color)
        pdf.setLineWidth(weight)
        pdf.line(x+w/2, y, x+w/2, top)
        pdf.line(x, y+h/2, x+w, y+h/2)
    for i in range(4):
        cx = x + (i % 2) * w/2 + 8
        cy = top - (i // 2) * h/2 - 8
        pdf.setFillColor('#ffffff')
        pdf.circle(cx, cy, 6, stroke=0, fill=1)
        pdf.setFont('Helvetica-Bold', 8)
        pdf.setFillColor(INK)
        pdf.drawCentredString(cx, cy-3, str(i+1))
    pdf.setFillColor('#151b18')
    pdf.setStrokeColor('#ffffff')
    pdf.setLineWidth(.65)
    for point in ad['points']:
        px = point['x'] * columns - ad['position'] % columns
        py = point['y'] * rows - ad['position'] // columns
        if 0 <= px <= 1 and 0 <= py <= 1:
            pdf.circle(x + px*w, top - py*h, 1.3, stroke=1, fill=1)
    pdf.restoreState()
    return y


def ad_page(pdf, study, ad, uploads):
    y = paragraph(pdf, ad['title'], HEIGHT - 75, 20, True)
    time = f'{number(ad["seconds"])} segundos estimados' if ad['samples'] else 'Sin muestras válidas'
    count = ad['samples']
    samples_label = '1 muestra válida' if count == 1 else f'{count} muestras válidas'
    y = paragraph(pdf, f'{time}   ·   {samples_label}', y - 5, color=MUTED)
    y = gaze_map(pdf, study, ad, uploads, y - 14)
    y = paragraph(pdf, 'Cada punto marca una muestra válida. Los números identifican los cuatro cuadrantes.',
                  y - 8, 9, color=MUTED)
    y = paragraph(pdf, 'Tiempo por cuadrante', y - 18, 15, True)
    for i, zone in enumerate(ad['quadrants'], 1):
        y = paragraph(pdf, f'{i}.  {zone["label"]}', y - 5)
        pdf.setFillColor(INK)
        pdf.setFont('Helvetica', 11)
        value = f'{number(zone["seconds"])} s' if ad['samples'] else 'Sin muestras válidas'
        pdf.drawRightString(WIDTH - MARGIN, y + 2, value)
    if ad['samples']:
        share = f' ({number(ad["quadrant_seconds"] / ad["seconds"] * 100)} %)' if ad['seconds'] else ''
        y = paragraph(pdf, f'Se atribuyeron {number(ad["quadrant_seconds"])} de '
                      f'{number(ad["seconds"])} segundos a cuadrantes{share}.', y - 10, bold=True)
    y = paragraph(pdf, 'Expresiones faciales detectadas', y - 19, 15, True)
    if not study['with_emotions']:
        paragraph(pdf, 'El análisis de expresiones estaba desactivado.', y - 6)
    elif not ad['emotions']:
        paragraph(pdf, 'Sin expresiones registradas para este anuncio.', y - 6)
    else:
        counts = sorted(ad['emotions'].items(), key=lambda item: -item[1])
        entries = [f'{"Alegría" if name == "Alegria" else name} ({count})' for name, count in counts]
        paragraph(pdf, 'Frecuencia en muestras: ' + ' · '.join(entries), y - 6)


def session_pdf(data, uploads):
    stream = io.BytesIO()
    pdf = Canvas(stream, pagesize=A4, pageCompression=1)
    pdf.setTitle('Reporte de sesión - ' + data['study']['name'])
    total = len(data['ads']) + 1
    page_header(pdf, 'Resumen de la sesión', 1, total)
    summary(pdf, data)
    pdf.showPage()
    for page, ad in enumerate(data['ads'], 2):
        page_header(pdf, f'Anuncio {ad["position"] + 1}', page, total)
        ad_page(pdf, data['study'], ad, uploads)
        pdf.showPage()
    pdf.save()
    stream.seek(0)
    return stream
