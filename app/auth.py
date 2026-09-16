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


@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(limit_per_minute=10)
def login():
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user and user.is_active_account() and not user.is_locked():
            if user.is_admin(): return redirect(url_for("admin.dashboard"))
            if user.is_jury(): return redirect(url_for("jury.dashboard"))
            if user.is_artist(): return redirect(url_for("artist.dashboard"))
        session.clear()

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        valid = bool(user and user.is_active_account() and not user.is_locked() and user.check_password(form.password.data))

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
            if user.is_admin(): return redirect(url_for("admin.dashboard"))
            if user.is_jury(): return redirect(url_for("jury.dashboard"))
            if user.is_artist(): return redirect(url_for("artist.dashboard"))
            session.clear()

        if user and user.is_locked():
            flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
        elif user and not user.is_active_account():
            flash("Votre compte est désactivé. Veuillez contacter l'administrateur.", "danger")
        else:
            if user:
                user.login_attempts += 1
                if user.login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                db.session.commit()
            flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_name = session.get("user_name", "Utilisateur")
    session.clear()
    flash(f"Au revoir {user_name}!", "info")
    return redirect(url_for("auth.login"))
