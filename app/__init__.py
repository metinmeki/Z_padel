import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config

# ── Extensions (created here, initialised in create_app) ──
db           = SQLAlchemy()
login_manager = LoginManager()
csrf         = CSRFProtect()


def create_app(config_name: str = None):
    config_name = config_name or os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    # ── Init extensions ──
    db.init_app(app)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view       = 'auth.login'
    login_manager.login_message    = 'يرجى تسجيل الدخول للوصول إلى هذه الصفحة.'
    login_manager.login_message_category = 'info'

    # ── Ensure upload folders exist ──
    os.makedirs(app.config['UPLOAD_FOLDER'],   exist_ok=True)
    os.makedirs(app.config['RECEIPTS_FOLDER'], exist_ok=True)

    # ── Register blueprints ──
    from app.routes.auth    import auth_bp
    from app.routes.main    import main_bp
    from app.routes.admin   import admin_bp
    from app.routes.booking import booking_bp
    from app.routes.store   import store_bp
    from app.routes.pos     import pos_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp,   url_prefix='/admin')
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(store_bp,   url_prefix='/store')
    app.register_blueprint(pos_bp,     url_prefix='/pos')

    # ── Create DB tables ──
    with app.app_context():
        db.create_all()
        _seed_admin(app)

    return app


def _seed_admin(app):
    """Create default superadmin if no users exist."""
    from app.models.main import Admin
    from werkzeug.security import generate_password_hash
    with app.app_context():
        if not Admin.query.first():
            admin = Admin(
                username='admin',
                password=generate_password_hash('admin123'),
                role='superadmin',
                is_active=True,
            )
            db.session.add(admin)
            db.session.commit()
            print('✅  Default admin created  →  admin / admin123')