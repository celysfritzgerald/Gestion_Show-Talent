from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Length

from app import db
from app.models import User
from app.permissions import rate_limit

auth_bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(max=100)])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(max=128)])


# ═══════════════════════════════════════════════════════════
# HELPER : redirection selon rôle
# ═══════════════════════════════════════════════════════════

def _redirect_for_role(user):
    """Retourne la redirection appropriée selon le rôle."""
    if user.is_admin():    return redirect(url_for("admin.dashboard"))
    if user.is_jury():     return redirect(url_for("jury.dashboard"))
    if user.is_artist():   return redirect(url_for("artist.dashboard"))
    if user.is_observer(): return redirect(url_for("observer.dashboard"))
    return None


# ═══════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════

@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(limit_per_minute=10)
def login():
    # Si déjà connecté : rediriger selon rôle
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user and user.is_active_account() and not user.is_locked():
            target = _redirect_for_role(user)
            if target:
                return target
        session.clear()

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()

        # ⚠️ Anti-énumération : on vérifie tout, mais on retourne
        #    TOUJOURS le même message en cas d'échec.
        valid = bool(
            user
            and user.is_active_account()
            and not user.is_locked()
            and user.check_password(form.password.data)
        )

        if valid:
            user.login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            db.session.commit()

            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            session["user_role"] = user.role
            session["user_name"] = user.full_name()

            target = _redirect_for_role(user)
            if target:
                return target

            # Rôle inconnu : on coupe tout
            session.clear()
            flash("Rôle inconnu. Contactez l'administrateur.", "danger")
            return redirect(url_for("auth.login"))

        # ─── Échec : on incrémente le compteur si user existe ───
        if user:
            user.login_attempts = (user.login_attempts or 0) + 1
            if user.login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()

        # Message unique (anti-énumération)
        flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")

    return render_template("auth/login.html", form=form)


# ═══════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════

@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_name = session.get("user_name", "Utilisateur")
    session.clear()
    flash(f"Au revoir {user_name}!", "info")
    return redirect(url_for("auth.login"))