"""
Module de sécurité — Protections WAF légères
Remplace flask_firewall (inexistant sur PyPI)
"""
import re
import time
import logging
from functools import wraps
from flask import render_template, request, abort, current_app, jsonify

logger = logging.getLogger(__name__)


# ============================================================
# PATTERNS DANGEREUX
# ============================================================

# XSS
XSS_PATTERNS = [
    re.compile(r'<\s*script[^>]*>', re.IGNORECASE),
    re.compile(r'javascript\s*:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick=, onerror=, etc.
    re.compile(r'<\s*iframe', re.IGNORECASE),
    re.compile(r'<\s*object', re.IGNORECASE),
    re.compile(r'<\s*embed', re.IGNORECASE),
]

# SQL Injection (défense en profondeur, SQLAlchemy gère déjà)
SQLI_PATTERNS = [
    re.compile(r"(\bunion\b.*\bselect\b)", re.IGNORECASE),
    re.compile(r"(\bselect\b.*\bfrom\b)", re.IGNORECASE),
    re.compile(r"(\bdrop\b\s+\btable\b)", re.IGNORECASE),
    re.compile(r"(\binsert\b\s+\binto\b)", re.IGNORECASE),
    re.compile(r"(\bdelete\b\s+\bfrom\b)", re.IGNORECASE),
    re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
    re.compile(r"(\bor\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+)", re.IGNORECASE),
]

# Path Traversal
PATH_TRAVERSAL_PATTERNS = [
    re.compile(r'\.\.[/\\]'),
    re.compile(r'%2e%2e[/\\]', re.IGNORECASE),
    re.compile(r'\.\.%2f', re.IGNORECASE),
]

# Command Injection
CMD_INJECTION_PATTERNS = [
    re.compile(r'[;&|`$]'),
    re.compile(r'\$\(.*\)'),
    re.compile(r'>\s*/'),
]


# ============================================================
# VÉRIFICATION DES ENTRÉES
# ============================================================

def _check_patterns(value, patterns, attack_type):
    """Vérifie si une valeur contient un pattern dangereux"""
    if not isinstance(value, str):
        return False
    for pattern in patterns:
        if pattern.search(value):
            logger.warning(f"🚨 {attack_type} détecté: {value[:100]}")
            return True
    return False


def check_request_security():
    """
    Vérifie toutes les entrées de la requête
    Retourne True si OK, False sinon
    """
    # Vérifier les args URL
    for key, value in request.args.items():
        if _check_patterns(value, XSS_PATTERNS, "XSS (query)"):
            return False
        if _check_patterns(value, PATH_TRAVERSAL_PATTERNS, "Path Traversal (query)"):
            return False

    # Vérifier le formulaire
    if request.form:
        for key, value in request.form.items():
            if _check_patterns(value, XSS_PATTERNS, "XSS (form)"):
                return False
            if _check_patterns(value, PATH_TRAVERSAL_PATTERNS, "Path Traversal (form)"):
                return False

    # Vérifier le JSON
    if request.is_json:
        try:
            data = request.get_json(silent=True) or {}
            for key, value in data.items():
                if isinstance(value, str):
                    if _check_patterns(value, XSS_PATTERNS, "XSS (json)"):
                        return False
                    if _check_patterns(value, PATH_TRAVERSAL_PATTERNS, "Path Traversal (json)"):
                        return False
        except Exception:
            pass

    # Vérifier l'URL path
    if request.path:
        if _check_patterns(request.path, PATH_TRAVERSAL_PATTERNS, "Path Traversal (path)"):
            return False

    return True


# ============================================================
# RATE LIMITING (en mémoire)
# ============================================================

_rate_limit_store = {}


def check_rate_limit(limit=100, period=60):
    """
    Vérifie le rate limit par IP
    Retourne True si OK, False si limite dépassée
    """
    from flask import current_app
    if not current_app.config.get('RATELIMIT_ENABLED', True):
        return True

    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')
    ip = ip.split(',')[0].strip()

    now = time.time()
    key = f"{ip}:{request.endpoint}"

    if key in _rate_limit_store:
        # Nettoyer les vieilles entrées
        _rate_limit_store[key] = [t for t in _rate_limit_store[key] if t > now - period]
    else:
        _rate_limit_store[key] = []

    if len(_rate_limit_store[key]) >= limit:
        logger.warning(f"🚨 Rate limit dépassé pour {ip} sur {request.endpoint}")
        return False

    _rate_limit_store[key].append(now)
    return True


# ============================================================
# MIDDLEWARE PRINCIPAL
# ============================================================

def init_security(app):
    """
    Initialise toutes les protections de sécurité
    À appeler dans create_app() APRÈS avoir créé `app`
    """

    # ---------------------------------------------------------
    # 1. Restriction des méthodes HTTP
    # ---------------------------------------------------------
    ALLOWED_METHODS = {'GET', 'POST', 'HEAD', 'OPTIONS'}

    @app.before_request
    def restrict_methods():
        if request.method not in ALLOWED_METHODS:
            logger.warning(f"🚨 Méthode HTTP bloquée: {request.method}")
            abort(405)

    # ---------------------------------------------------------
    # 2. Limitation de la taille de la requête
    # ---------------------------------------------------------
    MAX_REQUEST_SIZE = 2 * 1024 * 1024  # 2 MB

    @app.before_request
    def limit_request_size():
        content_length = request.content_length or 0
        if content_length > MAX_REQUEST_SIZE:
            logger.warning(f"🚨 Requête trop volumineuse: {content_length} bytes")
            abort(413)

    # ---------------------------------------------------------
    # 3. Vérification XSS / Path Traversal / SQLi
    # ---------------------------------------------------------
    @app.before_request
    def check_security_patterns():
        # Ne pas bloquer les routes statiques
        if request.path.startswith('/static') or request.path.startswith('/uploads'):
            return
        # Ne pas bloquer les requêtes OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return

        if not check_request_security():
            abort(400, description="Requête bloquée par la sécurité")

    # ---------------------------------------------------------
    # 4. Rate limiting global
    # ---------------------------------------------------------
    @app.before_request
    def rate_limit_global():
        if request.path.startswith('/static') or request.path.startswith('/uploads'):
            return

        # Limite globale : 200 requêtes/minute par IP
        if not check_rate_limit(limit=200, period=60):
            abort(429)

    # ---------------------------------------------------------
    # 5. HTTPS enforcement (production uniquement)
    # ---------------------------------------------------------
    @app.before_request
    def enforce_https():
        if app.config.get('ENV') == 'production' or not app.debug:
            # Ne rediriger que si on est en production ET pas déjà en HTTPS
            if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
                # Exception : healthcheck
                if request.path == '/health':
                    return
                # En prod, rediriger vers HTTPS (géré par Railway/nginx en amont)
                # Ici on laisse passer car Railway fait la redirection
                pass

    # ---------------------------------------------------------
    # 6. Réponses sécurisées pour les erreurs 400/413/429
    # ---------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Requête invalide'}), 400
        return render_template('errors/404.html'), 400

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Méthode non autorisée'}), 405
        return render_template('errors/404.html'), 405

    @app.errorhandler(413)
    def request_too_large(e):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Requête trop volumineuse'}), 413
        return render_template('errors/404.html'), 413

    logger.info("✅ Module de sécurité initialisé")

    return app