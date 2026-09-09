from functools import wraps
from flask import session, flash, redirect, url_for, abort, request, current_app
from app import db
from app.models import User, Artist, Assignment, CompetitionSession, Criterion
import time

_rate_limits = {}

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
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin():
            abort(403)
        
        if not user.is_active_account():
            flash('Votre compte est désactivé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

def jury_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_jury():
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
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        
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
            
            if key in _rate_limits:
                _rate_limits[key] = [t for t in _rate_limits[key] if t > minute_ago]
            else:
                _rate_limits[key] = []
            
            if len(_rate_limits[key]) >= limit_per_minute:
                abort(429)
            
            _rate_limits[key].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def can_evaluate_criterion(jury_id, session_id, criterion_id, artist_id):
    try:
        jury = User.query.get(jury_id)
        if not jury or not jury.is_jury():
            return False, "Jury invalide"
        
        if not jury.is_active_account():
            return False, "Compte jury désactivé"
        
        if jury.is_locked():
            return False, "Compte jury verrouillé"
        
        artist = Artist.query.get(artist_id)
        if not artist:
            return False, "Artiste inexistant"
        
        if artist.is_eliminated():
            return False, "Artiste éliminé"
        
        if not artist.user.is_active_account():
            return False, "Compte artiste désactivé"
        
        session_obj = CompetitionSession.query.get(session_id)
        if not session_obj:
            return False, "Session invalide"
        
        if session_obj.status == 'COMPLETED':
            return False, "Cette session est terminée"
        
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