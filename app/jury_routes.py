from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, session, current_app
from datetime import datetime
import math
from app import db
from app.services_ranking import (
    compute_ranking,
    get_sessions_for_ranking,
    get_matrix_for_session,
    invalidate_ranking_cache,
)
from app.models import User, Artist, CompetitionSession, Assignment, Score, Comment, Criterion
from app.permissions import (
    jury_required,
    can_evaluate_criterion,
    get_jury_sessions,
    get_jury_criteria_for_session,
    rate_limit,
)

jury_bp = Blueprint('jury', __name__, url_prefix='/jury')


# ═══════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════

@jury_bp.route('/')
@jury_required
@rate_limit(limit_per_minute=60)
def dashboard():
    try:
        user_id = session['user_id']
        sessions = get_jury_sessions(user_id)
        return render_template(
            'jury/dashboard.html',
            sessions=sessions,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"Erreur dashboard jury: {str(e)}")
        current_app.logger.exception("Détail complet")
        flash('Erreur lors du chargement du dashboard.', 'danger')
        return redirect(url_for('auth.login'))


# ═══════════════════════════════════════════════════════════
# ÉVALUATION
# ═══════════════════════════════════════════════════════════

@jury_bp.route('/evaluate/<int:session_id>')
@jury_required
@rate_limit(limit_per_minute=60)
def evaluate(session_id):
    user_id = session['user_id']

    try:
        session_obj = CompetitionSession.query.get_or_404(session_id)
        if session_obj.status == 'COMPLETED':
            flash('Cette session est déjà terminée.', 'warning')
            return redirect(url_for('jury.dashboard'))

        criteria = get_jury_criteria_for_session(user_id, session_id)
        if not criteria:
            flash('Vous n\'avez pas de critères assignés pour ce dimanche.', 'warning')
            return redirect(url_for('jury.dashboard'))

        artists = Artist.query.filter_by(competition_status='ACTIVE').all()

        scores = {}
        for artist in artists:
            for criterion in criteria:
                score = Score.query.filter_by(
                    artist_id=artist.id,
                    session_id=session_id,
                    criterion_id=criterion.id,
                    evaluator_id=user_id
                ).first()
                if score:
                    scores[f"{artist.id}_{criterion.id}"] = round(score.score, 1)

        comments = {}
        for artist in artists:
            comment = Comment.query.filter_by(
                jury_id=user_id,
                artist_id=artist.id,
                session_id=session_id
            ).first()
            if comment:
                comments[str(artist.id)] = comment.comment

        return render_template('jury/evaluation.html',
                             session=session_obj,
                             criteria=criteria,
                             artists=artists,
                             scores=scores,
                             comments=comments,
                             now=datetime.utcnow())

    except Exception as e:
        current_app.logger.error(f"Erreur évaluation jury: {str(e)}")
        current_app.logger.exception("Détail")
        flash('Erreur lors du chargement de la page d\'évaluation.', 'danger')
        return redirect(url_for('jury.dashboard'))


# ═══════════════════════════════════════════════════════════
# API CRUD POUR LES NOTES (JURY)
# ═══════════════════════════════════════════════════════════

@jury_bp.route('/api/save-score', methods=['POST'])
@jury_required
@rate_limit(limit_per_minute=120)
def save_score():
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

        artist = Artist.query.get(artist_id)
        if not artist:
            return jsonify({'error': 'Artiste invalide'}), 404

        if artist.is_eliminated():
            return jsonify({'error': 'Artiste éliminé'}), 403

        if not CompetitionSession.query.get(session_id):
            return jsonify({'error': 'Session invalide'}), 404

        if not Criterion.query.get(criterion_id):
            return jsonify({'error': 'Critère invalide'}), 404

        can_evaluate, message = can_evaluate_criterion(user_id, session_id, criterion_id, artist_id)
        if not can_evaluate:
            return jsonify({'error': message}), 403

        score = Score.query.filter_by(
            artist_id=artist_id,
            session_id=session_id,
            criterion_id=criterion_id,
            evaluator_id=user_id
        ).first()

        if score:
            score.score = score_value
            score.updated_at = datetime.utcnow()
            message = 'Note mise à jour avec succès'
        else:
            score = Score(
                artist_id=artist_id,
                session_id=session_id,
                criterion_id=criterion_id,
                evaluator_id=user_id,
                score=score_value
            )
            db.session.add(score)
            message = 'Note ajoutée avec succès'

        db.session.commit()
        invalidate_ranking_cache()   # ✅ AJOUT
        return jsonify({'success': True, 'score': score_value, 'message': message})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sauvegarde note: {str(e)}")
        current_app.logger.exception('Erreur serveur jury')
        return jsonify({'error': 'Erreur serveur'}), 500


