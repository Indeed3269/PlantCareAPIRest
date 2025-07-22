from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timedelta
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


app = Flask(__name__)
CORS(app)

# Cloudflare Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)

# Base de Datos
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(basedir, "app.db")}'
).replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)



# ================================
# Modelos de Datos
# ================================


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Relación con Sync (un usuario puede tener múltiples dispositivos)
    syncs = db.relationship('Sync', back_populates='usuario', cascade='all, delete-orphan')

class Devices(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    udid = db.Column(db.String(128), unique=True, nullable=False)
    # Relación con Sync (un dispositivo puede pertenecer a múltiples usuarios)
    syncs = db.relationship('Sync', back_populates='dispositivo', cascade='all, delete-orphan')
    # Relación directa con logs
    logs = db.relationship('Log', back_populates='device', cascade='all, delete-orphan')

class Sync(db.Model):
    __tablename__ = 'sync'
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones (nombres más claros)
    usuario = db.relationship('Usuario', back_populates='syncs')
    dispositivo = db.relationship('Devices', back_populates='syncs')

class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    temp = db.Column(db.Float, nullable=False)
    moisture_dirt = db.Column(db.Float, nullable=False)
    moisture_air = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relación explícita
    device = db.relationship('Devices', back_populates='logs')

# Creacion de tablas
with app.app_context():
    db.create_all()

# ==============================================
# Middlewares
# ==============================================


@app.before_request
def enforce_https():
    if request.headers.get('X-Forwarded-Proto') == 'http':
        return redirect(request.url.replace('http://', 'https://', 1), 301)
    

# ==============================================
# Ruta de desarrollo 
# ==============================================
@app.route('/api/devices/debug-list', methods=['GET']) # Lista de todos los dispositivos y sus relaciones
def debug_device_list():
    try:
        # Obtener dispositivos con información asociada
        devices = db.session.query(
            Devices.udid,
            Usuario.email,
            func.count(Log.id).label('total_logs')
        ).outerjoin(Sync, Sync.device_id == Devices.id
        ).outerjoin(Usuario, Usuario.id == Sync.user_id
        ).outerjoin(Log, Log.device_id == Devices.id
        ).group_by(Devices.udid, Usuario.email).all()

        # Formatear respuesta
        response = [{
            'udid': device.udid,
            'registered_to': device.email,
            'logs_count': device.total_logs
        } for device in devices]

        return jsonify({'devices': response})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ==============================================
# Rutas de Usuarios y Dispositivos
# ==============================================


@app.route('/api/iot/register', methods=['POST'])
def register_iot_device():
    data = request.get_json()
    
    # Validación
    if not data or 'udid' not in data or 'email' not in data:
        return jsonify({'error': 'Se requiere udid y email'}), 400

    try:
        # Registrar/actualizar usuario
        usuario = Usuario.query.filter_by(email=data['email']).first()
        if not usuario:
            usuario = Usuario(email=data['email'])
            db.session.add(usuario)
            db.session.flush()

        # Registrar dispositivo
        dispositivo = Devices.query.filter_by(udid=data['udid']).first()
        if not dispositivo:
            dispositivo = Devices(udid=data['udid'])
            db.session.add(dispositivo)
            db.session.flush()

        # Crear relación (evitando duplicados)
        sync = Sync.query.filter_by(user_id=usuario.id, device_id=dispositivo.id).first()
        if not sync:
            sync = Sync(user_id=usuario.id, device_id=dispositivo.id)
            db.session.add(sync)
        
        db.session.commit()
        return jsonify({
            'message': 'Dispositivo registrado',
            'udid': dispositivo.udid,
            'email': usuario.email
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/iot/share', methods=['POST']) # Compartir dispositivo existente con otro usuario
def share_device():
    # Payload: {"udid": "ESP32-123", "email": "correoamigo@gmail.com"}
    
    
    data = request.get_json()
    dispositivo = Devices.query.filter_by(udid=data['udid']).first()
    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    usuario = Usuario.query.filter_by(email=data['email']).first()
    if not usuario:
        usuario = Usuario(email=data['email'])
        db.session.add(usuario)
        db.session.flush()

    if not Sync.query.filter_by(user_id=usuario.id, device_id=dispositivo.id).first():
        nueva_relacion = Sync(user_id=usuario.id, device_id=dispositivo.id)
        db.session.add(nueva_relacion)
        db.session.commit()

    return jsonify({'message': 'Dispositivo compartido exitosamente'})

@app.route('/api/iot/<string:email>', methods=['GET']) #Obtener todos los dispositivos asociados a un usuario
def get_user_devices(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Email no registrado'}), 404

    dispositivos = db.session.query(Devices.udid).join(Sync).filter(
        Sync.user_id == usuario.id
    ).all()

    return jsonify([d.udid for d in dispositivos])

# ==============================================
# Rutas de Logs
# ==============================================
@app.route('/api/logs/submit', methods=['POST']) #Envio de datos de sensores
def submit_log():
    #Payload: {"udid": "ESP32-123", "temp": 25.5, "moisture_dirt": 40, "moisture_air": 60}

    try:
        data = request.get_json()
        required = ['udid', 'temp', 'moisture_dirt', 'moisture_air']
        if not all(field in data for field in required):
            return jsonify({'error': 'Campos requeridos faltantes'}), 400

        dispositivo = Devices.query.filter_by(udid=data['udid']).first()
        if not dispositivo:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404

        nuevo_log = Log(
            device_id=dispositivo.id,
            temp=float(data['temp']),
            moisture_dirt=float(data['moisture_dirt']),
            moisture_air=float(data['moisture_air'])
        )
        db.session.add(nuevo_log)
        db.session.commit()
        return jsonify({'message': 'Datos guardados'}), 201
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/device/<string:udid>', methods=['GET']) # Logs de dispositivo individual
def get_specific_device_logs(udid):
    # Param opcional: ?days=7 (últimos X días)

    
    days = request.args.get('days', type=int)
    
    dispositivo = Devices.query.filter_by(udid=udid).first()
    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    query = Log.query.filter_by(device_id=dispositivo.id)

    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Log.created_at >= cutoff_date)

    logs = query.order_by(Log.created_at.desc()).all()

    return jsonify([{
        'temp': log.temp,
        'moisture_dirt': log.moisture_dirt,
        'moisture_air': log.moisture_air,
        'timestamp': log.created_at.isoformat()
    } for log in logs])

@app.route('/api/logs/user-device/<string:email>/<string:udid>', methods=['GET']) # Logs de dispositivo individual (con verificacion de usuario)
def get_user_device_logs(email, udid):
    # Param opcional: ?days=7 (últimos X días)

    
    days = request.args.get('days', type=int)
    
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    dispositivo = Devices.query.filter_by(udid=udid).first()
    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    # Verificar que el dispositivo pertenece al usuario
    if not Sync.query.filter_by(user_id=usuario.id, device_id=dispositivo.id).first():
        return jsonify({'error': 'Dispositivo no asociado al usuario'}), 403

    query = Log.query.filter_by(device_id=dispositivo.id)

    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Log.created_at >= cutoff_date)

    logs = query.order_by(Log.created_at.desc()).all()

    return jsonify([{
        'temp': log.temp,
        'moisture_dirt': log.moisture_dirt,
        'moisture_air': log.moisture_air,
        'timestamp': log.created_at.isoformat()
    } for log in logs])

# ==============================================
# Inicio de la Aplicación
# ==============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)