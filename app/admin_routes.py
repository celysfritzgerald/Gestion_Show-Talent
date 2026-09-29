from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, session, jsonify
import os
from datetime import datetime
import math
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func
from app import db
from app.models import User, Artist, CompetitionSession, Criterion, Assignment, Score, Comment, Sponsor, Moment, ContactMessage, Lyric
from app.permissions import admin_required, rate_limit
from app.utils import save_uploaded_file, delete_uploaded_file, validate_http_url

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ============================================================
# DASHBOARD
# ============================================================

@admin_bp.route('/')
@admin_required
def dashboard():
    """Dashboard administrateur"""
    try:
        total_artists = Artist.query.count()
        active_artists = Artist.query.filter_by(competition_status='ACTIVE').count()
        total_juries = User.query.filter_by(role='jury', account_status='ACTIVE').count()
        total_sessions = CompetitionSession.query.count()
        completed_sessions = CompetitionSession.query.filter_by(status='COMPLETED').count()
        total_criteria = Criterion.query.count()
        total_scores = Score.query.count()
        total_messages = ContactMessage.query.count()
        new_messages = ContactMessage.query.filter_by(status='NEW').count()
        total_sponsors = Sponsor.query.count()
        total_lyrics = Lyric.query.count()
        published_lyrics = Lyric.query.filter_by(is_published=True).count()

        now = datetime.now()

        return render_template('admin/dashboard.html',
                             total_artists=total_artists,
                             active_artists=active_artists,
                             total_juries=total_juries,
                             total_sessions=total_sessions,
                             completed_sessions=completed_sessions,
                             total_criteria=total_criteria,
                             total_scores=total_scores,
                             total_messages=total_messages,
                             new_messages=new_messages,
                             total_sponsors=total_sponsors,
                             total_lyrics=total_lyrics,
                             published_lyrics=published_lyrics,
                             now=now)
    except Exception as e:
        current_app.logger.error(f"Erreur dashboard admin: {str(e)}")
        flash('Erreur lors du chargement du dashboard.', 'danger')
        return render_template('admin/dashboard.html')


# ============================================================
# GESTION DES ARTISTES
# ============================================================

@admin_bp.route('/artists')
@admin_required
def artists():
    """Liste des artistes"""
    try:
        artists = Artist.query.join(User).order_by(User.last_name).all()
        return render_template('admin/artists.html', artists=artists)
    except Exception as e:
        current_app.logger.error(f"Erreur liste artistes: {str(e)}")
        flash('Erreur lors du chargement des artistes.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/artists/create', methods=['GET', 'POST'])