@jury_bp.route('/api/delete-score', methods=['POST'])
@jury_required
@rate_limit(limit_per_minute=60)
def delete_score():
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

        if not Artist.query.get(artist_id):
            return jsonify({'error': 'Artiste invalide'}), 404

        if not CompetitionSession.query.get(session_id):
            return jsonify({'error': 'Session invalide'}), 404

        if not Criterion.query.get(criterion_id):
            return jsonify({'error': 'Critère invalide'}), 404

        can_evaluate, message = can_evaluate_criterion(user_id, session_id, criterion_id, artist_id)
        if not can_evaluate:
            return jsonify({'error': message}), 403

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
        invalidate_ranking_cache()   # ✅ AJOUT
        return jsonify({'success': True, 'message': 'Note supprimée avec succès'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression note: {str(e)}")
        current_app.logger.exception('Erreur serveur jury')
        return jsonify({'error': 'Erreur serveur'}), 500


@jury_bp.route('/api/save-comment', methods=['POST'])
@jury_required
@rate_limit(limit_per_minute=60)
def save_comment():
    user_id = session['user_id']

    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({'error': 'Données JSON invalides'}), 400

        artist_id = data.get('artist_id')
        session_id = data.get('session_id')
        comment_text = data.get('comment')

        if not all([artist_id, session_id, comment_text is not None]):
            return jsonify({'error': 'Données invalides'}), 400

        artist = Artist.query.get(artist_id)
        if not artist or artist.is_eliminated():
            return jsonify({'error': 'Artiste invalide'}), 404

        if not CompetitionSession.query.get(session_id):
            return jsonify({'error': 'Session invalide'}), 404

        assignment = Assignment.query.filter_by(
            session_id=session_id,
            evaluator_user_id=user_id
        ).first()

        if not assignment:
            return jsonify({'error': 'Vous n\'êtes pas autorisé'}), 403

        if not isinstance(comment_text, str):
            return jsonify({'error': 'Commentaire invalide'}), 400
        comment_text = comment_text.strip()
        if not comment_text or len(comment_text) > 500:
            return jsonify({'error': 'Le commentaire doit contenir entre 1 et 500 caractères'}), 400

        comment = Comment.query.filter_by(
            jury_id=user_id,
            artist_id=artist_id,
            session_id=session_id
        ).first()

        if comment:
            comment.comment = comment_text
            comment.updated_at = datetime.utcnow()
        else:
            comment = Comment(
                jury_id=user_id,
                artist_id=artist_id,
                session_id=session_id,
                comment=comment_text
            )
            db.session.add(comment)

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sauvegarde commentaire: {str(e)}")
        current_app.logger.exception('Erreur serveur jury')
        return jsonify({'error': 'Erreur serveur'}), 500


# ═══════════════════════════════════════════════════════════
# NOTES DÉTAILLÉES (matrice artistes × critères × dimanche)
# ═══════════════════════════════════════════════════════════

@jury_bp.route('/scores')
@jury_required
@rate_limit(limit_per_minute=60)
def scores():
    """
    Vue matricielle : pour chaque dimanche assigné au jury,
    affiche toutes les notes (artistes × critères).
    """
    user_id = session['user_id']
    try:
        sessions = get_jury_sessions(user_id)

        if not sessions:
            return render_template(
                'jury/scores.html',
                sessions=[],
                current_session=None,
                matrix=None,
                now=datetime.utcnow(),
            )

        session_id = request.args.get('session_id', type=int)
        valid_ids = [s.id for s in sessions]
        if session_id is None or session_id not in valid_ids:
            session_id = sessions[0].id

        current_session = next(
            (s for s in sessions if s.id == session_id), None
        )

        matrix = get_matrix_for_session(current_session.id)

        return render_template(
            'jury/scores.html',
            sessions=sessions,
            current_session=current_session,
            matrix=matrix,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"Erreur jury.scores: {e}")
        current_app.logger.exception("Détail")
        flash('Erreur lors du chargement des notes.', 'danger')
        return redirect(url_for('jury.dashboard'))


# ═══════════════════════════════════════════════════════════
# CLASSEMENT
# ═══════════════════════════════════════════════════════════

@jury_bp.route('/ranking')
@jury_required
@rate_limit(limit_per_minute=60)
def ranking():
    """
    Classement global OU par session (tous jurys confondus).
    """
    try:
        session_id = request.args.get('session_id', type=int)
        include_eliminated = request.args.get('eliminated', '0') == '1'

        sessions = get_sessions_for_ranking()
        session_obj = None
        if session_id is not None:
            session_obj = CompetitionSession.query.get(session_id)

        entries = compute_ranking(
            session_id=session_obj.id if session_obj else None,
            include_eliminated=include_eliminated,
            include_details=False,
        )

        for i, e in enumerate(entries, start=1):
            e.rank = i

        return render_template(
            'jury/ranking.html',
            entries=entries,
            sessions=sessions,
            current_session=session_obj,
            include_eliminated=include_eliminated,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"Erreur jury.ranking: {e}")
        current_app.logger.exception("Détail")
        flash('Erreur lors du chargement du classement.', 'danger')
        return redirect(url_for('jury.dashboard'))