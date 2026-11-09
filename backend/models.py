from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(10), nullable=False, default='owner')
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (CheckConstraint("role IN ('admin','owner')"),)

    def public(self):
        return dict(id=self.id, name=self.name, email=self.email, role=self.role, active=self.active)


class Ad(db.Model):
    __tablename__ = 'ads'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.String(500), nullable=False, default='')
    color = db.Column(db.String(7), nullable=False, default='#c7f36b')
    image = db.Column(db.String(80))
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def public(self):
        return dict(id=self.id, title=self.title, description=self.description, color=self.color,
                    active=self.active, image_url=f'/api/media/{self.image}' if self.image else None)


class Study(db.Model):
    __tablename__ = 'studies'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    status = db.Column(db.String(16), nullable=False, default='draft')
    camera_id = db.Column(db.String(300), default='')
    screen_width = db.Column(db.Integer)
    screen_height = db.Column(db.Integer)
    with_emotions = db.Column(db.Boolean, nullable=False, default=True)
    started_at = db.Column(db.DateTime(timezone=True))
    ended_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_seq = db.Column(db.Integer, nullable=False, default=-1)
    last_elapsed = db.Column(db.Float)
    last_ad_id = db.Column(db.Integer)
    slots = db.relationship('StudyAd', order_by='StudyAd.position', lazy='selectin')
    calibration = db.relationship('Calibration', uselist=False, lazy='selectin')
    __table_args__ = (CheckConstraint("status IN ('draft','calibrating','ready','running','completed','cancelled')"),)

    def public(self):
        return dict(id=self.id, name=self.name, status=self.status, with_emotions=self.with_emotions,
                    created_at=self.created_at.isoformat(),
                    started_at=self.started_at.isoformat() if self.started_at else None,
                    ended_at=self.ended_at.isoformat() if self.ended_at else None,
                    slots=[a.public() for a in self.slots],
                    calibrated=bool(self.calibration and self.calibration.coefficients),
                    camera_id=self.camera_id, screen_width=self.screen_width, screen_height=self.screen_height)


class StudyAd(db.Model):
    __tablename__ = 'study_ads'
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.ForeignKey('studies.id'), nullable=False, index=True)
    ad_id = db.Column(db.ForeignKey('ads.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    # Snapshot: las sesiones históricas no cambian al editar un anuncio.
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    color = db.Column(db.String(7), nullable=False)
    image = db.Column(db.String(80))
    __table_args__ = (UniqueConstraint('study_id', 'position'), UniqueConstraint('study_id', 'ad_id'),
                      CheckConstraint('position >= 0 AND position <= 3'))

    def public(self):
        return dict(id=self.id, ad_id=self.ad_id, position=self.position, title=self.title,
                    description=self.description, color=self.color,
                    image_url=f'/api/media/{self.image}' if self.image else None)


class Calibration(db.Model):
    __tablename__ = 'calibrations'
    study_id = db.Column(db.ForeignKey('studies.id'), primary_key=True)
    samples = db.Column(db.JSON, nullable=False, default=dict)
    mean = db.Column(db.JSON)
    scale = db.Column(db.JSON)
    coefficients = db.Column(db.JSON)
    completed_at = db.Column(db.DateTime(timezone=True))


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.ForeignKey('studies.id'), nullable=False, index=True)
    study_ad_id = db.Column(db.ForeignKey('study_ads.id'), index=True)
    seq = db.Column(db.Integer, nullable=False)
    elapsed = db.Column(db.Float, nullable=False)
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    valid = db.Column(db.Boolean, nullable=False)
    reason = db.Column(db.String(100), nullable=False, default='')
    emotion = db.Column(db.String(20))
    confidence = db.Column(db.Float)
    estimated_seconds = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint('study_id', 'seq'), CheckConstraint('elapsed >= 0'),
                      CheckConstraint('estimated_seconds >= 0'),)
