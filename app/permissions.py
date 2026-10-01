from functools import wraps
from flask import session, flash, redirect, url_for, abort, request, current_app
from app import db
from app.models import User, Artist, Assignment, CompetitionSession, Criterion
import time
from collections import defaultdict

_rate_limits = defaultdict(list)
_MAX_RATE_KEYS = 10000


# ═══════════════════════════════════════════════════════════
# HELPERS DE RÔLE
# ═══════════════════════════════════════════════════════════

def _get_current_user():
    """Retourne l'utilisateur connecté ou None."""
    if 'user_id' not in session:
        return None
    return db.session.get(User, session['user_id'])


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = _get_current_user()
        if not user:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))

        if not user.is_admin():
            abort(403)

        if not user.is_active_account():
            flash('Votre compte est désactivé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        if user.is_locked():
            session.clear()
            flash('Votre compte est verrouillé.', 'danger')
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function


def jury_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = _get_current_user()
        if not user:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))

        if not user.is_jury():
            abort(403)

        if not user.is_active_account():
            flash('Votre compte est désactivé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        if user.is_locked():
            flash('Votre compte est verrouillé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function


def artist_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = _get_current_user()
        if not user:
            session.clear()
            flash('Session invalide. Veuillez vous reconnecter.', 'warning')
            return redirect(url_for('auth.login'))

        if not user.is_artist():
            flash('Accès non autorisé. Cette page est réservée aux artistes.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active_account():
            flash('Votre compte est désactivé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        if user.is_locked():
            flash('Votre compte est verrouillé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        if not user.artist_profile:
            flash('Profil artiste introuvable.', 'danger')
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function


# ═══════════════════════════════════════════════════════════
# OBSERVER — RÔLE + PERMISSIONS GRANULAIRES
# ═══════════════════════════════════════════════════════════

def observer_required(f):
    """Accès réservé au rôle 'observer' avec compte actif."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = _get_current_user()
        if not user:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))

        if not user.is_observer():
            abort(403)

        if not user.is_active_account():
            flash('Votre compte observateur est désactivé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        if user.is_locked():
            flash('Votre compte est verrouillé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))

        # Vérifier qu'il a bien des permissions configurées
        if not user.observer_permission:
            current_app.logger.warning(
                f"[OBSERVER] user_id={user.id} n'a aucune permission configurée"
            )
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


def observer_has(section: str):
    """
    Décorateur : vérifie que l'observateur a accès à une section.

    Usage :
        @observer_bp.route('/finance')
        @observer_required
        @observer_has('finance')
        def finance(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = _get_current_user()
            if not user or not user.is_observer():
                abort(403)

            if not user.is_active_account() or user.is_locked():
                session.clear()
                flash('Compte indisponible.', 'danger')
                return redirect(url_for('auth.login'))

            perm = user.observer_permission
            if not perm or not perm.has(section):
                current_app.logger.warning(
                    f"[OBSERVER] Accès refusé section='{section}' "
                    f"user_id={user.id} username={user.username}"
                )
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_observer_sections():
    """
    Helper : retourne la liste des sections accessibles pour
    l'observateur connecté (pour la sidebar).
    """
    user = _get_current_user()
    if not user or not user.is_observer() or not user.observer_permission:
        return []
    return user.observer_permission.enabled_sections()


# ═══════════════════════════════════════════════════════════
# RATE LIMITING
# ═══════════════════════════════════════════════════════════

def rate_limit(limit_per_minute=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_app.config.get('RATELIMIT_ENABLED', True):
                return f(*args, **kwargs)

            user_id = session.get('user_id', 'anonymous')
            route = request.endpoint
            key = f"{user_id}:{route}"

            now = time.time()
            minute_ago = now - 60

            _rate_limits[key] = [t for t in _rate_limits[key] if t > minute_ago]
            if len(_rate_limits) > _MAX_RATE_KEYS:
                oldest_key = next(iter(_rate_limits))
                _rate_limits.pop(oldest_key, None)

            if len(_rate_limits[key]) >= limit_per_minute:
                abort(429)

            _rate_limits[key].append(now)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ═══════════════════════════════════════════════════════════
# HELPERS JURY
# ═══════════════════════════════════════════════════════════

def can_evaluate_criterion(jury_id, session_id, criterion_id, artist_id):
    try:
        if not all(isinstance(value, int) and value > 0 for value in (jury_id, session_id, criterion_id, artist_id)):
            return False, "Données invalides"
        jury = db.session.get(User, jury_id)
        if not jury or not jury.is_jury():
            return False, "Jury invalide"

        if not jury.is_active_account():
            return False, "Compte jury désactivé"

        if jury.is_locked():
            return False, "Compte jury verrouillé"

        artist = db.session.get(Artist, artist_id)
        if not artist:
            return False, "Artiste inexistant"

        if artist.is_eliminated():
            return False, "Artiste éliminé"

        if not artist.user.is_active_account():
            return False, "Compte artiste désactivé"

        session_obj = db.session.get(CompetitionSession, session_id)
        if not session_obj:
            return False, "Session invalide"

        if session_obj.status != 'IN_PROGRESS':
            return False, "Cette session n'est pas ouverte à l'évaluation"

        assignment = Assignment.query.filter_by(
            session_id=session_id,
            criterion_id=criterion_id,
            evaluator_user_id=jury_id
        ).first()

        if not assignment:
            return False, "Vous n'êtes pas autorisé à noter ce critère"

        return True, "OK"

    except Exception as e:
        current_app.logger.error(f"Erreur dans can_evaluate_criterion: {str(e)}")
        return False, "Erreur interne"


def get_jury_sessions(jury_id):
    try:
        sessions = CompetitionSession.query.join(
            Assignment, CompetitionSession.id == Assignment.session_id
        ).filter(
            Assignment.evaluator_user_id == jury_id
        ).distinct().all()
        return sessions
    except Exception as e:
        current_app.logger.error(f"Erreur dans get_jury_sessions: {str(e)}")
        return []


def get_jury_criteria_for_session(jury_id, session_id):
    try:
        criteria = Criterion.query.join(
            Assignment, Criterion.id == Assignment.criterion_id
        ).filter(
            Assignment.session_id == session_id,
            Assignment.evaluator_user_id == jury_id
        ).all()
        return criteria
    except Exception as e:
        current_app.logger.error(f"Erreur dans get_jury_criteria_for_session: {str(e)}")
        return []