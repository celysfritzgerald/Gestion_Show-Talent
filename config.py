import os
from datetime import timedelta


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Configuration commune et sécurisée."""
    SECRET_KEY = os.environ.get("SECRET_KEY")
    CSRF_SECRET_KEY = os.environ.get("CSRF_SECRET_KEY")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
    MAX_IMAGE_DIMENSIONS = (4096, 4096)

    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    SESSION_COOKIE_NAME = "show_talent_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    RATELIMIT_ENABLED = _env_bool("RATELIMIT_ENABLED", True)
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me"
    CSRF_SECRET_KEY = os.environ.get("CSRF_SECRET_KEY") or "dev-only-csrf-change-me"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///show_talent_dev.db"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_SSL_STRICT = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }

    @classmethod
    def validate(cls):
        missing = [name for name in ("SECRET_KEY", "CSRF_SECRET_KEY", "DATABASE_URL") if not os.environ.get(name)]
        if missing:
            raise RuntimeError("Variables de production manquantes: " + ", ".join(missing))
        if not os.environ["DATABASE_URL"].startswith(("postgresql://", "postgres://")):
            raise RuntimeError("DATABASE_URL doit pointer vers PostgreSQL en production")


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    CSRF_SECRET_KEY = "test-csrf-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
