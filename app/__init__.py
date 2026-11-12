import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, send_from_directory, request, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')

    if config_name not in config:
        raise RuntimeError(f"Configuration inconnue: {config_name}")
    app.config.from_object(config[config_name])
    if config_name == 'production':
        config['production'].validate()

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # ─── Logging ───
    _setup_logging(app, config_name)

    # ─── Extensions ───
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # ─── Sécurité WAF ───
    from app.security import init_security
    init_security(app)

    # ─── Route uploads ───
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        return send_from_directory(upload_folder, filename)

    # ─── Blueprints ───
    from app.routes import main_bp
    from app.auth import auth_bp
    from app.admin_routes import admin_bp
    from app.jury_routes import jury_bp
    from app.artist_routes import artist_bp
    from app.observer_routes import observer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(jury_bp, url_prefix='/jury')
    app.register_blueprint(artist_bp, url_prefix='/artist')
    app.register_blueprint(observer_bp, url_prefix='/observer')

    create_upload_directories(app)
    register_error_handlers(app)

    # ─── Filtres Jinja2 ───
    @app.template_filter('upload_url')
    def upload_url_filter(filename, subfolder='artists'):
        if not filename:
            return ''
        return f"/uploads/{subfolder}/{filename}"

    @app.template_filter('static_upload_url')
    def static_upload_url_filter(filename, subfolder='artists'):
        if not filename:
            return ''
        return f"/static/uploads/{subfolder}/{filename}"

    # ─── Context processor ───
    @app.context_processor
    def utility_processor():
        def get_upload_url(filename, subfolder='artists'):
            if not filename:
                return ''
            return f"/uploads/{subfolder}/{filename}"

        def get_static_upload_url(filename, subfolder='artists'):
            if not filename:
                return ''
            return f"/static/uploads/{subfolder}/{filename}"

        return dict(
            get_upload_url=get_upload_url,
            get_static_upload_url=get_static_upload_url,
            now=datetime.utcnow(),
        )

        # ═══════════════════════════════════════════════════════════
    # MIDDLEWARE : ANALYTICS (Style Google Analytics)
    # ═══════════════════════════════════════════════════════════
    @app.before_request
    def track_visitor():
        # Ignorer les fichiers statiques, API et requêtes non-GET
        if (request.path.startswith('/static') or 
            request.path.startswith('/uploads') or 
            request.path.startswith('/api/') or
            request.method != 'GET'):
            return

        try:
            from app.models import VisitorLog
            import hashlib
            import re
            from datetime import datetime, timedelta
            
            # 1. IDENTIFICATION DU VISITEUR (Empreinte IP + Navigateur)
            ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
            ua_string = request.headers.get('User-Agent', '')
            secret = current_app.config.get('SECRET_KEY', 'fallback')
            
            raw_visitor = f"{ip}|{ua_string}|{secret}"
            visitor_id = hashlib.sha256(raw_visitor.encode()).hexdigest()[:32]

            # 2. GESTION DE LA SESSION (Expire après 30 min d'inactivité)
            now = datetime.utcnow()
            # On crée un ID de session basé sur le visiteur et la tranche de 30 minutes
            time_block = int(now.timestamp() // 1800) # 1800 sec = 30 min
            raw_session = f"{visitor_id}|{time_block}"
            session_id = hashlib.sha256(raw_session.encode()).hexdigest()[:32]

            # 3. DÉTECTION APPAREIL / OS / BROWSER
            device = 'Desktop'
            os_name = 'Inconnu'
            browser = 'Inconnu'

            ua_lower = ua_string.lower()
            
            # Appareil
            if re.search(r'(mobi|android|iphone)', ua_lower): device = 'Mobile'
            if re.search(r'(ipad|tablet)', ua_lower): device = 'Tablet'

            # OS
            if 'windows' in ua_lower: os_name = 'Windows'
            elif 'mac os' in ua_lower: os_name = 'macOS'
            elif 'android' in ua_lower: os_name = 'Android'
            elif 'ios' in ua_lower or 'iphone' in ua_lower: os_name = 'iOS'
            elif 'linux' in ua_lower: os_name = 'Linux'

            # Browser
            if 'edg' in ua_lower: browser = 'Edge'
            elif 'chrome' in ua_lower and 'safari' in ua_lower: browser = 'Chrome'
            elif 'firefox' in ua_lower: browser = 'Firefox'
            elif 'safari' in ua_lower: browser = 'Safari'

            # 4. ENREGISTREMENT
            log = VisitorLog(
                visitor_id=visitor_id,
                session_id=session_id,
                ip_address=ip,
                user_agent=ua_string[:255],
                path=request.path,
                referrer=request.referrer[:255] if request.referrer else 'Direct',
                device_type=device,
                browser=browser,
                os=os_name
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            pass # On ignore silencieusement pour ne pas casser le site
    # ═══════════════════════════════════════════════════════════
    # HEADERS DE SÉCURITÉ + SEO
    # ═══════════════════════════════════════════════════════════
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        # ⚠️ CSP KORIJE (Espas ant 'unsafe-inline' ak 'unsafe-eval' ajoute)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://cdn.tailwindcss.com "
                "https://cdnjs.cloudflare.com "
                "https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' "
                "https://cdnjs.cloudflare.com "
                "https://fonts.googleapis.com "
                "https://cdn.tailwindcss.com; "
            "font-src 'self' data: "
                "https://cdnjs.cloudflare.com "
                "https://fonts.gstatic.com; "
            "img-src 'self' data: blob: "
                "https://images.unsplash.com "
                "https:; "
            "connect-src 'self' "
                "https://cdn.jsdelivr.net "
                "https://cdn.tailwindcss.com; "
            "media-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests"
        )

        if request.path.startswith(('/admin', '/jury', '/artist', '/observer', '/uploads')):
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow, noarchive")

        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains"
            )

        return response

    @app.after_request
    def add_cache_headers(response):
        path = request.path
        if path.startswith('/uploads/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif path in ('/sitemap.xml', '/robots.txt'):
            response.headers['Cache-Control'] = 'public, max-age=3600'
        elif path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=86400'
        elif path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store, must-revalidate'
        return response

    return app

def _setup_logging(app, config_name):
    if config_name == 'production':
        if not os.path.exists('logs'):
            os.makedirs('logs')
        file_handler = RotatingFileHandler('logs/showtalent.log', maxBytes=10 * 1024 * 1024, backupCount=10)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)

def create_upload_directories(app):
    upload_base = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    for subfolder in ['artists', 'moments', 'sponsors', 'lyrics', 'votes']:
        path = os.path.join(upload_base, subfolder)
        os.makedirs(path, exist_ok=True)
        gitkeep = os.path.join(path, '.gitkeep')
        if not os.path.exists(gitkeep):
            with open(gitkeep, 'w') as f:
                f.write('')
        try:
            os.chmod(path, 0o755)
        except OSError:
            pass

def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e): return render_template('errors/403.html'), 403
    @app.errorhandler(404)
    def not_found(e): return render_template('errors/404.html'), 404
    @app.errorhandler(429)
    def too_many_requests(e): return render_template('errors/404.html'), 429
    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        app.logger.exception('Erreur interne 500')
        return render_template('errors/500.html'), 500