from flask import Blueprint, request, jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from app import db, limiter
from app.models import Usuario, Devices, Log, Sync
from app.utils import jsonifiedlog

bp = Blueprint('legacy', __name__)

mild = "10 per minute"
medium = "5 per minute"
strict = "2 per minute"

@bp.route('/api/devices/debug-list', methods=['GET'])
@limiter.limit(mild)
def old_debug_device_list():
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

@bp.route('/api/iot/register', methods=['POST'])
@limiter.limit(strict)
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

@bp.route('/api/iot/share', methods=['POST'])
@limiter.limit(medium)
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

@bp.route('/api/iot/<string:email>', methods=['GET'])
@limiter.limit(medium)
def old_get_user_devices(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return jsonify({'error': 'Email no registrado'}), 404

    dispositivos = db.session.query(Devices.udid).join(Sync).filter(
        Sync.user_id == usuario.id
    ).all()

    return jsonify([d.udid for d in dispositivos])

@bp.route('/api/logs/device/<string:udid>', methods=['GET']) # Logs de dispositivo individual
@limiter.limit(mild)
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

@bp.route('/api/logs/user-device/<string:email>/<string:udid>', methods=['GET']) # Logs de dispositivo individual (con verificacion de usuario)
@limiter.limit(mild)
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