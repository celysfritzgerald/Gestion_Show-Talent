from flask import Blueprint, render_template, request, jsonify, current_app
from app import db
from datetime import datetime
from app.models import (
    Artist, CompetitionSession, Sponsor, Moment, User,
    Score, Criterion, ContactMessage, Lyric,
    PublicVote, Poll, PollOption, PollVote,
    VoteConfig, VoteSession,
)
from app.permissions import rate_limit
from email_validator import EmailNotValidError, validate_email

main_bp = Blueprint('main', __name__)


# ============================================================
# HELPERS
# ============================================================

def _generate_fingerprint(request, secret):
    """Génère une empreinte unique à partir de IP + User-Agent + Secret"""
    import hashlib
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
    ua = request.headers.get('User-Agent', 'unknown')
    raw = f"{ip}|{ua}|{secret}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _get_vote_config():
    """Récupère ou crée la config du vote"""
    config = VoteConfig.query.first()
    if not config:
        config = VoteConfig(mode="PER_SESSION", is_enabled=True)
        db.session.add(config)
        db.session.commit()
    return config


# ============================================================
# PAGES PUBLIQUES
# ============================================================

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

        lyrics_preview = Lyric.query.filter_by(is_published=True).order_by(
            Lyric.created_at.desc()
        ).limit(3).all()

        return render_template('public/index.html',
                             artists=artists,
                             sponsors=sponsors,
                             moments=moments,
                             sessions=sessions,
                             lyrics_preview=lyrics_preview)
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


# ============================================================
# API CONTACT
# ============================================================

@main_bp.route('/api/contact', methods=['POST'])
@rate_limit(limit_per_minute=30)
def contact():
    """API pour le formulaire de contact"""
    try:
        data = request.get_json(silent=True) or {}

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()

        if not all([first_name, last_name, email, message]):
            return jsonify({'success': False, 'message': 'Tous les champs sont requis.'}), 400

        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            return jsonify({'success': False, 'message': 'Email invalide.'}), 400

        if len(first_name) > 100 or len(last_name) > 100 or len(email) > 255 or len(message) > 5000:
            return jsonify({'success': False, 'message': 'Données trop longues.'}), 400

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


# ============================================================
# API RÉSULTATS
# ============================================================

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


# ============================================================
# PAROLES (LYRICS)
# ============================================================

