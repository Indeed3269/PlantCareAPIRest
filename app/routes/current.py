from flask import Blueprint, request, jsonify, redirect
from sqlalchemy import func
from app import db, limiter
from app.models import Usuario, Devices, Sync, Log
from app.utils import jsonifiedlog
from datetime import datetime

bp = Blueprint('current', __name__)
mild = "10 per minute"
medium = "5 per minute"
strict = "2 per minute"

@bp.before_request
def enforce_https():
    if request.headers.get('X-Forwarded-Proto') == 'http':
        return redirect(request.url.replace('http://', 'https://', 1), 301)

# Debug route
@bp.route('/iot/debug-list', methods=['GET'])
@limiter.limit(medium)
def show_known():
    try:
        devices = db.session.query(
            Devices.udid,
            Usuario.email,
            func.count(Log.id).label('total_logs')
        ).outerjoin(Sync, Sync.device_id == Devices.id
        ).outerjoin(Usuario, Usuario.id == Sync.user_id
        ).outerjoin(Log, Log.device_id == Devices.id
        ).group_by(Devices.udid, Usuario.email).all()

        response = [{
            'udid': device.udid,
            'registered_to': device.email,
            'logs_count': device.total_logs
        } for device in devices]

        return jsonify({'devices': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Device routes
@bp.route('/iot/register', methods=['POST'])
@limiter.limit(medium)
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

@bp.route('/iot/share', methods=['POST'])
@limiter.limit(strict)
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

@bp.route('/iot/<string:email>', methods=['GET'])
@limiter.limit(strict)
def get_user_devices(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Email no registrado'}), 404

    dispositivos = db.session.query(Devices.udid).join(Sync).filter(
        Sync.user_id == usuario.id
    ).all()

    return jsonify([d.udid for d in dispositivos])

# Log routes
@bp.route('/logs/submit', methods=['POST'])
@limiter.limit(strict)
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

@bp.route('/logs/<string:udid>', methods=['GET'])
@limiter.limit(mild)
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
            logs = Log.query.filter(Log.created_at >= since_datetime).order_by(Log.created_at.desc()).all()
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DDTHH:MM:SS'}), 400
    elif latest and latest.lower() == 'true':
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).limit(1).all()
    else:
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).paginate(page=page, per_page=page_size, error_out=False).items
    

    return jsonifiedlog(logs)

@bp.route('/logs/<string:email>/<string:udid>', methods=['GET'])
@limiter.limit(mild)
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
            logs = Log.query.filter(Log.created_at >= since_datetime).all()
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DDTHH:MM:SS'}), 400
    elif latest and latest.lower() == 'true':
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).limit(1).all()
    else:
        logs = Log.query.filter_by(device_id=dispositivo.id).order_by(Log.created_at.desc()).paginate(page=page, per_page=page_size, error_out=False).items
    

    return jsonifiedlog(logs)