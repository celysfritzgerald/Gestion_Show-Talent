"""
Service de calcul de classement et de statistiques.
✅ Version avec cache mémoire (TTL 60s) pour la performance.

Utilisé par :
- admin (dashboard, ranking)
- jury  (ranking)
- observer (lecture seule)
- artist (futur refactor)
"""
from __future__ import annotations
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    Artist, User, CompetitionSession, Criterion,
    Assignment, Score, Comment,
)


# ═══════════════════════════════════════════════════════════════
# CACHE MÉMOIRE (par worker)
# ═══════════════════════════════════════════════════════════════

_ranking_cache: Dict[str, tuple] = {}
_RANKING_CACHE_TTL = 60  # secondes
_RANKING_CACHE_MAX = 100  # nombre max d'entrées


def invalidate_ranking_cache():
    """
    Vide le cache du classement.
    ⚠️ À appeler APRÈS chaque modification de score :
    - admin_save_score / admin_delete_score
    - jury save_score / delete_score
    - modification d'artiste / session / critère
    """
    _ranking_cache.clear()


def _cache_key(session_id, evaluator_id, include_eliminated, include_details):
    return f"{session_id}|{evaluator_id}|{include_eliminated}|{include_details}"


# ─────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────

@dataclass
class ArtistScoreDetail:
    """Détail d'un score pour un artiste."""
    criterion_id: int
    criterion_name: str
    evaluator_id: int
    evaluator_name: str
    evaluator_role: str
    score: float
    max_score: float


@dataclass
class ArtistRankingEntry:
    """Entrée du classement pour un artiste."""
    artist_id: int
    artist_code: str
    artist_name: str
    artist_photo: Optional[str]
    competition_status: str
    total_score: float = 0.0
    average_score: float = 0.0
    scores_count: int = 0
    criteria_count: int = 0
    details: List[ArtistScoreDetail] = field(default_factory=list)

    @property
    def rank_label(self) -> str:
        return f"{self.artist_code} - {self.artist_name}"


# ─────────────────────────────────────────────────────────
# Fonctions publiques
# ─────────────────────────────────────────────────────────

def compute_ranking(
    session_id: Optional[int] = None,
    evaluator_id: Optional[int] = None,
    include_eliminated: bool = False,
    include_details: bool = True,
) -> List[ArtistRankingEntry]:
    """
    Calcule le classement des artistes.
    ✅ Avec cache mémoire (TTL 60 secondes).
    """
    # ✅ CACHE : vérifier d'abord
    key = _cache_key(session_id, evaluator_id, include_eliminated, include_details)
    now_ts = time.time()

    if key in _ranking_cache:
        cached_at, data = _ranking_cache[key]
        if now_ts - cached_at < _RANKING_CACHE_TTL:
            return data

    # ──────────── CALCUL ────────────
    artists_q = Artist.query.options(joinedload(Artist.user))
    if not include_eliminated:
        artists_q = artists_q.filter(Artist.competition_status == 'ACTIVE')
    artists = artists_q.all()

    if not artists:
        _ranking_cache[key] = (now_ts, [])
        return []

    artist_ids = [a.id for a in artists]

    scores_q = (
        db.session.query(
            Score.artist_id,
            Score.criterion_id,
            Score.evaluator_id,
            Score.score,
            Criterion.name.label('criterion_name'),
            Criterion.max_score,
            User.first_name,
            User.last_name,
            User.role,
        )
        .join(Criterion, Criterion.id == Score.criterion_id)
        .join(User, User.id == Score.evaluator_id)
        .filter(Score.artist_id.in_(artist_ids))
    )

    if session_id is not None:
        scores_q = scores_q.filter(Score.session_id == session_id)
    if evaluator_id is not None:
        scores_q = scores_q.filter(Score.evaluator_id == evaluator_id)

    rows = scores_q.all()

    by_artist: Dict[int, ArtistRankingEntry] = {}

    for a in artists:
        by_artist[a.id] = ArtistRankingEntry(
            artist_id=a.id,
            artist_code=a.code,
            artist_name=a.user.full_name() if a.user else "—",
            artist_photo=a.photo,
            competition_status=a.competition_status,
        )

    for row in rows:
        entry = by_artist.get(row.artist_id)
        if not entry:
            continue

        entry.total_score += float(row.score or 0.0)
        entry.scores_count += 1

        if include_details:
            entry.details.append(ArtistScoreDetail(
                criterion_id=row.criterion_id,
                criterion_name=row.criterion_name,
                evaluator_id=row.evaluator_id,
                evaluator_name=f"{row.first_name} {row.last_name}",
                evaluator_role=row.role,
                score=float(row.score or 0.0),
                max_score=float(row.max_score or 10.0),
            ))

    for entry in by_artist.values():
        criteria_ids = {d.criterion_id for d in entry.details} if include_details else set()
        entry.criteria_count = len(criteria_ids) or (1 if entry.scores_count else 0)
        entry.average_score = (
            round(entry.total_score / entry.scores_count, 2)
            if entry.scores_count else 0.0
        )
        entry.total_score = round(entry.total_score, 2)
        entry.details.sort(key=lambda d: (d.criterion_name, d.evaluator_name))

    ranking = sorted(
        by_artist.values(),
        key=lambda e: (e.total_score, e.average_score),
        reverse=True,
    )

    # ✅ CACHE : stocker
    _ranking_cache[key] = (now_ts, ranking)

    # Nettoyage si trop d'entrées
    if len(_ranking_cache) > _RANKING_CACHE_MAX:
        oldest_key = min(_ranking_cache.items(), key=lambda x: x[1][0])[0]
        _ranking_cache.pop(oldest_key, None)

    return ranking