@main_bp.route('/lyrics')
@rate_limit(limit_per_minute=60)
def lyrics():
    """Page publique des paroles"""
    try:
        lyrics_list = Lyric.query.filter_by(is_published=True).order_by(
            Lyric.created_at.desc()
        ).all()

        codes = sorted(set([l.artist_code for l in lyrics_list]))

        return render_template('public/lyrics.html',
                             lyrics=lyrics_list,
                             codes=codes)
    except Exception as e:
        current_app.logger.error(f"Erreur page lyrics: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/lyrics/<int:lyric_id>')
@rate_limit(limit_per_minute=60)
def lyric_detail(lyric_id):
    """Page détail d'une parole"""
    try:
        lyric = Lyric.query.filter_by(id=lyric_id, is_published=True).first_or_404()

        lyric.view_count = (lyric.view_count or 0) + 1
        db.session.commit()

        return render_template('public/lyric_detail.html', lyric=lyric)
    except Exception as e:
        current_app.logger.error(f"Erreur détail lyric: {str(e)}")
        return render_template('errors/500.html'), 500


# ============================================================
# VOTE PUBLIC — MODULE FLEXIBLE (GLOBAL ou PER_SESSION)
# ============================================================

@main_bp.route('/vote')
@rate_limit(limit_per_minute=30)
def vote():
    """Page publique de vote — s'adapte au mode configuré"""
    try:
        from sqlalchemy import func

        config = _get_vote_config()
        edition = request.args.get('edition', '4e')

        artists_list = Artist.query.join(User).filter(
            User.account_status == 'ACTIVE',
            Artist.competition_status == 'ACTIVE'
        ).order_by(Artist.code).all()

        sessions = VoteSession.query.order_by(VoteSession.number).all()
        current_session = None

        if config.mode == 'PER_SESSION':
            session_id = request.args.get('session_id', type=int)
            if session_id:
                current_session = VoteSession.query.get(session_id)
            if not current_session and sessions:
                current_session = VoteSession.query.filter_by(is_open=True).order_by(
                    VoteSession.number
                ).first()
                if not current_session:
                    current_session = sessions[0]

        if config.mode == 'GLOBAL':
            vote_query = db.session.query(
                PublicVote.artist_id, func.count(PublicVote.id)
            ).filter(
                PublicVote.mode == 'GLOBAL',
                PublicVote.edition == edition
            )
        else:
            if not current_session:
                return render_template('public/vote.html',
                                     config=config,
                                     sessions=sessions,
                                     current_session=None,
                                     artists_data=[],
                                     total_votes=0,
                                     existing_vote=None,
                                     edition=edition)
            vote_query = db.session.query(
                PublicVote.artist_id, func.count(PublicVote.id)
            ).filter(
                PublicVote.mode == 'PER_SESSION',
                PublicVote.session_id == current_session.id
            )

        vote_counts = dict(vote_query.group_by(PublicVote.artist_id).all())
        total_votes = sum(vote_counts.values())

        artists_data = []
        for artist in artists_list:
            count = vote_counts.get(artist.id, 0)
            percentage = round((count / total_votes * 100), 1) if total_votes > 0 else 0
            artists_data.append({
                'artist': artist,
                'votes': count,
                'percentage': percentage
            })

        artists_data.sort(key=lambda x: x['votes'], reverse=True)

        secret = current_app.config.get('SECRET_KEY', 'fallback')
        fingerprint = _generate_fingerprint(request, secret)

        if config.mode == 'GLOBAL':
            existing_vote = PublicVote.query.filter_by(
                voter_fingerprint=fingerprint,
                mode='GLOBAL',
                edition=edition
            ).first()
        else:
            if current_session:
                existing_vote = PublicVote.query.filter_by(
                    voter_fingerprint=fingerprint,
                    mode='PER_SESSION',
                    session_id=current_session.id
                ).first()
            else:
                existing_vote = None

        return render_template('public/vote.html',
                             config=config,
                             sessions=sessions,
                             current_session=current_session,
                             artists_data=artists_data,
                             total_votes=total_votes,
                             existing_vote=existing_vote,
                             edition=edition)
    except Exception as e:
        current_app.logger.error(f"Erreur page vote: {str(e)}")
        current_app.logger.exception('Erreur page vote')
        return render_template('errors/500.html'), 500


@main_bp.route('/api/vote', methods=['POST'])
@rate_limit(limit_per_minute=10)
def api_vote():
    """API pour enregistrer un vote"""
    try:
        config = _get_vote_config()

        if not config.is_enabled:
            return jsonify({
                'success': False,
                'message': config.closed_message or 'Le vote est actuellement fermé.',
                'vote_closed': True
            }), 403

        data = request.get_json(silent=True) or {}
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        artist_id = data.get('artist_id')
        session_id = data.get('session_id')
        edition = data.get('edition', '4e')

        if not all([first_name, last_name, artist_id]):
            return jsonify({
                'success': False,
                'message': 'Prénom, nom et artiste sont requis.'
            }), 400

        if len(first_name) > 100 or len(last_name) > 100:
            return jsonify({
                'success': False,
                'message': 'Nom ou prénom trop long (max 100 caractères).'
            }), 400

        try:
            artist_id = int(artist_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Artiste invalide.'}), 400

        session_obj = None
        if config.mode == 'PER_SESSION':
            if not session_id:
                return jsonify({
                    'success': False,
                    'message': 'La soirée est requise.'
                }), 400
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Soirée invalide.'}), 400

            session_obj = VoteSession.query.get(session_id)
            if not session_obj:
                return jsonify({'success': False, 'message': 'Soirée introuvable.'}), 404

            if not session_obj.is_open:
                return jsonify({
                    'success': False,
                    'message': session_obj.closed_message or 'Le vote pour cette soirée est fermé.',
                    'vote_closed': True
                }), 403

        artist = Artist.query.join(User).filter(
            Artist.id == artist_id,
            User.account_status == 'ACTIVE',
            Artist.competition_status == 'ACTIVE'
        ).first()

        if not artist:
            return jsonify({'success': False, 'message': 'Artiste introuvable ou inactif.'}), 404

        secret = current_app.config.get('SECRET_KEY', 'fallback')
        fingerprint = _generate_fingerprint(request, secret)

        if config.mode == 'GLOBAL':
            existing = PublicVote.query.filter_by(
                voter_fingerprint=fingerprint,
                mode='GLOBAL',
                edition=edition
            ).first()
        else:
            existing = PublicVote.query.filter_by(
                voter_fingerprint=fingerprint,
                mode='PER_SESSION',
                session_id=session_id
            ).first()

        if existing:
            return jsonify({
                'success': False,
                'message': f'Vous avez déjà voté ({existing.voter_first_name} {existing.voter_last_name}).',
                'already_voted': True
            }), 409

        vote_obj = PublicVote(
            voter_first_name=first_name,
            voter_last_name=last_name,
            voter_fingerprint=fingerprint,
            voter_ip=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:45],
            voter_user_agent=request.headers.get('User-Agent', '')[:255],
            artist_id=artist_id,
            session_id=session_id if config.mode == 'PER_SESSION' else None,
            mode=config.mode,
            edition=edition
        )
        db.session.add(vote_obj)
        db.session.commit()

        from sqlalchemy import func
        if config.mode == 'GLOBAL':
            new_count = PublicVote.query.filter_by(
                artist_id=artist_id, mode='GLOBAL', edition=edition
            ).count()
            total = PublicVote.query.filter_by(mode='GLOBAL', edition=edition).count()
        else:
            new_count = PublicVote.query.filter_by(
                artist_id=artist_id, session_id=session_id
            ).count()
            total = PublicVote.query.filter_by(session_id=session_id).count()

        return jsonify({
            'success': True,
            'message': f'Merci {first_name} ! Votre vote pour {artist.user.full_name()} a été enregistré.',
            'artist_votes': new_count,
            'total_votes': total
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur API vote: {str(e)}")
        current_app.logger.exception('Erreur API vote')
        return jsonify({'success': False, 'message': 'Erreur interne.'}), 500


@main_bp.route('/api/vote/results')
@rate_limit(limit_per_minute=60)
def api_vote_results():
    """Résultats en temps réel selon le mode"""
    try:
        from sqlalchemy import func

        config = _get_vote_config()
        edition = request.args.get('edition', '4e')

        if config.mode == 'GLOBAL':
            results = db.session.query(
                PublicVote.artist_id,
                func.count(PublicVote.id).label('votes')
            ).filter(
                PublicVote.mode == 'GLOBAL',
                PublicVote.edition == edition
            ).group_by(PublicVote.artist_id).all()
        else:
            session_id = request.args.get('session_id', type=int)
            if not session_id:
                return jsonify({'success': False, 'message': 'Session manquante.'}), 400

            results = db.session.query(
                PublicVote.artist_id,
                func.count(PublicVote.id).label('votes')
            ).filter(
                PublicVote.session_id == session_id
            ).group_by(PublicVote.artist_id).all()

        total = sum(r.votes for r in results)

        data = []
        for artist_id, votes in results:
            artist = Artist.query.get(artist_id)
            if artist:
                data.append({
                    'artist_id': artist_id,
                    'name': artist.user.full_name(),
                    'code': artist.code,
                    'votes': votes,
                    'percentage': round((votes / total * 100), 1) if total > 0 else 0
                })

        data.sort(key=lambda x: x['votes'], reverse=True)

        return jsonify({
            'success': True,
            'total_votes': total,
            'results': data
        })

    except Exception as e:
        current_app.logger.error(f"Erreur API vote results: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur interne.'}), 500


# ============================================================
# SONDAGES PUBLICS — MODULE INDÉPENDANT
# ============================================================

@main_bp.route('/sondages')
@rate_limit(limit_per_minute=60)
def public_polls():
    """Page publique des sondages actifs"""
    try:
        from sqlalchemy import func

        polls_list = Poll.query.filter_by(is_active=True).filter(
            db.or_(Poll.closes_at.is_(None), Poll.closes_at > datetime.utcnow())
        ).order_by(Poll.created_at.desc()).all()

        secret = current_app.config.get('SECRET_KEY', 'fallback')
        fingerprint = _generate_fingerprint(request, secret)

        polls_data = []
        for poll in polls_list:
            vote_counts = dict(
                db.session.query(PollVote.option_id, func.count(PollVote.id))
                .filter(PollVote.poll_id == poll.id)
                .group_by(PollVote.option_id)
                .all()
            )

            total = sum(vote_counts.values())

            options = []
            for option in poll.options.order_by(PollOption.display_order).all():
                count = vote_counts.get(option.id, 0)
                percentage = round((count / total * 100), 1) if total > 0 else 0
                options.append({
                    'option': option,
                    'votes': count,
                    'percentage': percentage
                })

            user_vote = PollVote.query.filter_by(
                poll_id=poll.id,
                voter_fingerprint=fingerprint
            ).first()

            polls_data.append({
                'poll': poll,
                'options': options,
                'total_votes': total,
                'user_vote': user_vote.option_id if user_vote else None
            })

        return render_template('public/polls.html', polls_data=polls_data)
    except Exception as e:
        current_app.logger.error(f"Erreur page polls: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/api/poll/vote', methods=['POST'])
@rate_limit(limit_per_minute=10)
def api_poll_vote():
    """API pour voter dans un sondage"""
    try:
        data = request.get_json(silent=True) or {}
        poll_id = data.get('poll_id')
        option_id = data.get('option_id')

        if not poll_id or not option_id:
            return jsonify({'success': False, 'message': 'Données manquantes.'}), 400

        try:
            poll_id = int(poll_id)
            option_id = int(option_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'IDs invalides.'}), 400

        poll = Poll.query.get(poll_id)
        if not poll or not poll.is_active:
            return jsonify({'success': False, 'message': 'Sondage introuvable ou inactif.'}), 404

        if poll.closes_at and poll.closes_at < datetime.utcnow():
            return jsonify({'success': False, 'message': 'Sondage fermé.'}), 403

        option = PollOption.query.filter_by(id=option_id, poll_id=poll_id).first()
        if not option:
            return jsonify({'success': False, 'message': 'Option invalide.'}), 404

        secret = current_app.config.get('SECRET_KEY', 'fallback')
        fingerprint = _generate_fingerprint(request, secret)

        existing = PollVote.query.filter_by(
            poll_id=poll_id,
            voter_fingerprint=fingerprint
        ).first()

        if existing:
            return jsonify({
                'success': False,
                'message': 'Vous avez déjà voté pour ce sondage.',
                'already_voted': True
            }), 409

        vote_obj = PollVote(
            poll_id=poll_id,
            option_id=option_id,
            voter_fingerprint=fingerprint
        )
        db.session.add(vote_obj)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Votre vote a été enregistré !'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur API poll vote: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur interne.'}), 500


@main_bp.route('/api/poll/<int:poll_id>/results')
@rate_limit(limit_per_minute=60)
def api_poll_results(poll_id):
    """Résultats en temps réel d'un sondage"""
    try:
        from sqlalchemy import func

        poll = Poll.query.get_or_404(poll_id)

        vote_counts = dict(
            db.session.query(PollVote.option_id, func.count(PollVote.id))
            .filter(PollVote.poll_id == poll_id)
            .group_by(PollVote.option_id)
            .all()
        )

        total = sum(vote_counts.values())

        results = []
        for option in poll.options.order_by(PollOption.display_order).all():
            count = vote_counts.get(option.id, 0)
            results.append({
                'option_id': option.id,
                'text': option.text,
                'votes': count,
                'percentage': round((count / total * 100), 1) if total > 0 else 0
            })

        return jsonify({
            'success': True,
            'total_votes': total,
            'results': results
        })

    except Exception as e:
        current_app.logger.error(f"Erreur API poll results: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur interne.'}), 500