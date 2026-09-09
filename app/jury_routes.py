from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, session, current_app
from datetime import datetime
from app import db
from app.models import User, Artist, CompetitionSession, Assignment, Score, Comment, Criterion
from app.permissions import jury_required, can_evaluate_criterion, get_jury_sessions, get_jury_criteria_for_session, rate_limit

jury_bp = Blueprint('jury', __name__, url_prefix='/jury')

@jury_bp.route('/')
@jury_required
@rate_limit(limit_per_minute=60)
def dashboard():
    try:
        user_id = session['user_id']
        sessions = get_jury_sessions(user_id)
        return render_template('jury/dashboard.html', sessions=sessions)
    except Exception as e:
        current_app.logger.error(f"Erreur dashboard jury: {str(e)}")
        flash('Erreur lors du chargement du dashboard.', 'danger')
        return redirect(url_for('auth.login'))

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
                             comments=comments)
                             
    except Exception as e:
        current_app.logger.error(f"Erreur évaluation jury: {str(e)}")
        flash('Erreur lors du chargement de la page d\'évaluation.', 'danger')
        return redirect(url_for('jury.dashboard'))

# ============================================================
# API CRUD POUR LES NOTES (JURY)
# ============================================================

@jury_bp.route('/api/save-score', methods=['POST'])
@jury_required
@rate_limit(limit_per_minute=120)
def save_score():
    user_id = session['user_id']
    
    try:
        data = request.get_json()
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
        return jsonify({'success': True, 'score': score_value, 'message': message})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sauvegarde note: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@jury_bp.route('/api/delete-score', methods=['POST'])
@jury_required
@rate_limit(limit_per_minute=60)
def delete_score():
    user_id = session['user_id']
    
    try:
        data = request.get_json()
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
        return jsonify({'success': True, 'message': 'Note supprimée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression note: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@jury_bp.route('/api/save-comment', methods=['POST'])
@jury_required
@rate_limit(limit_per_minute=60)
def save_comment():
    user_id = session['user_id']
    
    try:
        data = request.get_json()
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
        
        if len(comment_text) > 500:
            comment_text = comment_text[:500]
        
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
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500