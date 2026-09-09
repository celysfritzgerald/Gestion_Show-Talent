from flask import Blueprint, render_template, abort, session, flash, redirect, url_for, current_app
from app import db
from app.models import User, Artist, Score, Comment, CompetitionSession, Criterion
from app.permissions import artist_required

artist_bp = Blueprint('artist', __name__, url_prefix='/artist')

@artist_bp.route('/')
@artist_required
def dashboard():
    """Dashboard artiste - Notes, classement, commentaires"""
    try:
        # Vérifier l'utilisateur
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_artist():
            flash('Accès non autorisé.', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active_account():
            flash('Votre compte est désactivé.', 'danger')
            session.clear()
            return redirect(url_for('auth.login'))
        
        artist = user.artist_profile
        if not artist:
            flash('Profil artiste introuvable.', 'danger')
            return redirect(url_for('auth.login'))
        
        # === 1. RÉCUPÉRER LES NOTES DE L'ARTISTE ===
        sessions = CompetitionSession.query.order_by(CompetitionSession.number).all()
        session_scores = {}
        
        for session_obj in sessions:
            scores = Score.query.filter_by(
                artist_id=artist.id,
                session_id=session_obj.id
            ).all()
            
            if scores:
                total = sum(s.score for s in scores)
                session_scores[session_obj.number] = {
                    'total': round(total, 1),
                    'scores': scores,
                    'max_score': 100,
                    'complete': len(scores) == 10,
                    'session_id': session_obj.id
                }
        
        # === 2. RÉCUPÉRER LES COMMENTAIRES REÇUS ===
        comments = Comment.query.filter_by(
            artist_id=artist.id
        ).order_by(Comment.created_at.desc()).all()
        
        # === 3. RÉCUPÉRER LE CLASSEMENT GÉNÉRAL ===
        ranking = []
        all_artists = Artist.query.filter_by(competition_status='ACTIVE').all()
        
        for other_artist in all_artists:
            total_points = 0
            total_possible = 0
            for session_obj in sessions:
                scores = Score.query.filter_by(
                    artist_id=other_artist.id,
                    session_id=session_obj.id
                ).all()
                if scores and len(scores) == 10:
                    total_points += sum(s.score for s in scores)
                    total_possible += 100
            
            if total_points > 0:
                ranking.append({
                    'artist': other_artist,
                    'total': round(total_points, 1),
                    'max_possible': total_possible if total_possible > 0 else 100,
                    'rank': 0
                })
        
        # Trier et attribuer les rangs
        ranking.sort(key=lambda x: x['total'], reverse=True)
        for i, item in enumerate(ranking):
            item['rank'] = i + 1
        
        # Trouver le rang de l'artiste connecté
        artist_rank = None
        for item in ranking:
            if item['artist'].id == artist.id:
                artist_rank = item['rank']
                break
        
        return render_template('artist/dashboard.html',
                             artist=artist,
                             sessions=sessions,
                             session_scores=session_scores,
                             comments=comments,
                             ranking=ranking,
                             artist_rank=artist_rank)
                             
    except Exception as e:
        current_app.logger.error(f"Erreur dashboard artiste: {str(e)}")
        flash('Erreur lors du chargement du dashboard.', 'danger')
        return redirect(url_for('auth.login'))

@artist_bp.route('/scores/<int:session_id>')
@artist_required
def scores_detail(session_id):
    """Détail des notes par dimanche"""
    try:
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_artist():
            flash('Accès non autorisé.', 'danger')
            return redirect(url_for('auth.login'))
        
        artist = user.artist_profile
        if not artist:
            flash('Profil artiste introuvable.', 'danger')
            return redirect(url_for('auth.login'))
        
        session_obj = CompetitionSession.query.get_or_404(session_id)
        
        # Récupérer les notes avec les critères
        scores = Score.query.filter_by(
            artist_id=artist.id,
            session_id=session_id
        ).join(Criterion).order_by(Criterion.id).all()
        
        total = sum(s.score for s in scores) if scores else 0
        complete = len(scores) == 10
        
        # Récupérer les commentaires pour ce dimanche
        comments = Comment.query.filter_by(
            artist_id=artist.id,
            session_id=session_id
        ).all()
        
        return render_template('artist/scores_detail.html',
                             artist=artist,
                             session=session_obj,
                             scores=scores,
                             total=round(total, 1),
                             max_score=100,
                             complete=complete,
                             comments=comments)
                             
    except Exception as e:
        current_app.logger.error(f"Erreur affichage notes: {str(e)}")
        flash('Erreur lors du chargement des notes.', 'danger')
        return redirect(url_for('artist.dashboard'))

@artist_bp.route('/ranking')
@artist_required
def ranking():
    """Classement général de tous les artistes"""
    try:
        user = User.query.get(session['user_id'])
        artist = user.artist_profile
        
        sessions = CompetitionSession.query.order_by(CompetitionSession.number).all()
        
        ranking = []
        all_artists = Artist.query.filter_by(competition_status='ACTIVE').all()
        
        for other_artist in all_artists:
            total_points = 0
            total_possible = 0
            sessions_completed = 0
            for session_obj in sessions:
                scores = Score.query.filter_by(
                    artist_id=other_artist.id,
                    session_id=session_obj.id
                ).all()
                if scores and len(scores) == 10:
                    total_points += sum(s.score for s in scores)
                    total_possible += 100
                    sessions_completed += 1
            
            if total_points > 0:
                ranking.append({
                    'artist': other_artist,
                    'total': round(total_points, 1),
                    'max_possible': total_possible if total_possible > 0 else 100,
                    'percentage': round((total_points / total_possible) * 100, 1) if total_possible > 0 else 0,
                    'rank': 0,
                    'sessions_completed': sessions_completed
                })
        
        # Trier et attribuer les rangs
        ranking.sort(key=lambda x: x['total'], reverse=True)
        for i, item in enumerate(ranking):
            item['rank'] = i + 1
        
        return render_template('artist/ranking.html',
                             artist=artist,
                             ranking=ranking)
                             
    except Exception as e:
        current_app.logger.error(f"Erreur classement: {str(e)}")
        flash('Erreur lors du chargement du classement.', 'danger')
        return redirect(url_for('artist.dashboard'))