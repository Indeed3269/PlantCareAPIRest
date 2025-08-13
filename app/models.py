from datetime import datetime, timedelta, timezone
import time
from app import db

def get_pacific_time():
    utc_now = datetime.now(timezone.utc)
    is_dst = time.localtime().tm_isdst > 0
    offset = timedelta(hours=7 if is_dst else 8)
    return (utc_now - offset).replace(tzinfo=None)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=get_pacific_time, index=True)
    syncs = db.relationship('Sync', back_populates='usuario', cascade='all, delete-orphan')

class Devices(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    udid = db.Column(db.String(128), unique=True, nullable=False)
    syncs = db.relationship('Sync', back_populates='dispositivo', cascade='all, delete-orphan')
    logs = db.relationship('Log', back_populates='device', cascade='all, delete-orphan')

class Sync(db.Model):
    __tablename__ = 'sync'
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=get_pacific_time, index=True)
    usuario = db.relationship('Usuario', back_populates='syncs')
    dispositivo = db.relationship('Devices', back_populates='syncs')

class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    temp = db.Column(db.Float, nullable=False)
    moisture_dirt = db.Column(db.Float, nullable=False)
    moisture_air = db.Column(db.Float, nullable=False)
    raw_soil = db.Column(db.Float, nullable=True)
    raw_calMin = db.Column(db.Float, nullable=True)
    raw_calMax = db.Column(db.Float, nullable=True)
    soil_type = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=get_pacific_time, index=True)
    device = db.relationship('Devices', back_populates='logs')