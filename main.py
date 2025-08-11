from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
import time
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
    default_limits=["2000 per day", "100 per hour"]
)

# Base de Datos
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(basedir, "app.db")}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


def get_pacific_time():
    # Get current timezone-aware UTC time
    utc_now = datetime.now(timezone.utc)
    
    # Tijuana is UTC-8 (PST) or UTC-7 (PDT during DST)
    is_dst = time.localtime().tm_isdst > 0
    offset = timedelta(hours=7 if is_dst else 8)
    
    # Return as timezone-naive datetime (compatible with SQLite)
    return (utc_now - offset).replace(tzinfo=None)
# ================================
# Modelos de Datos
# ================================


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=get_pacific_time, index=True)
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
    created_at = db.Column(db.DateTime, default=get_pacific_time, index=True)
    
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
    raw_soil = db.Column(db.Float, nullable=True)
    raw_calMin = db.Column(db.Float, nullable=True)
    raw_calMax = db.Column(db.Float, nullable=True)
    soil_type = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=get_pacific_time, index=True)
    
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
@app.route('/iot/debug-list', methods=['GET'])
def show_known():
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
# Rutas de Dispositivos
# ==============================================
@app.route('/iot/register', methods=['POST']) # Registro de enlace dispositivo-usuario
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

@app.route('/iot/share', methods=['POST']) # Compartir dispositivo existente con otro usuario
def share_device():
    # Payload: {"udid": "ESP32-123", "email_personal": "miemail@gmail.com", "email": "correoamigo@gmail.com"}

    data = request.get_json()
    alerta = ''
    

    # Consulta de dispositivo
    dispositivo = Devices.query.filter_by(udid=data['udid']).first()
    if not dispositivo:
        alerta += 'Dispositivo no encontrado. '

    # Consulta de usuario sincronizado
    usr_primario = Usuario.query.filter_by(email=data['email_personal']).first()
    if not usr_primario:
        alerta += 'Usuario primario no encontrado. '
    elif not Sync.query.filter_by(user_id=usr_primario.id, device_id=dispositivo.id).first():
        alerta += 'Dispositivo no asociado al usuario primario. '

    if alerta:
        return jsonify({'error': alerta}), 403
    
    # Consulta de usuario a compartir
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

@app.route('/iot/<string:email>', methods=['GET']) #Obtener todos los dispositivos asociados a un usuario
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
@app.route('/logs/submit', methods=['POST']) #Envio de datos de sensores
def submit_log():
    #Payload: {"udid": "ESP32-123", "temp": 25.5, "moisture_dirt": 40, "moisture_air": 60, "raw_soil": 2034, "soil_type": 1}

    try:
        data = request.get_json()
        required = ['udid', 'temp', 'moisture_dirt', 'moisture_air', 'raw_soil','raw_calMin','raw_calMax', 'soil_type']
        if not all(field in data for field in required):
            return jsonify({'error': 'Campos requeridos faltantes'}), 400

        dispositivo = Devices.query.filter_by(udid=data['udid']).first()
        if not dispositivo:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404

        nuevo_log = Log(
            device_id=dispositivo.id,
            temp=float(data['temp']),
            moisture_dirt=float(data['moisture_dirt']),
            moisture_air=float(data['moisture_air']),
            raw_soil=float(data['raw_soil']),
            raw_calMin=float(data['raw_calMin']),
            raw_calMax=float(data['raw_calMax']),
            soil_type=int(data['soil_type'])
        )
        db.session.add(nuevo_log)
        db.session.commit()
        return jsonify({'message': 'Datos guardados'}), 201       
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/logs/<string:udid>', methods=['GET']) # Logs de dispositivo individual
def get_device_logs(udid):
    # Param opcional: ?page=# ?page_size=# ?all=true ?since=YYYY-MM-DDTHH:MM:SS
    
    page = request.args.get('page', default=1, type=int)
    page_size = request.args.get('page_size', default=10, type=int)
    all_logs = request.args.get('all', default='false', type=str).lower() == 'true'
    since_str = request.args.get('since', type=str)
    latest = request.args.get('latest', type=str)
    dispositivo = Devices.query.filter_by(udid=udid).first()

    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    if all_logs:
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).all()
    elif since_str:
        try:
            # Parseamos la fecha CON segundos (formato: YYYY-MM-DDTHH:MM:SS)
            since_datetime = datetime.strptime(since_str, '%Y-%m-%dT%H:%M:%S')
            # Filtramos registros >= al timestamp proporcionado (ignorando microsegundos en la comparación)
            logs = Log.query.filter(Log.created_at >= since_datetime)
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DDTHH:MM:SS'}), 400
    elif latest and latest.lower() == 'true':
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).limit(1).all()
    else:
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).paginate(page, page_size, False).items
    

    return jsonify([{
        'temp': log.temp,
        'moisture_dirt': log.moisture_dirt,
        'moisture_air': log.moisture_air,
        'raw_soil': log.raw_soil,
        'soil_type': log.soil_type,
        'timestamp': log.created_at.isoformat()
    } for log in logs])

