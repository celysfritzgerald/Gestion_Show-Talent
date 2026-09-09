from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired
from app import db
from app.models import User
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

class LoginForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            if user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif user.is_jury():
                return redirect(url_for('jury.dashboard'))
            elif user.is_artist():
                if user.is_active_account():
                    return redirect(url_for('artist.dashboard'))
                else:
                    session.clear()
                    flash('Votre compte est désactivé.', 'danger')
            else:
                session.clear()
        else:
            session.clear()
    
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active_account():
                flash('Votre compte est désactivé. Veuillez contacter l\'administrateur.', 'danger')
                return render_template('auth/login.html', form=form)
            
            if user.is_locked():
                flash('Votre compte est verrouillé. Veuillez réessayer plus tard.', 'danger')
                return render_template('auth/login.html', form=form)
            
            user.login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            session.permanent = True
            session['user_id'] = user.id
            session['user_role'] = user.role
            session['user_name'] = user.full_name()
            
            flash(f'Bienvenue {user.full_name()}!', 'success')
            
            if user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif user.is_jury():
                return redirect(url_for('jury.dashboard'))
            elif user.is_artist():
                return redirect(url_for('artist.dashboard'))
            else:
                flash('Rôle inconnu.', 'danger')
                session.clear()
                return redirect(url_for('auth.login'))
        else:
            if user:
                user.login_attempts += 1
                if user.login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    flash('Trop de tentatives échouées. Compte verrouillé pour 15 minutes.', 'danger')
                else:
                    flash(f'Mot de passe incorrect. {5 - user.login_attempts} tentatives restantes.', 'danger')
                db.session.commit()
            else:
                flash('Nom d\'utilisateur ou mot de passe incorrect.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    user_name = session.get('user_name', 'Utilisateur')
    session.clear()
    flash(f'Au revoir {user_name}!', 'info')
    return redirect(url_for('auth.login'))