import os
from datetime import timedelta

class Config:
    """Configuration de base"""
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-1234567890abcdefghijklmnopqrstuvwxyz'
    CSRF_SECRET_KEY = os.environ.get('CSRF_SECRET_KEY') or 'dev-csrf-key-1234567890abcdefghijklmnopqrstuvwxyz'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_MIME_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}
    MAX_IMAGE_DIMENSIONS = (4096, 4096)
    
    # Sessions
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

class DevelopmentConfig(Config):
    """Développement - SQLite"""
    DEBUG = True
    # ✅ Valeur par défaut pour le développement
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///show_talent_dev.db'
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False}
    }

class ProductionConfig(Config):
    """Production - PostgreSQL"""
    DEBUG = False
    # ✅ En production, DATABASE_URL est OBLIGATOIRE
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        # ✅ Si pas de DATABASE_URL en prod, on utilise SQLite comme fallback
        # (utile pour le développement local en mode production)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///show_talent_prod.db'
        print("⚠️  ATTENTION: DATABASE_URL non définie, utilisation de SQLite en mode production!")
    
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    WTF_CSRF_SSL_STRICT = True
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

class TestingConfig(Config):
    """Test - SQLite en mémoire"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}