@app.route('/logs/<string:email>/<string:udid>', methods=['GET']) # Logs de dispositivo individual (con verificacion de usuario)
def get_user_device_logs(email, udid):
    # Param opcional: ?page=# ?page_size=# ?all=true ?since=YYYY-MM-DDTHH:MM:SS
    page = request.args.get('page', default=1, type=int)
    page_size = request.args.get('page_size', default=10, type=int)
    all_logs = request.args.get('all', default='false', type=str).lower() == 'true'
    since_str = request.args.get('since', type=str)
    latest = request.args.get('latest', type=str)

    # Validacion de usuario y dispositivo
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    dispositivo = Devices.query.filter_by(udid=udid).first()
    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    # Verificar que el dispositivo pertenece al usuario
    if not Sync.query.filter_by(user_id=usuario.id, device_id=dispositivo.id).first():
        return jsonify({'error': 'Dispositivo no asociado al usuario'}), 403

    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404
    
    # Consulta de logs
    if all_logs:
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).all()
    elif since_str:
        try:
            # Parseamos la fecha CON segundos (formato: YYYY-MM-DDTHH:MM:SS)
            since_datetime = datetime.strptime(since_str, '%Y-%m-%dT%H:%M:%S')
            # Filtramos registros >= al timestamp proporcionado (ignorando microsegundos en la comparación)
            logs = Log.query.filter(Log.created_at >= since_datetime)
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DDTHH:MM:SS'}), 400
    elif latest and latest.lower() == 'true':
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).limit(1).all()
    else:
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).paginate(page, page_size, False).items
    

    return jsonify([{
        'temp': log.temp,
        'moisture_dirt': log.moisture_dirt,
        'moisture_air': log.moisture_air,
        'raw_soil': log.raw_soil,
        'soil_type': log.soil_type,
        'timestamp': log.created_at.isoformat()
    } for log in logs])

# ==============================================
# Rutas antiguas
# ==============================================
@app.route('/api/devices/debug-list', methods=['GET']) # Lista de todos los dispositivos y sus relaciones
def old_debug_device_list():
    try:
        # devices": [ { "udid": "ESP32-123", "logs_count": 42, "registered_users_count": 3 } ]
        devices = db.session.query(
            Devices.udid,
            func.count(Log.id).label('total_logs'),
            func.count(Sync.user_id).label('user_count')  # Count of registered users
        ).outerjoin(Log, Log.device_id == Devices.id
        ).outerjoin(Sync, Sync.device_id == Devices.id
        ).group_by(Devices.udid).all()

        # Format response
        response = [{
            'udid': device.udid,
            'logs_count': device.total_logs,
            'registered_users_count': device.user_count
        } for device in devices]

        return jsonify({'devices': response})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Rutas de Usuarios y Dispositivos
@app.route('/api/iot/register', methods=['POST'])
def old_register_iot_device():
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
def old_share_device():
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
def old_get_user_devices(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Email no registrado'}), 404

    dispositivos = db.session.query(Devices.udid).join(Sync).filter(
        Sync.user_id == usuario.id
    ).all()

    return jsonify([d.udid for d in dispositivos])

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Email no registrado'}), 404

    dispositivos = db.session.query(Devices.udid).join(Sync).filter(
        Sync.user_id == usuario.id
    ).all()

    return jsonify([d.udid for d in dispositivos])
# Rutas de Logs
@app.route('/api/logs/device/<string:udid>', methods=['GET']) # Logs de dispositivo individual
def old_get_specific_device_logs(udid):
    # Param opcional: ?days=7 (últimos X días)
    # Param opcional: ?latest=true o ?amount=5 (ultimo/ultimos x registros)

    
    days = request.args.get('days', type=int)
    latest = request.args.get('latest', type=str)
    amount = request.args.get('amount', type=int)
    since_str = request.args.get('since', type=str)
    
    dispositivo = Devices.query.filter_by(udid=udid).first()
    if not dispositivo:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    query = Log.query.filter_by(device_id=dispositivo.id)

    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Log.created_at >= cutoff_date)
    
    if since_str:
        try:
            # Parseamos la fecha CON segundos (formato: YYYY-MM-DDTHH:MM:SS)
            since_datetime = datetime.strptime(since_str, '%Y-%m-%dT%H:%M:%S')
            # Filtramos registros >= al timestamp proporcionado (ignorando microsegundos en la comparación)
            query = query.filter(Log.created_at >= since_datetime)
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DDTHH:MM:SS'}), 400

    if latest and latest.lower() == 'true':
        logs = query.order_by(Log.created_at.desc()).limit(1).all()
    elif amount:
        logs = query.order_by(Log.created_at.desc()).limit(amount).all()
    else:
        logs = query.order_by(Log.created_at.desc()).all()

    return jsonify([{
        'temp': log.temp,
        'moisture_dirt': log.moisture_dirt,
        'moisture_air': log.moisture_air,
        'timestamp': log.created_at.isoformat()
    } for log in logs])

@app.route('/api/logs/user-device/<string:email>/<string:udid>', methods=['GET']) # Logs de dispositivo individual (con verificacion de usuario)
def old_get_user_device_logs(email, udid):
    # Param opcional: ?days=7 (últimos X días)
    # Param opcional: ?latest=true o ?amount=5 (ultimo/ultimos x registros)

    
    days = request.args.get('days', type=int)
    latest = request.args.get('latest', type=str)
    amount = request.args.get('amount', type=int)
    
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
    
    if latest and latest.lower() == 'true':
        logs = query.order_by(Log.created_at.desc()).limit(1).all()
    elif amount:
        logs = query.order_by(Log.created_at.desc()).limit(amount).all()
    else:
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
