import os
import logging
from flask import Flask, render_template, send_from_directory, request, jsonify
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

    # Railway/Reverse proxy: ne faire confiance qu'à un proxy direct.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # Initialiser les extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # ROUTE POUR SERVIR LES FICHIERS UPLOADÉS
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Servir les fichiers uploadés (artists, moments, sponsors)"""
        upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        return send_from_directory(upload_folder, filename)
    
    # Enregistrer les blueprints
    from app.routes import main_bp
    from app.auth import auth_bp
    from app.admin_routes import admin_bp
    from app.jury_routes import jury_bp
    from app.artist_routes import artist_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(jury_bp, url_prefix='/jury')
    app.register_blueprint(artist_bp, url_prefix='/artist')
    
    # Créer les dossiers d'upload
    create_upload_directories(app)
    
    # Gestionnaires d'erreurs
    register_error_handlers(app)
    
    # FILTRES JINJA2 POUR LES UPLOADS
    @app.template_filter('upload_url')
    def upload_url_filter(filename, subfolder='artists'):
        """Filtre Jinja2 pour générer l'URL d'une image uploadée"""
        if not filename:
            return ''
        return f"/uploads/{subfolder}/{filename}"
    
    @app.template_filter('static_upload_url')
    def static_upload_url_filter(filename, subfolder='artists'):
        """Filtre Jinja2 pour générer l'URL statique d'une image uploadée"""
        if not filename:
            return ''
        return f"/static/uploads/{subfolder}/{filename}"
    
    # CONTEXT PROCESSOR POUR LES UPLOADS
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
            get_static_upload_url=get_static_upload_url
        )
    
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    return app

def create_upload_directories(app):
    """Création sécurisée des dossiers d'upload"""
    upload_base = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    for subfolder in ['artists', 'moments', 'sponsors']:
        path = os.path.join(upload_base, subfolder)
        os.makedirs(path, exist_ok=True)
        # Créer un fichier .gitkeep pour garder le dossier
        gitkeep = os.path.join(path, '.gitkeep')
        if not os.path.exists(gitkeep):
            with open(gitkeep, 'w') as f:
                f.write('')
        # Donner les permissions
        try:
            os.chmod(path, 0o755)
        except OSError:
            pass  # Windows

def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/404.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        app.logger.exception('Erreur interne 500')
        return render_template('errors/500.html'), 500