def get_sessions_for_ranking() -> List[CompetitionSession]:
    """Retourne toutes les sessions triées par numéro."""
    return CompetitionSession.query.order_by(CompetitionSession.number).all()


def get_all_criteria() -> List[Criterion]:
    """Retourne tous les critères."""
    return Criterion.query.order_by(Criterion.name).all()


def get_global_stats() -> Dict[str, Any]:
    """Stats globales pour les dashboards."""
    return {
        'total_artists': Artist.query.count(),
        'active_artists': Artist.query.filter_by(competition_status='ACTIVE').count(),
        'eliminated_artists': Artist.query.filter_by(competition_status='ELIMINATED').count(),
        'total_juries': User.query.filter_by(role='jury').count(),
        'active_juries': User.query.filter_by(role='jury', account_status='ACTIVE').count(),
        'total_sessions': CompetitionSession.query.count(),
        'completed_sessions': CompetitionSession.query.filter_by(status='COMPLETED').count(),
        'in_progress_sessions': CompetitionSession.query.filter_by(status='IN_PROGRESS').count(),
        'total_criteria': Criterion.query.count(),
        'total_scores': Score.query.count(),
    }


def get_matrix_for_session(session_id: int, evaluator_id: Optional[int] = None):
    """
    Construit une matrice : artistes × critères → notes
    pour une session donnée.
    """
    session_obj = CompetitionSession.query.get(session_id)
    if not session_obj:
        return None

    criteria = (
        Criterion.query
        .join(Assignment, Assignment.criterion_id == Criterion.id)
        .filter(Assignment.session_id == session_id)
        .order_by(Criterion.id)
        .all()
    )

    artists = (
        Artist.query
        .options(joinedload(Artist.user))
        .filter_by(competition_status='ACTIVE')
        .order_by(Artist.code)
        .all()
    )

    scores_q = db.session.query(Score).filter(Score.session_id == session_id)
    if evaluator_id is not None:
        scores_q = scores_q.filter(Score.evaluator_id == evaluator_id)

    all_scores = scores_q.all()

    bucket = defaultdict(list)
    for sc in all_scores:
        bucket[(sc.artist_id, sc.criterion_id)].append(float(sc.score))

    rows = []
    totals_by_criterion = {c.id: 0.0 for c in criteria}

    for artist in artists:
        scores_by_criterion = {}
        total = 0.0
        count = 0

        for crit in criteria:
            values = bucket.get((artist.id, crit.id), [])
            if values:
                avg = sum(values) / len(values)
                scores_by_criterion[crit.id] = round(avg, 1)
                total += avg
                count += 1
                totals_by_criterion[crit.id] += avg
            else:
                scores_by_criterion[crit.id] = None

        rows.append({
            'artist': artist,
            'scores_by_criterion': scores_by_criterion,
            'total': round(total, 1),
            'count': count,
            'max_possible': len(criteria) * 10,
        })

    rows.sort(key=lambda r: r['total'], reverse=True)

    for i, r in enumerate(rows, start=1):
        r['rank'] = i

    for cid in totals_by_criterion:
        totals_by_criterion[cid] = round(totals_by_criterion[cid], 1)

    return {
        'session': session_obj,
        'criteria': criteria,
        'rows': rows,
        'totals_by_criterion': totals_by_criterion,
    }