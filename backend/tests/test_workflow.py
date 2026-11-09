import io
from datetime import timedelta
from sqlalchemy import select
from backend.models import Study, Observation, User, db, utcnow
from conftest import login, make_study, FakeVision, calibrate, jpeg


def test_auth_csrf_and_roles(client):
    assert client.get('/api/ads').status_code==401
    assert client.post('/api/auth/login',json={}).status_code==403
    h=login(client)
    assert client.get('/api/users').status_code==403
    assert client.post('/api/users',json={},headers=h).status_code==403
    assert client.post('/api/ads',json={'title':'<script>texto</script>'},headers=h).status_code==201


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
    assert client.get(f'/api/studies/{sid}/export.csv').status_code==200
    assert client.post(f'/api/studies/{sid}/observations',data={},headers=h).status_code==409


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
