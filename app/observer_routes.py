"""
Blueprint Observateur — LECTURE SEULE + PERMISSIONS GRANULAIRES.

Chaque route est protégée par @observer_has('<section>').
L'observateur ne voit que ce que l'admin lui a autorisé.
"""
from flask import (
    Blueprint, render_template, session, flash,
    redirect, url_for, current_app, request, abort, jsonify,
)
from datetime import datetime
from sqlalchemy import func
from app import db
from app.models import (
    User, Artist, CompetitionSession, Criterion,
    Assignment, Score, Comment,
    Sponsor, FinanceCategory, FinanceTransaction,
    PublicVote, VoteConfig, VoteSession,
    Lyric, Poll, PollOption, PollVote,
    ContactMessage, Moment,
    ObserverPermission,
)
from app.permissions import (
    observer_required, observer_has, get_observer_sections, rate_limit,
)
from app.services_ranking import (
    compute_ranking,
    get_global_stats,
    get_sessions_for_ranking,
    get_all_criteria,
    get_matrix_for_session,
)

observer_bp = Blueprint('observer', __name__, url_prefix='/observer')


# ═══════════════════════════════════════════════════════════
# GARDE-FOU : refuse toute méthode non-GET
# ═══════════════════════════════════════════════════════════

@observer_bp.before_request
def _observer_readonly_guard():
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        current_app.logger.warning(
            f"[OBSERVER] Tentative {request.method} bloquée sur {request.path} "
            f"par user_id={session.get('user_id')}"
        )
        abort(405)


