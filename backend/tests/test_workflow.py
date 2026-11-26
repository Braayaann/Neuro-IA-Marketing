import io
import pytest
from datetime import timedelta
from PIL import Image
from sqlalchemy import select
from backend.models import Study, StudyAd, Calibration, Observation, User, db, utcnow
from conftest import login, make_study, FakeVision, calibrate, jpeg


@pytest.mark.parametrize('legacy', [False, True], ids=['fila-nueva', 'cuadricula-anterior'])
def test_three_ads_use_saved_layout_for_capture_and_results(app, client, legacy):
    headers = login(client)
    ids = [client.post('/api/ads', json={'title': title}, headers=headers).json['id']
           for title in ['A', 'B', 'C']]
    order = [ids[2], ids[0], ids[1]]
    study = client.post('/api/studies', json={'name': 'Tres', 'ad_ids': order}, headers=headers).json
    assert study['layout_columns'] == 3
    assert [slot['ad_id'] for slot in study['slots']] == order
    sid = study['id']
    if legacy:
        with app.app_context():
            db.session.get(Study, sid).layout_columns = 2
            db.session.commit()
    vision = FakeVision()
    app.extensions['vision'] = vision
    calibrate(client, headers, sid, vision)
    assert client.post(f'/api/studies/{sid}/start', headers=headers).status_code == 200
    for seq in range(2):
        vision.iris = [.9, .8]
        response = client.post(f'/api/studies/{sid}/observations', headers=headers, data={
            'seq': str(seq), 'elapsed': str(seq * .5), 'frame': (jpeg(), 'f.jpg')})
        assert response.status_code == 200
        assert response.json['ad_id'] == (None if legacy else study['slots'][2]['id'])
    result = client.get(f'/api/studies/{sid}/results').json
    assert result['study']['layout_columns'] == (2 if legacy else 3)
    assert result['ads'][2]['quadrants'][3]['seconds'] == (0 if legacy else .5)


def test_auth_csrf_and_roles(client):
    assert client.get('/api/ads').status_code==401
    assert client.post('/api/auth/login',json={}).status_code==403
    h=login(client)
    assert client.get('/api/users').status_code==403
    assert client.post('/api/users',json={},headers=h).status_code==403
    assert client.post('/api/ads',json={'title':'<script>texto</script>'},headers=h).status_code==201


