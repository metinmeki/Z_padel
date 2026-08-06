import os
from flask import Flask, session, g, request as flask_request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate  # ✅ ADD THIS
from config import config

# ── Extensions (created here, initialised in create_app) ──
db           = SQLAlchemy()
migrate      = Migrate()  # ✅ ADD THIS
login_manager = LoginManager()
csrf         = CSRFProtect()


def create_app(config_name: str = None):
    config_name = config_name or os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    # ── Init extensions ──
    db.init_app(app)
    migrate.init_app(app, db)  # ✅ ADD THIS
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view       = 'auth.login'
    login_manager.login_message    = 'يرجى تسجيل الدخول للوصول إلى هذه الصفحة.'
    login_manager.login_message_category = 'info'

    # ── Ensure upload folders exist ──
    os.makedirs(app.config['UPLOAD_FOLDER'],   exist_ok=True)
    os.makedirs(app.config['RECEIPTS_FOLDER'], exist_ok=True)
    os.makedirs(app.config['CLIPS_FOLDER'],    exist_ok=True)

    # ── Static file caching (1 week) ──
    @app.after_request
    def add_cache_headers(response):
        if flask_request.path.startswith('/static/'):
            response.cache_control.max_age = 604800  # 7 days
            response.cache_control.public = True
        return response

    # ── Language middleware ──
    @app.before_request
    def set_lang():
        g.lang = session.get('lang', 'en')

    @app.context_processor
    def inject_lang():
        return dict(lang=g.lang)

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
        _add_missing_columns(app)
        _seed_admin(app)
        _seed_activities(app)

    return app


def _add_missing_columns(app):
    """Add any new columns that db.create_all() won't add to existing tables."""
    from sqlalchemy import text
    alters = [
        "ALTER TABLE order_items ADD COLUMN product_name VARCHAR(120)",
        "ALTER TABLE products ADD COLUMN max_stock INTEGER DEFAULT 50",
        "ALTER TABLE products ADD COLUMN show_on_website BOOLEAN DEFAULT 0",
        "ALTER TABLE products ADD COLUMN description_ar TEXT",
        "ALTER TABLE products ADD COLUMN description_ku TEXT",
    ]
    with app.app_context():
        with db.engine.connect() as conn:
            for stmt in alters:
                try:
                    conn.execute(text(stmt))
                    conn.commit()
                except Exception:
                    pass  # column already exists


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


def _seed_activities(app):
    """Create default activity tables if none exist."""
    from app.models.main import ActivityTable
    with app.app_context():
        if ActivityTable.query.count() == 0:
            defaults = [
                ActivityTable(name='Table 1', activity='snooker',      hourly_rate=12000),
                ActivityTable(name='Table 2', activity='snooker',      hourly_rate=12000),
                ActivityTable(name='Table 1', activity='billiard',     hourly_rate=10000),
                ActivityTable(name='Table 1', activity='table_tennis', hourly_rate=5000),
            ]
            db.session.add_all(defaults)
            db.session.commit()
            print('✅  Default activity tables created')
        # Seed spectator tables if none exist yet
        if ActivityTable.query.filter_by(activity='spectator').count() == 0:
            spectators = [
                ActivityTable(name='طاولة 1', activity='spectator', hourly_rate=0),
                ActivityTable(name='طاولة 2', activity='spectator', hourly_rate=0),
                ActivityTable(name='طاولة 3', activity='spectator', hourly_rate=0),
            ]
            db.session.add_all(spectators)
            db.session.commit()
            print('✅  Spectator tables created')