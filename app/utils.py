from flask import jsonify
from app.models import Log

def jsonifiedlog(logs):
    return jsonify([{
        'temp': log.temp,
        'moisture_dirt': log.moisture_dirt,
        'moisture_air': log.moisture_air,
        'raw_soil': log.raw_soil,
        'raw_calMin': log.raw_calMin,
        'raw_calMax': log.raw_calMax,
        'soil_type': log.soil_type,
        'timestamp': log.created_at.isoformat()
    } for log in logs])