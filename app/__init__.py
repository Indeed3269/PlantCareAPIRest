from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

# Inicializacion de extensiones
db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["2000 per day", "100 per hour"]
)

def create_app():
    app = Flask(__name__)

    # Cargar config
    app.config.from_object('app.config.Config')

    # Init extensiones
    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Proxy Cloudflare
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Register routes
    from app.routes import current, legacy
    app.register_blueprint(current.bp)
    app.register_blueprint(legacy.bp)

    return app