# ═══════════════════════════════════════════════════════════
# DASHBOARD (toujours accessible)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/')
@observer_required
@rate_limit(limit_per_minute=120)
def dashboard():
    """Dashboard observateur : ne montre que les sections autorisées."""
    try:
        sections = get_observer_sections()
        stats = get_global_stats()
        sessions = get_sessions_for_ranking()

        # Compteurs dynamiques selon permissions
        new_messages_count = 0
        recent_votes = []
        recent_transactions = []
        recent_comments = []

        if 'messages' in sections:
            new_messages_count = ContactMessage.query.filter_by(status='NEW').count()

        if 'votes' in sections:
            recent_votes = (
                PublicVote.query
                .order_by(PublicVote.created_at.desc())
                .limit(5).all()
            )

        if 'finance' in sections:
            recent_transactions = (
                FinanceTransaction.query
                .order_by(FinanceTransaction.created_at.desc())
                .limit(5).all()
            )

        if 'artists' in sections:
            recent_comments = (
                Comment.query
                .order_by(Comment.created_at.desc())
                .limit(5).all()
            )

        return render_template(
            'observer/dashboard.html',
            sections=sections,
            stats=stats,
            sessions=sessions,
            recent_votes=recent_votes,
            recent_transactions=recent_transactions,
            recent_comments=recent_comments,
            new_messages_count=new_messages_count,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur dashboard: {e}")
        current_app.logger.exception("Détail")
        flash("Erreur lors du chargement du dashboard.", "danger")
        return redirect(url_for('auth.login'))


# ═══════════════════════════════════════════════════════════
# ARTISTES (section : artists)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/artists')
@observer_required
@observer_has('artists')
@rate_limit(limit_per_minute=120)
def artists():
    try:
        show_eliminated = request.args.get('eliminated', '0') == '1'
        q = Artist.query
        if not show_eliminated:
            q = q.filter(Artist.competition_status == 'ACTIVE')
        artists_list = q.order_by(Artist.code).all()

        return render_template(
            'observer/artists.html',
            sections=get_observer_sections(),
            artists=artists_list,
            show_eliminated=show_eliminated,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur artists: {e}")
        flash("Erreur lors du chargement des artistes.", "danger")
        return redirect(url_for('observer.dashboard'))


@observer_bp.route('/artists/<int:artist_id>')
@observer_required
@observer_has('artists')
@rate_limit(limit_per_minute=120)
def artist_detail(artist_id):
    try:
        artist = Artist.query.get_or_404(artist_id)
        sessions = get_sessions_for_ranking()

        session_scores = {}
        for s in sessions:
            scores = (
                Score.query
                .filter_by(artist_id=artist.id, session_id=s.id)
                .join(Criterion)
                .order_by(Criterion.id)
                .all()
            )
            if scores:
                total = sum(float(sc.score) for sc in scores)
                session_scores[s.id] = {
                    'session': s,
                    'scores': scores,
                    'total': round(total, 1),
                    'max_possible': 100,
                    'complete': len(scores) == 10,
                }

        comments = (
            Comment.query
            .filter_by(artist_id=artist.id)
            .order_by(Comment.created_at.desc())
            .all()
        )

        ranking = compute_ranking(include_eliminated=True)
        artist_rank = next(
            (i + 1 for i, e in enumerate(ranking) if e.artist_id == artist.id),
            None
        )
        artist_entry = next(
            (e for e in ranking if e.artist_id == artist.id),
            None
        )

        return render_template(
            'observer/artist_detail.html',
            sections=get_observer_sections(),
            artist=artist,
            session_scores=session_scores,
            comments=comments,
            artist_rank=artist_rank,
            artist_entry=artist_entry,
            sessions=sessions,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur artist_detail: {e}")
        flash("Erreur lors du chargement de l'artiste.", "danger")
        return redirect(url_for('observer.artists'))


# ═══════════════════════════════════════════════════════════
# NOTES DÉTAILLÉES (section : artists)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/scores')
@observer_required
@observer_has('artists')
@rate_limit(limit_per_minute=120)
def scores():
    try:
        sessions = CompetitionSession.query.order_by(CompetitionSession.number).all()

        if not sessions:
            return render_template(
                'observer/scores.html',
                sections=get_observer_sections(),
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
            'observer/scores.html',
            sections=get_observer_sections(),
            sessions=sessions,
            current_session=current_session,
            matrix=matrix,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur scores: {e}")
        flash("Erreur lors du chargement des notes.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# JURYS (section : juries)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/juries')
@observer_required
@observer_has('juries')
@rate_limit(limit_per_minute=120)
def juries():
    try:
        juries_list = (
            User.query
            .filter_by(role='jury')
            .order_by(User.last_name, User.first_name)
            .all()
        )

        scores_count = dict(
            db.session.query(Score.evaluator_id, func.count(Score.id))
            .group_by(Score.evaluator_id)
            .all()
        )

        jury_assignments = {}
        for j in juries_list:
            assigns = Assignment.query.filter_by(evaluator_user_id=j.id).all()
            jury_assignments[j.id] = assigns

        return render_template(
            'observer/juries.html',
            sections=get_observer_sections(),
            juries=juries_list,
            scores_count=scores_count,
            jury_assignments=jury_assignments,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur juries: {e}")
        flash("Erreur lors du chargement des jurys.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# CLASSEMENT (section : ranking)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/ranking')
@observer_required
@observer_has('ranking')
@rate_limit(limit_per_minute=120)
def ranking():
    try:
        session_id = request.args.get('session_id', type=int)
        include_eliminated = request.args.get('eliminated', '1') == '1'

        sessions = get_sessions_for_ranking()
        criteria = get_all_criteria()

        session_obj = None
        if session_id is not None:
            session_obj = CompetitionSession.query.get(session_id)
            if not session_obj:
                flash("Session introuvable.", "warning")
                return redirect(url_for('observer.ranking'))

        entries = compute_ranking(
            session_id=session_obj.id if session_obj else None,
            include_eliminated=include_eliminated,
            include_details=True,
        )

        for i, e in enumerate(entries, start=1):
            e.rank = i

        return render_template(
            'observer/ranking.html',
            sections=get_observer_sections(),
            entries=entries,
            sessions=sessions,
            criteria=criteria,
            current_session=session_obj,
            include_eliminated=include_eliminated,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur ranking: {e}")
        flash("Erreur lors du chargement du classement.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# SPONSORS (section : sponsors)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/sponsors')
@observer_required
@observer_has('sponsors')
@rate_limit(limit_per_minute=120)
def sponsors():
    try:
        sponsors_list = Sponsor.query.order_by(Sponsor.name).all()
        return render_template(
            'observer/sponsors.html',
            sections=get_observer_sections(),
            sponsors=sponsors_list,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur sponsors: {e}")
        flash("Erreur lors du chargement des sponsors.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# FINANCE (section : finance)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/finance')
@observer_required
@observer_has('finance')
@rate_limit(limit_per_minute=120)
def finance():
    try:
        total_income = (
            db.session.query(func.coalesce(func.sum(FinanceTransaction.amount), 0))
            .filter(FinanceTransaction.type == 'income')
            .scalar() or 0
        )
        total_expense = (
            db.session.query(func.coalesce(func.sum(FinanceTransaction.amount), 0))
            .filter(FinanceTransaction.type == 'expense')
            .scalar() or 0
        )
        balance = float(total_income) - float(total_expense)

        categories = (
            FinanceCategory.query
            .order_by(FinanceCategory.type, FinanceCategory.name)
            .all()
        )

        category_totals = {}
        for cat in categories:
            cat_total = (
                db.session.query(func.coalesce(func.sum(FinanceTransaction.amount), 0))
                .filter(FinanceTransaction.category_id == cat.id)
                .scalar() or 0
            )
            category_totals[cat.id] = float(cat_total)

        transactions = (
            FinanceTransaction.query
            .order_by(
                FinanceTransaction.transaction_date.desc(),
                FinanceTransaction.created_at.desc(),
            )
            .limit(100).all()
        )

        return render_template(
            'observer/finance.html',
            sections=get_observer_sections(),
            total_income=float(total_income),
            total_expense=float(total_expense),
            balance=balance,
            categories=categories,
            transactions=transactions,
            category_totals=category_totals,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur finance: {e}")
        flash("Erreur lors du chargement de la finance.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# VOTES PUBLICS (section : votes)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/votes')
@observer_required
@observer_has('votes')
@rate_limit(limit_per_minute=120)
def votes():
    try:
        config = VoteConfig.query.first()
        if not config:
            config = VoteConfig(mode="PER_SESSION", is_enabled=True)
            db.session.add(config)
            db.session.commit()

        edition = request.args.get('edition', '4e')
        session_id = request.args.get('session_id', type=int)

        vote_sessions = VoteSession.query.order_by(VoteSession.number).all()
        current_session = None
        if session_id:
            current_session = VoteSession.query.get(session_id)
        if not current_session and vote_sessions:
            current_session = vote_sessions[0]

        vote_q = PublicVote.query
        if config.mode == 'GLOBAL':
            vote_q = vote_q.filter_by(mode='GLOBAL', edition=edition)
        elif current_session:
            vote_q = vote_q.filter_by(session_id=current_session.id)
        else:
            vote_q = vote_q.filter(PublicVote.id == -1)

        results_q = db.session.query(
            PublicVote.artist_id,
            func.count(PublicVote.id).label('votes')
        )

        if config.mode == 'GLOBAL':
            results_q = results_q.filter(
                PublicVote.mode == 'GLOBAL', PublicVote.edition == edition
            )
        elif current_session:
            results_q = results_q.filter(PublicVote.session_id == current_session.id)
        else:
            results_q = results_q.filter(PublicVote.id == -1)

        results_raw = (
            results_q
            .group_by(PublicVote.artist_id)
            .order_by(func.count(PublicVote.id).desc())
            .all()
        )

        total_votes = sum(r.votes for r in results_raw)

        results = []
        for artist_id, votes_count in results_raw:
            artist = Artist.query.get(artist_id)
            if artist:
                results.append({
                    'artist': artist,
                    'votes': votes_count,
                    'percentage': (
                        round(votes_count / total_votes * 100, 1)
                        if total_votes > 0 else 0
                    ),
                })

        voters = vote_q.order_by(PublicVote.created_at.desc()).limit(200).all()

        return render_template(
            'observer/votes.html',
            sections=get_observer_sections(),
            config=config,
            sessions=vote_sessions,
            current_session=current_session,
            results=results,
            voters=voters,
            total_votes=total_votes,
            edition=edition,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur votes: {e}")
        flash("Erreur lors du chargement des votes.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# PAROLES (section : lyrics)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/lyrics')
@observer_required
@observer_has('lyrics')
@rate_limit(limit_per_minute=120)
def lyrics():
    try:
        lyrics_list = Lyric.query.order_by(Lyric.created_at.desc()).all()
        return render_template(
            'observer/lyrics.html',
            sections=get_observer_sections(),
            lyrics=lyrics_list,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur lyrics: {e}")
        flash("Erreur lors du chargement des paroles.", "danger")
        return redirect(url_for('observer.dashboard'))


@observer_bp.route('/lyrics/<int:lyric_id>')
@observer_required
@observer_has('lyrics')
@rate_limit(limit_per_minute=120)
def lyric_detail(lyric_id):
    try:
        lyric = Lyric.query.get_or_404(lyric_id)
        return render_template(
            'observer/lyric_detail.html',
            sections=get_observer_sections(),
            lyric=lyric,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur lyric_detail: {e}")
        flash("Erreur lors du chargement de la parole.", "danger")
        return redirect(url_for('observer.lyrics'))


# ═══════════════════════════════════════════════════════════
# SONDAGES (section : polls)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/polls')
@observer_required
@observer_has('polls')
@rate_limit(limit_per_minute=120)
def polls():
    try:
        polls_list = Poll.query.order_by(Poll.created_at.desc()).all()

        poll_results = {}
        for p in polls_list:
            total = (
                db.session.query(func.count(PollVote.id))
                .filter(PollVote.poll_id == p.id)
                .scalar() or 0
            )
            options = []
            for opt in p.options.order_by(PollOption.display_order).all():
                count = (
                    db.session.query(func.count(PollVote.id))
                    .filter(PollVote.option_id == opt.id)
                    .scalar() or 0
                )
                options.append({
                    'text': opt.text,
                    'count': count,
                    'percentage': round(count / total * 100, 1) if total > 0 else 0,
                })
            poll_results[p.id] = {'total': total, 'options': options}

        return render_template(
            'observer/polls.html',
            sections=get_observer_sections(),
            polls=polls_list,
            poll_results=poll_results,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur polls: {e}")
        flash("Erreur lors du chargement des sondages.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# MESSAGES (section : messages)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/messages')
@observer_required
@observer_has('messages')
@rate_limit(limit_per_minute=120)
def messages():
    try:
        messages_list = (
            ContactMessage.query
            .order_by(ContactMessage.created_at.desc())
            .all()
        )
        return render_template(
            'observer/messages.html',
            sections=get_observer_sections(),
            messages=messages_list,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur messages: {e}")
        flash("Erreur lors du chargement des messages.", "danger")
        return redirect(url_for('observer.dashboard'))


# ═══════════════════════════════════════════════════════════
# MOMENTS (section : moments)
# ═══════════════════════════════════════════════════════════

@observer_bp.route('/moments')
@observer_required
@observer_has('moments')
@rate_limit(limit_per_minute=120)
def moments():
    try:
        moments_list = Moment.query.order_by(Moment.created_at.desc()).all()
        return render_template(
            'observer/moments.html',
            sections=get_observer_sections(),
            moments=moments_list,
            now=datetime.utcnow(),
        )
    except Exception as e:
        current_app.logger.error(f"[OBSERVER] Erreur moments: {e}")
        flash("Erreur lors du chargement des moments.", "danger")
        return redirect(url_for('observer.dashboard'))