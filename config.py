import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ── Security ──
    SECRET_KEY = os.environ.get('SECRET_KEY', 'z-padel-secret-change-in-production')
    WTF_CSRF_ENABLED    = True
    WTF_CSRF_TIME_LIMIT = 7200   # 2-hour token expiry

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
    CLIPS_FOLDER         = os.path.join(BASE_DIR, 'clips')
    MAX_CONTENT_LENGTH   = 4 * 1024 * 1024   # 4 MB
    ALLOWED_EXTENSIONS   = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

    # ── NVR / Camera ── (set these in .env — no fallback defaults)
    NVR_URL  = os.environ.get('NVR_URL')
    NVR_USER = os.environ.get('NVR_USER')
    NVR_PASS = os.environ.get('NVR_PASS')

    # ── Web Push (VAPID) ──
    VAPID_PUBLIC_KEY  = 'BK0DMCR_lBGcOFj16EA4B3K55YrHapRJMBlY3aA1u2UL2iJikmxAMLWJ85v6rmNF4oSKQ8WFgOhDGEcax4RqPds'
    VAPID_PRIVATE_PEM = os.path.join(BASE_DIR, 'vapid_private.pem')
    VAPID_CLAIMS_EMAIL = os.environ.get('VAPID_EMAIL', 'admin@z-padel.com')

    # ── Business defaults (overridden by DB settings) ──
    DEFAULT_PRICE_PER_HOUR = 25_000   # IQD
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