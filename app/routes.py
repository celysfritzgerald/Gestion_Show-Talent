from flask import Blueprint, render_template, request, jsonify, current_app
from app import db
from app.models import Artist, CompetitionSession, Sponsor, Moment, User, Score, Criterion, ContactMessage
from app.permissions import rate_limit
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@rate_limit(limit_per_minute=120)
def index():
    """Page d'accueil"""
    try:
        artists = Artist.query.join(User).filter(
            User.account_status == 'ACTIVE'
        ).limit(6).all()
        
        sponsors = Sponsor.query.all()
        
        moments = Moment.query.order_by(
            Moment.created_at.desc()
        ).limit(12).all()
        
        sessions = CompetitionSession.query.order_by(
            CompetitionSession.number
        ).all()
        
        return render_template('public/index.html',
                             artists=artists,
                             sponsors=sponsors,
                             moments=moments,
                             sessions=sessions)
    except Exception as e:
        current_app.logger.error(f"Erreur page accueil: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/about')
def about():
    """Page À propos"""
    return render_template('public/about.html')


@main_bp.route('/artists')
@rate_limit(limit_per_minute=60)
def artists():
    """Page des artistes"""
    try:
        artists = Artist.query.join(User).filter(
            User.account_status == 'ACTIVE'
        ).order_by(User.last_name).all()
        return render_template('public/artists.html', artists=artists)
    except Exception as e:
        current_app.logger.error(f"Erreur page artistes: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/results')
@rate_limit(limit_per_minute=60)
def results():
    """Page des résultats"""
    try:
        sessions = CompetitionSession.query.order_by(
            CompetitionSession.number
        ).all()
        return render_template('public/results.html', sessions=sessions)
    except Exception as e:
        current_app.logger.error(f"Erreur page résultats: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/sponsors')
@rate_limit(limit_per_minute=60)
def sponsors_page():
    """Page des sponsors"""
    try:
        sponsors = Sponsor.query.all()
        return render_template('public/sponsors.html', sponsors=sponsors)
    except Exception as e:
        current_app.logger.error(f"Erreur page sponsors: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/api/contact', methods=['POST'])
@rate_limit(limit_per_minute=30)
def contact():
    """API pour le formulaire de contact"""
    try:
        data = request.get_json()
        
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()
        
        if not all([first_name, last_name, email, message]):
            return jsonify({'success': False, 'message': 'Tous les champs sont requis.'}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'message': 'Email invalide.'}), 400
        
        if len(message) < 10:
            return jsonify({'success': False, 'message': 'Le message doit contenir au moins 10 caractères.'}), 400
        
        contact = ContactMessage(
            first_name=first_name,
            last_name=last_name,
            email=email,
            message=message,
            status='NEW'
        )
        db.session.add(contact)
        db.session.commit()
        
        current_app.logger.info(f"📩 Message de contact de {first_name} {last_name} ({email})")
        
        return jsonify({'success': True, 'message': 'Message envoyé avec succès !'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur contact: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur interne.'}), 500


@main_bp.route('/api/results/<int:session_id>')
@rate_limit(limit_per_minute=120)
def api_results(session_id):
    """API pour les résultats d'une session"""
    try:
        session_obj = CompetitionSession.query.get_or_404(session_id)
        
        scores = Score.query.filter_by(session_id=session_id).all()
        
        artist_totals = {}
        for score in scores:
            if score.artist_id not in artist_totals:
                artist_totals[score.artist_id] = {
                    'total': 0,
                    'count': 0
                }
            artist_totals[score.artist_id]['total'] += score.score
            artist_totals[score.artist_id]['count'] += 1
        
        results = []
        for artist_id, data in sorted(
            artist_totals.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        ):
            artist = Artist.query.get(artist_id)
            if artist and artist.user.account_status == 'ACTIVE':
                if data['count'] == 10:
                    results.append({
                        'position': len(results) + 1,
                        'artist_id': artist.id,
                        'code': artist.code,
                        'first_name': artist.user.first_name,
                        'last_name': artist.user.last_name,
                        'total': round(data['total'], 1),
                        'max_score': 100
                    })
        
        return jsonify({
            'results': results,
            'session': session_obj.number,
            'session_status': session_obj.status
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur API résultats: {str(e)}")
        return jsonify({'error': 'Erreur lors du chargement des résultats'}), 500