def test_calibration_rejects_inconsistent_vertical_signal(app, client):
    from mirada.calibracion import OBJETIVOS
    headers = login(client)
    sid = make_study(client, headers)['id']
    path = f'/api/studies/{sid}/calibration'
    assert client.post(path+'/start', headers=headers,json={'width':1100,'height':540}).status_code == 200
    with app.app_context():
        db.session.get(Calibration,sid).samples = {
            str(i): [[x, .12 + .38*((i//3 + i%3) % 3)]] * 10 for i,(x,_) in enumerate(OBJETIVOS)}
        db.session.commit()
    assert client.post(path+'/finish', headers=headers).status_code == 400
    assert client.post(f'/api/studies/{sid}/start', headers=headers).status_code == 409


def test_ownership_and_snapshots(app,client):
    h=login(client)
    s=make_study(client,h)
    aid=s['slots'][0]['ad_id']
    assert client.patch(f'/api/ads/{aid}',json={'title':'Cambiado'},headers=h).status_code==200
    assert client.get(f"/api/studies/{s['id']}").json['slots'][0]['title']=='Anuncio uno'
    other=app.test_client();oh=login(other,'other@test.cl')
    assert other.get(f"/api/studies/{s['id']}/results").status_code==403
    assert other.patch(f'/api/ads/{aid}',json={'title':'Ajeno'},headers=oh).status_code==403
    assert other.post('/api/studies',json={'name':'Mal','ad_ids':[aid]},headers=oh).status_code==403


def test_full_session_and_interval_accounting(app,client):
    h=login(client);s=make_study(client,h,True);sid=s['id']
    fake=FakeVision();app.extensions['vision']=fake
    assert client.post(f'/api/studies/{sid}/start',headers=h).status_code==409
    calibrate(client,h,sid,fake)
    assert client.post(f'/api/studies/{sid}/start',headers=h).status_code==200
    with app.app_context():
        st=db.session.get(Study,sid);st.started_at=utcnow()-timedelta(seconds=20);db.session.commit()
    for seq,t in enumerate([0.,.5,1.,4.,4.5]):
        fake.iris=[.3,.5]
        r=client.post(f'/api/studies/{sid}/observations',data={'seq':str(seq),'elapsed':str(t),'frame':(jpeg(),'f.jpg')},headers=h)
        assert r.status_code==200,r.json
    assert client.post(f'/api/studies/{sid}/observations',data={'seq':'4','elapsed':'4.5','frame':(jpeg(),'f.jpg')},headers=h).status_code==409
    fake.iris=None;fake.reason='sin_rostro'
    assert client.post(f'/api/studies/{sid}/observations',data={'seq':'5','elapsed':'5','frame':(jpeg(),'f.jpg')},headers=h).status_code==200
    fake.iris=[.3,.5]
    assert client.post(f'/api/studies/{sid}/observations',data={'seq':'6','elapsed':'5.5','frame':(jpeg(),'f.jpg')},headers=h).status_code==200
    assert client.post(f'/api/studies/{sid}/stop',headers=h).status_code==200
    result=client.get(f'/api/studies/{sid}/results').json
    assert result['estimated_seconds']==1.5 # gap de 3 s y pérdida de rostro no se suman
    assert result['valid_samples']==6
    assert result['total_samples']==7
    assert result['ads'][0]['seconds']==1.5
    assert result['ads'][1]['seconds']==0
    assert result['emotions']=={'Alegria':7}
    download = client.get(f'/api/studies/{sid}/export.csv')
    assert download.status_code == 200 and download.mimetype == 'text/csv'
    assert len(download.data.decode('utf-8-sig').splitlines()) == 1 + result['total_samples']
    assert client.post(f'/api/studies/{sid}/observations',data={},headers=h).status_code==409


@pytest.mark.parametrize('extension', ['csv', 'pdf'])
def test_cancelled_export_is_blocked_on_direct_request(client, extension):
    headers = login(client)
    study = make_study(client, headers)
    path = f"/api/studies/{study['id']}"
    cancelled = client.post(path + '/stop', headers=headers).json
    assert cancelled['status'] == 'cancelled'
    response = client.get(path + '/export.' + extension)
    assert response.status_code == 409
    assert response.json['error'] == cancelled['export_block_reason'] == 'Las sesiones canceladas no se pueden exportar'
    assert 'Content-Disposition' not in response.headers


def test_delete_study_protects_owner_and_running_capture(app, client):
    h = login(client)
    study = make_study(client, h)
    sid = study['id']
    path = f'/api/studies/{sid}'
    other = app.test_client()
    assert other.delete(path, headers=login(other, 'admin@test.cl')).status_code == 403
    fake = FakeVision()
    app.extensions['vision'] = fake
    calibrate(client, h, sid, fake)
    assert client.post(path + '/start', headers=h).status_code == 200
    assert client.post(path + '/observations', headers=h, data={
        'seq': '0', 'elapsed': '0', 'frame': (jpeg(), 'frame.jpg')}).status_code == 200
    assert client.delete(path, headers=h).status_code == 409
    assert client.get(path + '/results').json['total_samples'] == 1
    assert client.post(path + '/stop', headers=h).status_code == 200
    assert client.delete(path, headers=h).status_code == 204
    assert client.get(path + '/results').status_code == 404
    assert client.get('/api/studies').json == []
    assert len(client.get('/api/ads').json) == 2
    with app.app_context():
        assert db.session.get(Calibration, sid) is None
        for model in (Observation, StudyAd):
            assert db.session.scalar(select(model.id).where(model.study_id == sid)) is None


def test_calibration_insufficient_and_degenerate(app,client):
    h=login(client);sid=make_study(client,h)['id'];app.extensions['vision']=FakeVision()
    client.post(f'/api/studies/{sid}/calibration/start',json={'width':1200,'height':800},headers=h)
    assert client.post(f'/api/studies/{sid}/calibration/finish',headers=h).status_code==400
    for i in range(9):
        for _ in range(10):
            assert client.post(f'/api/studies/{sid}/calibration/sample',data={'target':str(i),'frame':(jpeg(),'f.jpg')},headers=h).status_code==200
    assert client.post(f'/api/studies/{sid}/calibration/finish',headers=h).status_code==400


def test_admin_account_validation(client):
    h=login(client,'admin@test.cl')
    uid=client.get('/api/auth/me').json['user']['id']
    assert client.patch(f'/api/users/{uid}',json={'name':'Admin','email':'admin@test.cl','role':'owner'},headers=h).status_code==400
    assert client.post('/api/users',json={'name':'Nueva','email':'nueva@test.cl','password':'corta'},headers=h).status_code==400
    r=client.post('/api/users',json={'name':'Nueva','email':'nueva@test.cl','password':'Password12345'},headers=h)
    assert r.status_code==201
    assert 'password_hash' not in r.json


def test_upload_private_media_and_invalid_input(app,client):
    h=login(client);sid=make_study(client,h)['id'];ad=client.get(f'/api/studies/{sid}').json['slots'][0]['ad_id']
    assert client.post(f'/api/ads/{ad}/image',data={'image':(io.BytesIO(b'bad'),'x.png')},headers=h).status_code==400
    r=client.post(f'/api/ads/{ad}/image',data={'image':(jpeg(),'x.jpg')},headers=h)
    assert r.status_code==200,r.json
    url=r.json['image_url']
    assert client.get(url).status_code==200
    other=app.test_client();login(other,'other@test.cl')
    assert other.get(url).status_code==403
    assert client.post('/api/studies',json={'name':'n','ad_ids':[ad,ad]},headers=h).status_code==400


def test_ad_image_and_metadata_are_saved_together(client):
    headers = login(client)
    png = io.BytesIO()
    Image.new('RGBA', (48, 96), (255, 0, 0, 0)).save(png, 'PNG')
    png.seek(0)
    saved = client.post('/api/ads', headers=headers, data={
        'title': 'Original', 'active': 'true', 'image': (png, 'vertical.png')})
    assert saved.status_code == 201
    ad = saved.json
    with Image.open(io.BytesIO(client.get(ad['image_url']).data)) as displayed:
        assert displayed.size == (48, 96)
        assert displayed.getpixel((0, 0)) == (0, 0, 0)
    gif = io.BytesIO()
    Image.new('RGB', (1, 1)).save(gif, 'GIF')
    gif.seek(0)
    for invalid, code in [(io.BytesIO(b'damaged'), 400), (gif, 400),
                          (io.BytesIO(bytes(6 * 1024 * 1024 + 1)), 413)]:
        response = client.patch(f"/api/ads/{ad['id']}", headers=headers, data={
            'title': 'Intento de cambio', 'image': (invalid, 'reemplazo.jpg')})
        assert response.status_code == code
        assert client.get('/api/ads').json == [ad]
    changed = client.patch(f"/api/ads/{ad['id']}", headers=headers, data={
        'title': 'Nueva imagen', 'image': (jpeg(), 'nueva.jpg')})
    assert changed.status_code == 200
    assert changed.json['image_url'] != ad['image_url']


def test_edit_ads_before_calibration_keeps_study_and_history(app, client):
    headers = login(client)
    study = make_study(client, headers)
    first, second = [slot['ad_id'] for slot in study['slots']]
    history = client.post('/api/studies', headers=headers,
                          json={'name': 'Otra sesión', 'ad_ids': [first]}).json
    third = client.post('/api/ads', headers=headers, json={'title': 'Tercero'}).json['id']
    client.patch(f'/api/ads/{first}', headers=headers,
                 data={'title': 'Actualizado', 'image': (jpeg(), 'foto.jpg')})
    path = f"/api/studies/{study['id']}"
    other = app.test_client()
    assert other.patch(path + '/ads', headers=login(other, 'other@test.cl'),
                       json={'ad_ids': [first]}).status_code == 403
    for invalid in [[], [first, first], [third, 99999]]:
        assert client.patch(path + '/ads', headers=headers, json={'ad_ids': invalid}).status_code >= 400
        assert client.get(path).json['slots'] == study['slots']
    order = [second, third, first]
    updated = client.patch(path + '/ads', headers=headers, json={'ad_ids': order}).json
    assert updated['id'] == study['id'] and updated['layout_columns'] == 3
    assert [slot['ad_id'] for slot in updated['slots']] == order
    assert updated['slots'][2]['title'] == 'Actualizado' and updated['slots'][2]['image_url']
    assert client.get(f"/api/studies/{history['id']}").json['slots'] == history['slots']
    assert client.post(path + '/calibration/start', headers=headers,
                       json={'width': 1200, 'height': 800}).status_code == 200
    assert client.patch(path + '/ads', headers=headers, json={'ad_ids': [third]}).status_code == 409
    assert client.get(path).json['slots'] == updated['slots']