@admin_required
def create_artist():
    """Créer un artiste"""
    if request.method == 'POST':
        try:
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            code = request.form.get('code', '').strip().upper()
            address = request.form.get('address', '').strip()
            biography = request.form.get('biography', '').strip()

            if not all([first_name, last_name, email, username, password, code]):
                flash('Tous les champs marqués * sont requis.', 'danger')
                return render_template('admin/artist_form.html')
            if any(len(value) > limit for value, limit in [(first_name, 100), (last_name, 100), (email, 255), (username, 100), (code, 20), (address, 500), (biography, 5000)]):
                flash('Un ou plusieurs champs sont trop longs.', 'danger')
                return render_template('admin/artist_form.html')
            try:
                email = validate_email(email, check_deliverability=False).normalized
            except EmailNotValidError:
                flash('Email invalide.', 'danger')
                return render_template('admin/artist_form.html')

            if User.query.filter_by(email=email).first():
                flash('Cet email est déjà utilisé.', 'danger')
                return render_template('admin/artist_form.html')

            if User.query.filter_by(username=username).first():
                flash('Ce nom d\'utilisateur est déjà utilisé.', 'danger')
                return render_template('admin/artist_form.html')

            if Artist.query.filter_by(code=code).first():
                flash('Ce code artiste est déjà utilisé.', 'danger')
                return render_template('admin/artist_form.html')

            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                role='artist',
                account_status='ACTIVE'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            artist = Artist(
                user_id=user.id,
                code=code,
                address=address,
                biography=biography,
                competition_status='ACTIVE'
            )

            if 'photo' in request.files and request.files['photo'].filename:
                try:
                    photo_filename = save_uploaded_file(request.files['photo'], 'artists')
                    if photo_filename:
                        artist.photo = photo_filename
                except ValueError as e:
                    flash(f'Erreur photo: {str(e)}', 'danger')
                    db.session.rollback()
                    return render_template('admin/artist_form.html')

            db.session.add(artist)
            db.session.commit()

            flash(f'Artiste {user.full_name()} créé avec succès!', 'success')
            return redirect(url_for('admin.artists'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur création artiste: {str(e)}")
            flash('Une erreur interne est survenue.', 'danger')
            return render_template('admin/artist_form.html')

    return render_template('admin/artist_form.html')


@admin_bp.route('/artists/<int:artist_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_artist(artist_id):
    """Modifier un artiste"""
    artist = Artist.query.get_or_404(artist_id)

    if request.method == 'POST':
        try:
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            username = request.form.get('username', '').strip()
            code = request.form.get('code', '').strip().upper()
            address = request.form.get('address', '').strip()
            biography = request.form.get('biography', '').strip()
            if not all([first_name, last_name, email, username, code]):
                flash('Les champs obligatoires sont requis.', 'danger')
                return render_template('admin/artist_form.html', artist=artist)
            try:
                email = validate_email(email, check_deliverability=False).normalized
            except EmailNotValidError:
                flash('Email invalide.', 'danger')
                return render_template('admin/artist_form.html', artist=artist)
            if User.query.filter(User.email == email, User.id != artist.user_id).first() or User.query.filter(User.username == username, User.id != artist.user_id).first():
                flash("Email ou nom d'utilisateur déjà utilisé.", "danger")
                return render_template('admin/artist_form.html', artist=artist)
            if Artist.query.filter(Artist.code == code, Artist.id != artist.id).first():
                flash('Ce code artiste est déjà utilisé.', 'danger')
                return render_template('admin/artist_form.html', artist=artist)
            if any(len(value) > limit for value, limit in [(first_name, 100), (last_name, 100), (email, 255), (username, 100), (code, 20), (address, 500), (biography, 5000)]):
                flash('Un ou plusieurs champs sont trop longs.', 'danger')
                return render_template('admin/artist_form.html', artist=artist)
            artist.user.first_name = first_name
            artist.user.last_name = last_name
            artist.user.email = email
            artist.user.username = username

            artist.code = code
            artist.address = address
            artist.biography = biography

            if request.form.get('password', '').strip():
                if len(request.form['password'].strip()) < 8:
                    flash('Le mot de passe doit contenir au moins 8 caractères.', 'danger')
                    return render_template('admin/artist_form.html', artist=artist)
                artist.user.set_password(request.form['password'])

            if 'photo' in request.files and request.files['photo'].filename:
                try:
                    if artist.photo:
                        delete_uploaded_file(artist.photo, 'artists')

                    photo_filename = save_uploaded_file(request.files['photo'], 'artists')
                    if photo_filename:
                        artist.photo = photo_filename
                except ValueError as e:
                    flash(f'Erreur photo: {str(e)}', 'danger')
                    return render_template('admin/artist_form.html', artist=artist)

            db.session.commit()
            flash('Artiste mis à jour avec succès!', 'success')
            return redirect(url_for('admin.artists'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur modification artiste: {str(e)}")
            flash('Une erreur interne est survenue.', 'danger')

    return render_template('admin/artist_form.html', artist=artist)


@admin_bp.route('/artists/<int:artist_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_artist_account_status(artist_id):
    try:
        artist = Artist.query.get_or_404(artist_id)
        if artist.user.account_status == 'ACTIVE':
            artist.user.account_status = 'INACTIVE'
            flash(f'Compte de {artist.user.full_name()} désactivé.', 'info')
        else:
            artist.user.account_status = 'ACTIVE'
            flash(f'Compte de {artist.user.full_name()} activé.', 'success')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur toggle status artiste: {str(e)}")
        flash('Erreur lors de la modification du statut.', 'danger')
    return redirect(url_for('admin.artists'))


@admin_bp.route('/artists/<int:artist_id>/toggle-competition', methods=['POST'])
@admin_required
def toggle_artist_competition_status(artist_id):
    try:
        artist = Artist.query.get_or_404(artist_id)
        if artist.competition_status == 'ACTIVE':
            artist.competition_status = 'ELIMINATED'
            flash(f'{artist.code} - {artist.user.full_name()} éliminé de la compétition.', 'warning')
        else:
            artist.competition_status = 'ACTIVE'
            flash(f'{artist.code} - {artist.user.full_name()} réintégré dans la compétition.', 'success')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur toggle competition artiste: {str(e)}")
        flash('Erreur lors de la modification du statut.', 'danger')
    return redirect(url_for('admin.artists'))


# ============================================================
# GESTION DES JURYS
# ============================================================

@admin_bp.route('/juries')
@admin_required
def juries():
    try:
        juries = User.query.filter_by(role='jury').all()
        return render_template('admin/juries.html', juries=juries)
    except Exception as e:
        current_app.logger.error(f"Erreur liste jurys: {str(e)}")
        flash('Erreur lors du chargement des jurys.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/juries/create', methods=['GET', 'POST'])
@admin_required
def create_jury():
    if request.method == 'POST':
        try:
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()

            if not all([first_name, last_name, email, username, password]):
                flash('Tous les champs sont requis.', 'danger')
                return render_template('admin/jury_form.html')
            try:
                email = validate_email(email, check_deliverability=False).normalized
            except EmailNotValidError:
                flash('Email invalide.', 'danger')
                return render_template('admin/jury_form.html')
            if any(len(value) > limit for value, limit in [(first_name, 100), (last_name, 100), (email, 255), (username, 100)]):
                flash('Un ou plusieurs champs sont trop longs.', 'danger')
                return render_template('admin/jury_form.html')

            if User.query.filter_by(email=email).first():
                flash('Cet email est déjà utilisé.', 'danger')
                return render_template('admin/jury_form.html')

            if User.query.filter_by(username=username).first():
                flash('Ce nom d\'utilisateur est déjà utilisé.', 'danger')
                return render_template('admin/jury_form.html')

            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                role='jury',
                account_status='ACTIVE'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash(f'Jury {user.full_name()} créé avec succès!', 'success')
            return redirect(url_for('admin.juries'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur création jury: {str(e)}")
            flash('Une erreur interne est survenue.', 'danger')

    return render_template('admin/jury_form.html')


@admin_bp.route('/juries/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_jury_status(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.role != 'jury':
            abort(400)
        if user.account_status == 'ACTIVE':
            user.account_status = 'INACTIVE'
            flash(f'{user.full_name()} désactivé.', 'info')
        else:
            user.account_status = 'ACTIVE'
            flash(f'{user.full_name()} activé.', 'success')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur toggle status jury: {str(e)}")
        flash('Erreur lors de la modification du statut.', 'danger')
    return redirect(url_for('admin.juries'))


# ============================================================
# GESTION DES CRITÈRES
# ============================================================

@admin_bp.route('/criteria')
@admin_required
def criteria():
    try:
        criteria = Criterion.query.all()
        return render_template('admin/criteria.html', criteria=criteria)
    except Exception as e:
        current_app.logger.error(f"Erreur liste critères: {str(e)}")
        flash('Erreur lors du chargement des critères.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/criteria/create', methods=['POST'])
@admin_required
def create_criterion():
    try:
        name = request.form.get('name', '').strip()
        if not name:
            flash('Le nom du critère est requis.', 'danger')
            return redirect(url_for('admin.criteria'))
        if len(name) > 100 or len(request.form.get('description', '').strip()) > 5000:
            flash('Le nom ou la description est trop long.', 'danger')
            return redirect(url_for('admin.criteria'))
        if Criterion.query.count() >= 10:
            flash('La compétition doit conserver exactement 10 critères.', 'danger')
            return redirect(url_for('admin.criteria'))
        if Criterion.query.filter(func.lower(Criterion.name) == name.lower()).first():
            flash('Ce critère existe déjà.', 'danger')
            return redirect(url_for('admin.criteria'))

        criterion = Criterion(
            name=name,
            description=request.form.get('description', '').strip(),
            max_score=10
        )
        db.session.add(criterion)
        db.session.commit()
        flash('Critère créé avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur création critère: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.criteria'))


@admin_bp.route('/criteria/<int:criterion_id>/edit', methods=['POST'])
@admin_required
def edit_criterion(criterion_id):
    criterion = Criterion.query.get_or_404(criterion_id)
    try:
        name = request.form.get('name', '').strip()
        if not name:
            flash('Le nom du critère est requis.', 'danger')
            return redirect(url_for('admin.criteria'))
        criterion.name = name
        criterion.description = request.form.get('description', '').strip()
        db.session.commit()
        flash('Critère mis à jour avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur modification critère: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.criteria'))


@admin_bp.route('/criteria/<int:criterion_id>/delete', methods=['POST'])
@admin_required
def delete_criterion(criterion_id):
    criterion = Criterion.query.get_or_404(criterion_id)
    try:
        if Criterion.query.count() <= 10:
            flash('La compétition doit conserver exactement 10 critères.', 'danger')
            return redirect(url_for('admin.criteria'))
        if Assignment.query.filter_by(criterion_id=criterion_id).first():
            flash('Ce critère est utilisé dans des affectations et ne peut pas être supprimé.', 'danger')
            return redirect(url_for('admin.criteria'))

        if Score.query.filter_by(criterion_id=criterion_id).first():
            flash('Ce critère a déjà des notes et ne peut pas être supprimé.', 'danger')
            return redirect(url_for('admin.criteria'))

        db.session.delete(criterion)
        db.session.commit()
        flash('Critère supprimé avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression critère: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.criteria'))


@admin_bp.route('/criteria/<int:criterion_id>/force-delete', methods=['POST'])
@admin_required
def force_delete_criterion(criterion_id):
    """Supprimer un critère FORCÉMENT (supprime aussi les affectations et notes)"""
    criterion = Criterion.query.get_or_404(criterion_id)
    try:
        if Criterion.query.count() <= 10:
            flash('La compétition doit conserver exactement 10 critères.', 'danger')
            return redirect(url_for('admin.criteria'))
        assignments_count = Assignment.query.filter_by(criterion_id=criterion_id).count()
        scores_count = Score.query.filter_by(criterion_id=criterion_id).count()

        Assignment.query.filter_by(criterion_id=criterion_id).delete()
        Score.query.filter_by(criterion_id=criterion_id).delete()

        db.session.delete(criterion)
        db.session.commit()

        flash(f'Critère supprimé avec succès! ({assignments_count} affectations et {scores_count} notes supprimées)', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur force delete critère: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.criteria'))


# ============================================================
# GESTION DES DIMANCHES ET AFFECTATIONS (CRUD DIMANCHES)
# ============================================================

@admin_bp.route('/sundays')
@admin_required
def sundays():
    """READ: Affichage de la liste des dimanches et des données associées"""
    try:
        sessions = CompetitionSession.query.order_by(CompetitionSession.number).all()
        juries = User.query.filter_by(role='jury', account_status='ACTIVE').all()
        criteria = Criterion.query.all()
        artists = Artist.query.filter_by(competition_status='ACTIVE').all()

        admin_user = User.query.filter_by(role='admin').first()

        session_assignments = {}
        jury_assignments = {}
        jury_criteria_count = {}

        for session in sessions:
            assignments = Assignment.query.filter_by(session_id=session.id).all()
            session_assignments[session.id] = assignments

            for assignment in assignments:
                jury_id = assignment.evaluator_user_id
                if session.id not in jury_assignments:
                    jury_assignments[session.id] = {}
                if jury_id not in jury_assignments[session.id]:
                    jury_assignments[session.id][jury_id] = []
                jury_assignments[session.id][jury_id].append(assignment)

            jury_criteria_count[session.id] = {}
            for jury in juries:
                count = Assignment.query.filter_by(
                    session_id=session.id,
                    evaluator_user_id=jury.id
                ).count()
                jury_criteria_count[session.id][jury.id] = count

        return render_template('admin/sundays.html',
                             sessions=sessions,
                             juries=juries,
                             criteria=criteria,
                             artists=artists,
                             admin_user=admin_user,
                             session_assignments=session_assignments,
                             jury_assignments=jury_assignments,
                             jury_criteria_count=jury_criteria_count)
    except Exception as e:
        current_app.logger.error(f"Erreur gestion dimanches: {str(e)}")
        flash('Erreur lors du chargement de la page.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/sundays/create', methods=['POST'])
@admin_required
def create_sunday():
    """CREATE: Création d'un nouveau dimanche"""
    try:
        number = int(request.form.get('number', 0))
        date_str = request.form.get('date', '')

        if number < 1 or number > 6:
            flash('Le numéro de session doit être compris entre 1 et 6.', 'danger')
            return redirect(url_for('admin.sundays'))

        if not date_str:
            flash('La date est requise.', 'danger')
            return redirect(url_for('admin.sundays'))

        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if CompetitionSession.query.filter_by(number=number).first():
            flash(f'Le dimanche numéro {number} existe déjà.', 'danger')
            return redirect(url_for('admin.sundays'))

        session = CompetitionSession(
            number=number,
            date=date,
            status='PENDING'
        )
        db.session.add(session)
        db.session.commit()

        flash(f'Dimanche {number} créé avec succès!', 'success')
    except ValueError:
        flash('Format de date invalide.', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur création dimanche: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.sundays'))


@admin_bp.route('/sundays/<int:session_id>/edit', methods=['POST'])
@admin_required
def edit_sunday(session_id):
    """UPDATE: Modification des détails d'un dimanche (numéro et date)"""
    session_obj = CompetitionSession.query.get_or_404(session_id)
    try:
        number = request.form.get('number')
        date_str = request.form.get('date')

        if number:
            number = int(number)
            if number < 1 or number > 6:
                flash('Le numéro de session doit être compris entre 1 et 6.', 'danger')
                return redirect(url_for('admin.sundays'))
            existing = CompetitionSession.query.filter_by(number=number).first()
            if existing and existing.id != session_id:
                flash(f'Le dimanche numéro {number} existe déjà.', 'danger')
                return redirect(url_for('admin.sundays'))
            session_obj.number = number

        if date_str:
            session_obj.date = datetime.strptime(date_str, '%Y-%m-%d').date()

        db.session.commit()
        flash('Dimanche mis à jour avec succès!', 'success')
    except ValueError:
        flash('Format de données ou date invalide.', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur modification dimanche: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.sundays'))


@admin_bp.route('/sundays/<int:session_id>/delete', methods=['POST'])
@admin_required
def delete_sunday(session_id):
    """DELETE: Suppression d'un dimanche et de ses affectations/notes dépendantes"""
    session_obj = CompetitionSession.query.get_or_404(session_id)
    try:
        # Nettoyage des enregistrements associés
        Assignment.query.filter_by(session_id=session_id).delete()
        Score.query.filter_by(session_id=session_id).delete()
        Moment.query.filter_by(session_id=session_id).delete()

        db.session.delete(session_obj)
        db.session.commit()
        flash('Dimanche et ses données associées ont été supprimés avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression dimanche: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.sundays'))


@admin_bp.route('/sundays/<int:session_id>/assign', methods=['POST'])
@admin_required
def assign_criteria(session_id):
    try:
        jury_data = {}
        admin_criteria = []

        for key in request.form.keys():
            if key.startswith('jury_') and key.endswith('_criteria[]'):
                jury_id = key.replace('jury_', '').replace('_criteria[]', '')
                if jury_id.isdigit():
                    jury_id = int(jury_id)
                    values = request.form.getlist(key)
                    criteria_list = [int(v) for v in values if v and v.isdigit()]
                    if criteria_list:
                        jury_data[jury_id] = criteria_list

        admin_values = request.form.getlist('admin_criteria[]')
        admin_criteria = [int(v) for v in admin_values if v and v.isdigit()]

        admin_user_id = request.form.get('admin_user_id')
        if admin_user_id and admin_user_id.isdigit():
            admin_user_id = int(admin_user_id)
        session_obj = CompetitionSession.query.get_or_404(session_id)
        current_admin = db.session.get(User, session.get('user_id'))
        if not admin_user_id:
            admin_user_id = current_admin.id
        admin_user = User.query.filter_by(id=admin_user_id, role='admin', account_status='ACTIVE').first()
        if not admin_user:
            flash('Administrateur invalide.', 'danger')
            return redirect(url_for('admin.sundays'))

        all_criteria = []
        for jury_id, criteria_list in jury_data.items():
            all_criteria.extend(criteria_list)
        all_criteria.extend(admin_criteria)

        if len(all_criteria) != 10:
            flash('Une session doit avoir exactement 10 critères affectés.', 'danger')
            return redirect(url_for('admin.sundays'))

        if len(all_criteria) != len(set(all_criteria)):
            flash('Un même critère ne peut pas être attribué plusieurs fois.', 'danger')
            return redirect(url_for('admin.sundays'))

        for criterion_id in all_criteria:
            if not Criterion.query.get(criterion_id):
                flash(f'Critère ID {criterion_id} invalide.', 'danger')
                return redirect(url_for('admin.sundays'))

        for jury_id in jury_data.keys():
            if not User.query.filter_by(id=jury_id, role='jury', account_status='ACTIVE').first():
                flash(f'Jury ID {jury_id} invalide ou inactif.', 'danger')
                return redirect(url_for('admin.sundays'))

        Assignment.query.filter_by(session_id=session_id).delete()

        for jury_id, criteria_list in jury_data.items():
            for criterion_id in criteria_list:
                assignment = Assignment(
                    session_id=session_id,
                    criterion_id=criterion_id,
                    evaluator_user_id=jury_id
                )
                db.session.add(assignment)

        if admin_user_id:
            for criterion_id in admin_criteria:
                assignment = Assignment(
                    session_id=session_id,
                    criterion_id=criterion_id,
                    evaluator_user_id=admin_user_id
                )
                db.session.add(assignment)

        db.session.commit()
        flash('Affectations mises à jour avec succès!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur assignation critères: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')

    return redirect(url_for('admin.sundays'))


@admin_bp.route('/sundays/<int:session_id>/status', methods=['POST'])
@admin_required
def update_session_status(session_id):
    """UPDATE: Mise à jour du statut d'une session (PENDING, IN_PROGRESS, COMPLETED)"""
    try:
        session_obj = CompetitionSession.query.get_or_404(session_id)
        new_status = request.form.get('status', '')

        if new_status not in ['PENDING', 'IN_PROGRESS', 'COMPLETED']:
            flash('Statut invalide.', 'danger')
            return redirect(url_for('admin.sundays'))

        session_obj.status = new_status
        db.session.commit()
        flash('Statut mis à jour avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur mise à jour statut: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.sundays'))


# ============================================================
# GESTION DES AFFECTATIONS (CRUD AFFECTATIONS)
# ============================================================

@admin_bp.route('/assignments/<int:assignment_id>/delete', methods=['POST'])
@admin_required
def delete_assignment(assignment_id):
    """Supprimer une affectation spécifique"""
    try:
        assignment = Assignment.query.get_or_404(assignment_id)
        db.session.delete(assignment)
        db.session.commit()
        flash('Affectation supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression affectation: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')

    return redirect(url_for('admin.sundays'))


@admin_bp.route('/assignments/<int:assignment_id>/edit', methods=['POST'])
@admin_required
def edit_assignment(assignment_id):
    """Modifier une affectation (changer le critère ou le jury)"""
    try:
        assignment = Assignment.query.get_or_404(assignment_id)

        new_jury_id = request.form.get('jury_id')
        new_criterion_id = request.form.get('criterion_id')

        if new_criterion_id:
            existing = Assignment.query.filter_by(
                session_id=assignment.session_id,
                criterion_id=new_criterion_id
            ).first()
            if existing and existing.id != assignment_id:
                flash('Ce critère est déjà attribué à un autre évaluateur pour cette session.', 'danger')
                return redirect(url_for('admin.sundays'))

        if new_jury_id:
            jury = User.query.filter_by(id=new_jury_id, role='jury', account_status='ACTIVE').first()
            if not jury:
                flash('Jury invalide.', 'danger')
                return redirect(url_for('admin.sundays'))
            assignment.evaluator_user_id = new_jury_id

        if new_criterion_id:
            criterion = Criterion.query.get(new_criterion_id)
            if not criterion:
                flash('Critère invalide.', 'danger')
                return redirect(url_for('admin.sundays'))
            assignment.criterion_id = new_criterion_id

        db.session.commit()
        flash('Affectation modifiée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur modification affectation: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')

    return redirect(url_for('admin.sundays'))


# ============================================================
# GESTION DES SPONSORS
# ============================================================

@admin_bp.route('/sponsors')
@admin_required
def sponsors():
    try:
        sponsors = Sponsor.query.all()
        return render_template('admin/sponsors.html', sponsors=sponsors)
    except Exception as e:
        current_app.logger.error(f"Erreur liste sponsors: {str(e)}")
        flash('Erreur lors du chargement des sponsors.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/sponsors/create', methods=['POST'])
@admin_required
def create_sponsor():
    try:
        name = request.form.get('name', '').strip()
        website = request.form.get('website', '').strip()

        if not name:
            flash('Le nom du sponsor est requis.', 'danger')
            return redirect(url_for('admin.sponsors'))

        if len(name) > 200:
            flash('Nom du sponsor trop long.', 'danger')
            return redirect(url_for('admin.sponsors'))
        try:
            website = validate_http_url(website) if website else None
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('admin.sponsors'))

        if 'logo' not in request.files or not request.files['logo'].filename:
            flash('Un logo est requis.', 'danger')
            return redirect(url_for('admin.sponsors'))

        logo_filename = save_uploaded_file(request.files['logo'], 'sponsors')

        sponsor = Sponsor(
            name=name,
            logo=logo_filename,
            website=website if website else None
        )
        db.session.add(sponsor)
        db.session.commit()

        flash('Sponsor ajouté avec succès!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur création sponsor: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.sponsors'))


@admin_bp.route('/sponsors/<int:sponsor_id>/delete', methods=['POST'])
@admin_required
def delete_sponsor(sponsor_id):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    try:
        if sponsor.logo:
            delete_uploaded_file(sponsor.logo, 'sponsors')
        db.session.delete(sponsor)
        db.session.commit()
        flash('Sponsor supprimé avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression sponsor: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.sponsors'))


# ============================================================
# GESTION DES MOMENTS FORTS
# ============================================================

@admin_bp.route('/moments')
@admin_required
def moments():
    try:
        moments = Moment.query.order_by(Moment.created_at.desc()).all()
        sessions = CompetitionSession.query.all()
        return render_template('admin/moments.html', moments=moments, sessions=sessions)
    except Exception as e:
        current_app.logger.error(f"Erreur liste moments: {str(e)}")
        flash('Erreur lors du chargement des moments.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/moments/create', methods=['POST'])
@admin_required
def create_moment():
    try:
        caption = request.form.get('caption', '').strip()
        session_id = request.form.get('session_id')

        if 'image' not in request.files or not request.files['image'].filename:
            flash('Une image est requise.', 'danger')
            return redirect(url_for('admin.moments'))

        image_filename = save_uploaded_file(request.files['image'], 'moments')

        if len(caption) > 500:
            flash('La légende est trop longue.', 'danger')
            delete_uploaded_file(image_filename, 'moments')
            return redirect(url_for('admin.moments'))
        if session_id:
            try:
                session_id = int(session_id)
            except (TypeError, ValueError):
                delete_uploaded_file(image_filename, 'moments')
                flash('Dimanche invalide.', 'danger')
                return redirect(url_for('admin.moments'))
            if not CompetitionSession.query.get(session_id):
                delete_uploaded_file(image_filename, 'moments')
                flash('Dimanche invalide.', 'danger')
                return redirect(url_for('admin.moments'))
        moment = Moment(
            image=image_filename,
            caption=caption if caption else None,
            session_id=session_id if session_id else None
        )
        db.session.add(moment)
        db.session.commit()

        flash('Moment ajouté avec succès!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur création moment: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.moments'))


@admin_bp.route('/moments/<int:moment_id>/delete', methods=['POST'])
@admin_required
def delete_moment(moment_id):
    moment = Moment.query.get_or_404(moment_id)
    try:
        if moment.image:
            delete_uploaded_file(moment.image, 'moments')
        db.session.delete(moment)
        db.session.commit()
        flash('Moment supprimé avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression moment: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.moments'))


# ============================================================
# CRUD ADMIN POUR SES CRITÈRES
# ============================================================

@admin_bp.route('/admin-evaluate/<int:session_id>')
@admin_required
def admin_evaluate(session_id):
    user_id = session['user_id']

    try:
        session_obj = CompetitionSession.query.get_or_404(session_id)
        if session_obj.status == 'COMPLETED':
            flash('Cette session est déjà terminée.', 'warning')
            return redirect(url_for('admin.dashboard'))

        admin_criteria = Criterion.query.join(
            Assignment, Criterion.id == Assignment.criterion_id
        ).filter(
            Assignment.session_id == session_id,
            Assignment.evaluator_user_id == user_id
        ).all()

        if not admin_criteria:
            flash('Vous n\'avez pas de critères assignés pour ce dimanche.', 'warning')
            return redirect(url_for('admin.sundays'))

        artists = Artist.query.filter_by(competition_status='ACTIVE').all()

        scores = {}
        for artist in artists:
            for criterion in admin_criteria:
                score = Score.query.filter_by(
                    artist_id=artist.id,
                    session_id=session_id,
                    criterion_id=criterion.id,
                    evaluator_id=user_id
                ).first()
                if score:
                    scores[f"{artist.id}_{criterion.id}"] = round(score.score, 1)

        return render_template('admin/admin_evaluate.html',
                             session=session_obj,
                             criteria=admin_criteria,
                             artists=artists,
                             scores=scores)

    except Exception as e:
        current_app.logger.error(f"Erreur évaluation admin: {str(e)}")
        flash('Erreur lors du chargement de la page d\'évaluation.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/api/admin-save-score', methods=['POST'])
@admin_required
def admin_save_score():
    """API pour sauvegarder une note de l'administrateur"""
    user_id = session['user_id']

    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({'error': 'Données JSON invalides'}), 400

        artist_id = data.get('artist_id')
        session_id = data.get('session_id')
        criterion_id = data.get('criterion_id')
        score_value = data.get('score')

        if not all([artist_id, session_id, criterion_id, score_value is not None]):
            return jsonify({'error': 'Tous les champs sont requis'}), 400

        try:
            score_value = float(score_value)
            if not math.isfinite(score_value):
                raise ValueError
            score_value = round(score_value, 1)
            if score_value < 0 or score_value > 10:
                return jsonify({'error': 'La note doit être entre 0 et 10'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Note invalide'}), 400

        assignment = Assignment.query.filter_by(
            session_id=session_id,
            criterion_id=criterion_id,
            evaluator_user_id=user_id
        ).first()

        if not assignment:
            return jsonify({'error': 'Vous n\'êtes pas autorisé à noter ce critère'}), 403

        artist = Artist.query.get(artist_id)
        if not artist:
            return jsonify({'error': 'Artiste invalide'}), 404

        if artist.is_eliminated():
            return jsonify({'error': 'Artiste éliminé'}), 403

        session_obj = CompetitionSession.query.get(session_id)
        if not session_obj:
            return jsonify({'error': 'Session invalide'}), 404

        if session_obj.status != 'IN_PROGRESS':
            return jsonify({"error": "Cette session n'est pas ouverte à l'évaluation"}), 403

        existing_score = Score.query.filter_by(
            artist_id=artist_id,
            session_id=session_id,
            criterion_id=criterion_id,
            evaluator_id=user_id
        ).first()

        if existing_score:
            existing_score.score = score_value
            existing_score.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'score': score_value,
                'message': 'Note mise à jour avec succès'
            })
        else:
            new_score = Score(
                artist_id=artist_id,
                session_id=session_id,
                criterion_id=criterion_id,
                evaluator_id=user_id,
                score=score_value,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(new_score)
            db.session.commit()
            return jsonify({
                'success': True,
                'score': score_value,
                'message': 'Note ajoutée avec succès'
            })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sauvegarde note admin: {str(e)}")
        current_app.logger.exception('Erreur API admin')
        return jsonify({'error': 'Erreur serveur', 'success': False}), 500


@admin_bp.route('/api/admin-delete-score', methods=['POST'])
@admin_required
def admin_delete_score():
    """API pour supprimer une note de l'administrateur"""
    user_id = session['user_id']

    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({'error': 'Données JSON invalides'}), 400

        artist_id = data.get('artist_id')
        session_id = data.get('session_id')
        criterion_id = data.get('criterion_id')

        if not all([artist_id, session_id, criterion_id]):
            return jsonify({'error': 'Tous les champs sont requis'}), 400

        assignment = Assignment.query.filter_by(
            session_id=session_id,
            criterion_id=criterion_id,
            evaluator_user_id=user_id
        ).first()

        if not assignment:
            return jsonify({'error': 'Vous n\'êtes pas autorisé'}), 403

        score = Score.query.filter_by(
            artist_id=artist_id,
            session_id=session_id,
            criterion_id=criterion_id,
            evaluator_id=user_id
        ).first()

        if not score:
            return jsonify({'error': 'Note non trouvée'}), 404

        db.session.delete(score)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Note supprimée avec succès'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression note admin: {str(e)}")
        current_app.logger.exception('Erreur API admin')
        return jsonify({'error': 'Erreur serveur', 'success': False}), 500


# ============================================================
# GESTION DES MESSAGES DE CONTACT
# ============================================================

@admin_bp.route('/messages')
@admin_required
def messages():
    """Liste des messages de contact"""
    try:
        messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
        return render_template('admin/messages.html', messages=messages)
    except Exception as e:
        current_app.logger.error(f"Erreur liste messages: {str(e)}")
        flash('Erreur lors du chargement des messages.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/messages/<int:message_id>/mark-read', methods=['POST'])
@admin_required
def mark_message_read(message_id):
    """Marquer un message comme lu"""
    try:
        message = ContactMessage.query.get_or_404(message_id)
        message.status = 'READ'
        db.session.commit()
        flash('Message marqué comme lu.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors du marquage du message.', 'danger')
    return redirect(url_for('admin.messages'))


@admin_bp.route('/messages/<int:message_id>/delete', methods=['POST'])
@admin_required
def delete_message(message_id):
    """Supprimer un message"""
    try:
        message = ContactMessage.query.get_or_404(message_id)
        db.session.delete(message)
        db.session.commit()
        flash('Message supprimé avec succès.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la suppression du message.', 'danger')
    return redirect(url_for('admin.messages'))


# ============================================================
# GESTION DES PAROLES (LYRICS) — MODULE INDÉPENDANT
# ============================================================

@admin_bp.route('/lyrics')
@admin_required
def lyrics():
    """Liste des paroles"""
    try:
        lyrics_list = Lyric.query.order_by(Lyric.created_at.desc()).all()
        return render_template('admin/lyrics.html', lyrics=lyrics_list)
    except Exception as e:
        current_app.logger.error(f"Erreur liste lyrics: {str(e)}")
        flash('Erreur lors du chargement des paroles.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/lyrics/create', methods=['POST'])
@admin_required
def create_lyric():
    """Créer une nouvelle parole avec artiste saisi manuellement"""
    try:
        artist_name = request.form.get('artist_name', '').strip()
        artist_code = request.form.get('artist_code', '').strip().upper()
        song_title = request.form.get('song_title', '').strip()
        content = request.form.get('content', '').strip()
        is_published = request.form.get('is_published') == 'on'

        if not all([artist_name, artist_code, song_title, content]):
            flash('Le nom, le code, le titre et les paroles sont requis.', 'danger')
            return redirect(url_for('admin.lyrics'))

        if len(artist_name) > 150 or len(artist_code) > 20 or len(song_title) > 200 or len(content) > 5000:
            flash('Un ou plusieurs champs sont trop longs.', 'danger')
            return redirect(url_for('admin.lyrics'))

        artist_photo = None
        if 'artist_photo' in request.files and request.files['artist_photo'].filename:
            try:
                artist_photo = save_uploaded_file(request.files['artist_photo'], 'lyrics')
            except ValueError as e:
                flash(f'Erreur photo: {str(e)}', 'danger')
                return redirect(url_for('admin.lyrics'))

        lyric = Lyric(
            artist_name=artist_name,
            artist_code=artist_code,
            artist_photo=artist_photo,
            song_title=song_title,
            content=content,
            is_published=is_published
        )
        db.session.add(lyric)
        db.session.commit()

        flash(f'Paroles "{song_title}" ajoutées avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur création lyric: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.lyrics'))


@admin_bp.route('/lyrics/<int:lyric_id>/edit', methods=['POST'])
@admin_required
def edit_lyric(lyric_id):
    """Modifier une parole"""
    lyric = Lyric.query.get_or_404(lyric_id)
    try:
        artist_name = request.form.get('artist_name', '').strip()
        artist_code = request.form.get('artist_code', '').strip().upper()
        song_title = request.form.get('song_title', '').strip()
        content = request.form.get('content', '').strip()
        is_published = request.form.get('is_published') == 'on'

        if not all([artist_name, artist_code, song_title, content]):
            flash('Tous les champs obligatoires sont requis.', 'danger')
            return redirect(url_for('admin.lyrics'))

        if len(artist_name) > 150 or len(artist_code) > 20 or len(song_title) > 200 or len(content) > 5000:
            flash('Un ou plusieurs champs sont trop longs.', 'danger')
            return redirect(url_for('admin.lyrics'))

        lyric.artist_name = artist_name
        lyric.artist_code = artist_code
        lyric.song_title = song_title
        lyric.content = content
        lyric.is_published = is_published

        if 'artist_photo' in request.files and request.files['artist_photo'].filename:
            try:
                if lyric.artist_photo:
                    delete_uploaded_file(lyric.artist_photo, 'lyrics')
                new_photo = save_uploaded_file(request.files['artist_photo'], 'lyrics')
                if new_photo:
                    lyric.artist_photo = new_photo
            except ValueError as e:
                flash(f'Erreur photo: {str(e)}', 'danger')
                return redirect(url_for('admin.lyrics'))

        db.session.commit()
        flash('Paroles mises à jour avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur modification lyric: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.lyrics'))


@admin_bp.route('/lyrics/<int:lyric_id>/delete', methods=['POST'])
@admin_required
def delete_lyric(lyric_id):
    """Supprimer une parole"""
    lyric = Lyric.query.get_or_404(lyric_id)
    try:
        if lyric.artist_photo:
            delete_uploaded_file(lyric.artist_photo, 'lyrics')
        db.session.delete(lyric)
        db.session.commit()
        flash('Paroles supprimées avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression lyric: {str(e)}")
        flash('Une erreur interne est survenue.', 'danger')
    return redirect(url_for('admin.lyrics'))


@admin_bp.route('/lyrics/<int:lyric_id>/toggle-publish', methods=['POST'])
@admin_required
def toggle_lyric_publish(lyric_id):
    """Publier/Dépublier une parole"""
    lyric = Lyric.query.get_or_404(lyric_id)
    try:
        lyric.is_published = not lyric.is_published
        db.session.commit()
        status = "publiée" if lyric.is_published else "dépubliée"
        flash(f'Parole {status} avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors du changement de statut.', 'danger')
    return redirect(url_for('admin.lyrics'))