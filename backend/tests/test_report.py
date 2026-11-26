import io

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from backend.models import Observation, Study, db
from conftest import login


@pytest.mark.parametrize('samples', [True, False], ids=['con-muestras', 'sin-muestras'])
def test_session_pdf(app, client, tmp_path, samples):
    headers = login(client)
    ids = []
    titles = ['Colección mar', 'Colección bosque', 'Colección sol']
    for i, (name, color) in enumerate(zip(titles, ['#468caf', '#27644e', '#efa73e'])):
        picture = Image.new('RGB', (240 + i*120, 300), color)
        ImageDraw.Draw(picture).ellipse((28, 70, 170, 210), fill='#f7eed8')
        image = io.BytesIO()
        picture.save(image, 'PNG')
        image.seek(0)
        ad = client.post('/api/ads', headers=headers, data={'title': name, 'image': (image, 'foto.png')})
        ids.append(ad.json['id'])
    study = client.post('/api/studies', headers=headers, json={
        'name': 'Campaña de temporada', 'ad_ids': ids, 'with_emotions': samples}).json
    sid = study['id']
    with app.app_context():
        s = db.session.get(Study, sid)
        s.status = 'completed'
        s.screen_width, s.screen_height = 1200, 800
        s.layout_columns = 2 if samples else 3
        if samples:
            for seq, (idx, x, y, seconds) in enumerate([
                    (0, .31, .11, 0), (0, .33, .12, .75), (1, .7, .17, 0), (0, .31, .11, 0)]):
                db.session.add(Observation(study_id=sid, study_ad_id=s.slots[idx].id,
                                           seq=seq, elapsed=seq*.75, valid=True, x=x, y=y,
                                           emotion='Neutral' if seq == 3 else 'Alegria', estimated_seconds=seconds))
        db.session.commit()
    base = f'/api/studies/{sid}'
    result = client.get(base + '/results').json
    response = client.get(base + '/export.pdf')
    assert response.status_code == 200 and response.mimetype == 'application/pdf'
    assert 'attachment' in response.headers['Content-Disposition']
    file = tmp_path / 'reporte.pdf'
    file.write_bytes(response.data)
    pages = PdfReader(file).pages
    assert len(pages) == 4
    summary, *details = [page.extract_text() for page in pages]
    assert f"{result['valid_samples']} de {result['total_samples']} muestras válidas" in summary
    for index, (title, detail) in enumerate(zip(titles, details), 1):
        assert title in summary and title in detail and len(pages[index].images) == 1
    if samples:
        assert result['ads'][0]['quadrant_seconds'] == result['ads'][0]['seconds'] == .75
        assert 'Se atribuyeron 0,75 de 0,75 segundos' in details[0]
        chart = details[0].split('Número de muestras por expresión')[1].split()
        assert chart == ['Alegría', '2', 'Neutral', '1']
        assert '0 segundos estimados' in details[1] and 'Sin muestras válidas' in details[2]
        assert 'Colección mar reunió el mayor' in summary and 'Vacío' in summary
    else:
        assert all('Sin muestras válidas' in detail and 'desactivado' in detail for detail in details)
    other = app.test_client()
    login(other, 'other@test.cl')
    assert other.get(base + '/export.pdf').status_code == 403
