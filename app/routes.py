from flask import Blueprint, render_template, request, jsonify, current_app, Response, send_from_directory
from app import db
from datetime import datetime
from sqlalchemy import func
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
    """Génère une empreinte unique à partir de IP + User-Agent + Secret."""
    import hashlib
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
    ua = request.headers.get('User-Agent', 'unknown')
    raw = f"{ip}|{ua}|{secret}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _get_vote_config():
    """Récupère ou crée la config du vote avec TOUS les défauts."""
    config = VoteConfig.query.first()
    if not config:
        config = VoteConfig(
            mode="PER_SESSION",
            is_enabled=True,
            title="Qui va gagner cette édition ?",
            subtitle="Votez pour votre artiste préféré",
            cta_text="Voter pour cet artiste",
            primary_color="#facc15",
            show_results_live=True,
            show_vote_counts=True,
            show_percentages=True,
            show_progress_bars=True,
            show_ranking_badge=True,
            require_first_name=True,
            require_last_name=True,
            max_votes_per_session=1,
        )
        db.session.add(config)
        db.session.commit()
    return config


# ============================================================
# PAGES PUBLIQUES
# ============================================================

@main_bp.route('/')
@rate_limit(limit_per_minute=120)
def index():
    """Page d'accueil."""
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
    """Page À propos."""
    return render_template('public/about.html')


@main_bp.route('/artists')
@rate_limit(limit_per_minute=60)
def artists():
    """Page des artistes."""
    try:
        artists_list = Artist.query.join(User).filter(
            User.account_status == 'ACTIVE'
        ).order_by(User.last_name).all()
        return render_template('public/artists.html', artists=artists_list)
    except Exception as e:
        current_app.logger.error(f"Erreur page artistes: {str(e)}")
        return render_template('errors/500.html'), 500


@main_bp.route('/results')
@rate_limit(limit_per_minute=60)
def results():
    """Page des résultats — GLOBAL + par dimanche."""
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
    """Page des sponsors."""
    try:
        sponsors_list = Sponsor.query.all()
        return render_template('public/sponsors.html', sponsors=sponsors_list)
    except Exception as e:
        current_app.logger.error(f"Erreur page sponsors: {str(e)}")
        return render_template('errors/500.html'), 500


# ============================================================
# MOMENTS FORTS — PAGE PUBLIQUE
# ============================================================

@main_bp.route('/moments')
@rate_limit(limit_per_minute=60)
def moments():
    """Galerie publique des moments forts."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 24
        if page < 1:
            page = 1

        session_id = request.args.get('session_id', type=int)

        if session_id:
            pagination = (
                Moment.query
                .filter_by(session_id=session_id)
                .order_by(Moment.created_at.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
        else:
            pagination = (
                Moment.query
                .order_by(Moment.created_at.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )

        sessions = CompetitionSession.query.order_by(
            CompetitionSession.number
        ).all()

        return render_template(
            'public/moments.html',
            pagination=pagination,
            moments=pagination.items,
            sessions=sessions,
            current_session_id=session_id,
        )

    except Exception as e:
        current_app.logger.error(f"Erreur page moments: {str(e)}")
        return render_template('errors/500.html'), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@main_bp.route('/health')
def health():
    """Health check : DB + timestamp."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
        }), 200
    except Exception as e:
        current_app.logger.error(f"Health check FAILED: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
        }), 500


# ============================================================
# API CONTACT
# ============================================================

