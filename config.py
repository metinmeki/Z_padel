import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ── Security ──
    SECRET_KEY = os.environ.get('SECRET_KEY', 'z-padel-secret-change-in-production')
    WTF_CSRF_ENABLED = True

    # ── Database ──
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASE_DIR, 'z_padel.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Session ──
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY     = True
    SESSION_COOKIE_SAMESITE     = 'Lax'

    # ── Uploads ──
    UPLOAD_FOLDER        = os.path.join(BASE_DIR, 'app', 'static', 'images', 'products')
    RECEIPTS_FOLDER      = os.path.join(BASE_DIR, 'app', 'static', 'receipts')
    MAX_CONTENT_LENGTH   = 4 * 1024 * 1024   # 4 MB
    ALLOWED_EXTENSIONS   = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

    # ── Business defaults (overridden by DB settings) ──
    DEFAULT_PRICE_PER_HOUR = 25_000   # IQD
    DISCOUNT_PERCENT       = 25
    DISCOUNT_START_HOUR    = 12
    DISCOUNT_END_HOUR      = 16
    OPEN_HOUR              = 6
    CLOSE_HOUR             = 23


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}