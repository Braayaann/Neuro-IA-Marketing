import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app import create_app
from backend.models import User, db


@pytest.fixture
def app(tmp_path):
    test_url = 'sqlite:///' + str(tmp_path/'test.sqlite')
    app = create_app({'TESTING':True, 'SECRET_KEY':'test-only-key', 'SQLALCHEMY_DATABASE_URI':test_url,
                      'UPLOAD_DIR':str(tmp_path/'uploads')})
    with app.app_context():
        db.create_all()
        for email, role in [('admin@test.cl','admin'), ('owner@test.cl','owner'), ('other@test.cl','owner')]:
            db.session.add(User(name=role, email=email, role=role, password_hash=generate_password_hash('TestPassword123!')))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email='owner@test.cl'):
    token=client.get('/api/auth/me').json['csrf']
    r=client.post('/api/auth/login', json={'email':email,'password':'TestPassword123!'}, headers={'X-CSRF-Token':token})
    assert r.status_code==200, r.json
    return {'X-CSRF-Token':r.json['csrf']}


def make_study(client, headers, emotions=False):
    ids=[]
    for title in ['Anuncio uno','Anuncio dos']:
        r=client.post('/api/ads',json={'title':title},headers=headers)
        assert r.status_code==201,r.json
        ids.append(r.json['id'])
    r=client.post('/api/studies',json={'name':'Prueba','ad_ids':ids,'with_emotions':emotions},headers=headers)
    assert r.status_code==201,r.json
    return r.json


def jpeg():
    stream=io.BytesIO()
    Image.new('RGB',(100,100),'white').save(stream,'JPEG')
    stream.seek(0)
    return stream


class FakeVision:
    def __init__(self):
        self.iris=[.3,.5]
        self.reason=''
    def analyze(self, jpeg, emotions=False):
        return dict(iris=self.iris, reason=self.reason, emotion='Alegria' if emotions else None,
                    confidence=.8 if emotions else None)


def calibrate(client, headers, sid, vision):
    from mirada.calibracion import OBJETIVOS
    assert client.post(f'/api/studies/{sid}/calibration/start',json={'width':1200,'height':800},headers=headers).status_code==200
    for i,xy in enumerate(OBJETIVOS):
        vision.iris=list(xy)
        for _ in range(10):
            r=client.post(f'/api/studies/{sid}/calibration/sample', data={'target':str(i),'frame':(jpeg(),'f.jpg')},headers=headers)
            assert r.status_code==200,r.json
    r=client.post(f'/api/studies/{sid}/calibration/finish',headers=headers)
    assert r.status_code==200,r.json