@main_bp.route('/api/contact', methods=['POST'])
@rate_limit(limit_per_minute=30)
def contact():
    """API pour le formulaire de contact."""
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

        contact_obj = ContactMessage(
            first_name=first_name,
            last_name=last_name,
            email=email,
            message=message,
            status='NEW'
        )
        db.session.add(contact_obj)
        db.session.commit()

        current_app.logger.info(f"📩 Message de contact de {first_name} {last_name} ({email})")

        return jsonify({'success': True, 'message': 'Message envoyé avec succès !'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur contact: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur interne.'}), 500


# ============================================================
# API RÉSULTATS (par session — optimisé)
# ============================================================

@main_bp.route('/api/results/<int:session_id>')
@rate_limit(limit_per_minute=120)
def api_results(session_id):
    """API pour les résultats d'une session."""
    try:
        session_obj = CompetitionSession.query.get_or_404(session_id)

        rows = (
            db.session.query(
                Artist.id,
                Artist.code,
                User.first_name,
                User.last_name,
                func.sum(Score.score).label('total'),
                func.count(Score.id).label('count'),
            )
            .join(User, User.id == Artist.user_id)
            .join(Score, Score.artist_id == Artist.id)
            .filter(
                Score.session_id == session_id,
                User.account_status == 'ACTIVE',
            )
            .group_by(Artist.id, Artist.code, User.first_name, User.last_name)
            .having(func.count(Score.id) == 10)
            .order_by(func.sum(Score.score).desc())
        ).all()

        results = [
            {
                'position': i,
                'artist_id': row[0],
                'code': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'total': round(float(row[4]), 1),
                'max_score': 100,
            }
            for i, row in enumerate(rows, 1)
        ]

        return jsonify({
            'results': results,
            'session': session_obj.number,
            'session_status': session_obj.status,
        })

    except Exception as e:
        current_app.logger.error(f"Erreur API résultats: {str(e)}")
        current_app.logger.exception("Détail")
        return jsonify({'error': 'Erreur lors du chargement des résultats'}), 500


# ============================================================
# API CLASSEMENT PUBLIC
# ============================================================

@main_bp.route('/api/public-ranking')
@rate_limit(limit_per_minute=120)
def api_public_ranking():
    """Classement public (JSON)."""
    from app.services_ranking import compute_ranking

    try:
        session_id = request.args.get('session_id', type=int)
        session_obj = None

        if session_id and session_id > 0:
            session_obj = CompetitionSession.query.get(session_id)
            if not session_obj:
                return jsonify({'success': False, 'error': 'Session introuvable'}), 404

        entries = compute_ranking(
            session_id=session_obj.id if session_obj else None,
            include_eliminated=True,
            include_details=False,
        )

        sessions_count = CompetitionSession.query.count()

        results = []
        for i, e in enumerate(entries, start=1):
            parts = (e.artist_name or '').split(' ', 1)
            first_name = parts[0] if parts else ''
            last_name = parts[1] if len(parts) > 1 else ''

            results.append({
                'position': i,
                'artist_id': e.artist_id,
                'code': e.artist_code,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': e.artist_name,
                'photo': e.artist_photo,
                'total': round(e.total_score, 1),
                'average': round(e.average_score, 2),
                'scores_count': e.scores_count,
                'eliminated': e.competition_status == 'ELIMINATED',
                'status': e.competition_status,
            })

        return jsonify({
            'success': True,
            'mode': 'SESSION' if session_obj else 'GLOBAL',
            'session': session_obj.number if session_obj else None,
            'session_id': session_obj.id if session_obj else None,
            'sessions_count': sessions_count,
            'results': results,
        })

    except Exception as e:
        current_app.logger.error(f"Erreur API public-ranking: {str(e)}")
        current_app.logger.exception("Détail")
        return jsonify({'success': False, 'error': 'Erreur lors du chargement'}), 500


# ============================================================
# PAROLES (LYRICS)
# ============================================================

@main_bp.route('/lyrics')
@rate_limit(limit_per_minute=60)
def lyrics():
    """Page publique des paroles."""
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
    """Page détail d'une parole."""
    try:
        lyric = Lyric.query.filter_by(id=lyric_id, is_published=True).first_or_404()

        lyric.view_count = (lyric.view_count or 0) + 1
        db.session.commit()

        return render_template('public/lyric_detail.html', lyric=lyric)
    except Exception as e:
        current_app.logger.error(f"Erreur détail lyric: {str(e)}")
        return render_template('errors/500.html'), 500


# ============================================================
# VOTE PUBLIC
# ============================================================

@main_bp.route('/vote')
@rate_limit(limit_per_minute=30)
def vote():
    """Page publique de vote — s'adapte à la config."""
    try:
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

        if config.show_results_live:
            artists_data.sort(key=lambda x: x['votes'], reverse=True)
        else:
            artists_data.sort(key=lambda x: x['artist'].user.last_name.lower())

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
    """API pour enregistrer un vote."""
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
    """Résultats en temps réel selon le mode."""
    try:
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
# SONDAGES PUBLICS
# ============================================================

@main_bp.route('/sondages')
@rate_limit(limit_per_minute=60)
def public_polls():
    """Page publique des sondages actifs."""
    try:
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
    """API pour voter dans un sondage."""
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
    """Résultats en temps réel d'un sondage."""
    try:
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


# ============================================================
# SEO — SITEMAP DYNAMIQUE
# ============================================================

@main_bp.route('/sitemap.xml')
@rate_limit(limit_per_minute=10)
def sitemap():
    """Sitemap XML dynamique pour les moteurs de recherche."""
    base_url = request.url_root.rstrip('/')

    static_pages = [
        ('/',          '1.0', 'daily'),
        ('/artists',   '0.9', 'weekly'),
        ('/results',   '0.9', 'daily'),
        ('/moments',   '0.8', 'weekly'),
        ('/sponsors',  '0.7', 'weekly'),
        ('/lyrics',    '0.8', 'weekly'),
        ('/sondages',  '0.6', 'daily'),
        ('/about',     '0.5', 'monthly'),
    ]

    lyrics_list = Lyric.query.filter_by(is_published=True).all()

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for path, priority, changefreq in static_pages:
        xml.append('<url>')
        xml.append(f'  <loc>{base_url}{path}</loc>')
        xml.append(f'  <changefreq>{changefreq}</changefreq>')
        xml.append(f'  <priority>{priority}</priority>')
        xml.append('</url>')

    for lyric in lyrics_list:
        xml.append('<url>')
        xml.append(f'  <loc>{base_url}/lyrics/{lyric.id}</loc>')
        xml.append(f'  <lastmod>{lyric.updated_at.strftime("%Y-%m-%d")}</lastmod>')
        xml.append('  <changefreq>monthly</changefreq>')
        xml.append('  <priority>0.6</priority>')
        xml.append('</url>')

    xml.append('</urlset>')

    return Response(
        '\n'.join(xml),
        mimetype='application/xml',
        headers={'Cache-Control': 'public, max-age=3600'}
    )


# ============================================================
# SEO — robots.txt
# ============================================================

@main_bp.route('/robots.txt')
def robots():
    """Sert le fichier robots.txt depuis /static/."""
    return send_from_directory(current_app.static_folder, 'robots.txt')