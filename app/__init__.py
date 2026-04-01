from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.main import main
    from app.routes.booking import booking
    from app.routes.auth import auth
    from app.routes.admin import admin
    from app.routes.store import store

    app.register_blueprint(main)
    app.register_blueprint(booking)
    app.register_blueprint(auth)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(store)

    with app.app_context():
        from app import models
        from app.models import store as store_models
        db.create_all()

    return app