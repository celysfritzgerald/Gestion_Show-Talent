"""
Tests du système de vote public
Modes GLOBAL et PER_SESSION
"""
import pytest
from app import db
from app.models import PublicVote, VoteConfig, VoteSession, Artist, User


# ============================================================
# Tests VoteConfig
# ============================================================

class TestVoteConfig:

    def test_get_or_create_default_config(self, app, db):
        """Le système crée une config par défaut si absente"""
        with app.app_context():
            VoteConfig.query.delete()
            db.session.commit()

            assert VoteConfig.query.first() is None

            from app.routes import _get_vote_config
            config = _get_vote_config()

            assert config is not None
            assert config.mode == "PER_SESSION"
            assert config.is_enabled is True

    def test_mode_global(self, app, db):
        """Test du mode GLOBAL"""
        with app.app_context():
            config = VoteConfig(mode="GLOBAL", is_enabled=True)
            db.session.add(config)
            db.session.commit()

            assert config.mode == "GLOBAL"

    def test_mode_per_session(self, app, db):
        """Test du mode PER_SESSION"""
        with app.app_context():
            config = VoteConfig(mode="PER_SESSION", is_enabled=True)
            db.session.add(config)
            db.session.commit()

            assert config.mode == "PER_SESSION"


# ============================================================
# Tests PublicVote
# ============================================================

class TestPublicVoteModel:

    def test_create_vote_global(self, app, db, artist_user):
        """Créer un vote en mode GLOBAL"""
        with app.app_context():
            artist = artist_user.artist_profile
            vote = PublicVote(
                voter_first_name="Jean",
                voter_last_name="Dupont",
                voter_fingerprint="test_fp_1",
                artist_id=artist.id,
                session_id=None,
                mode="GLOBAL",
                edition="4e"
            )
            db.session.add(vote)
            db.session.commit()

            assert vote.id is not None
            assert vote.mode == "GLOBAL"
            assert vote.session_id is None

    def test_create_vote_per_session(self, app, db, artist_user, vote_session):
        """Créer un vote en mode PER_SESSION"""
        with app.app_context():
            artist = artist_user.artist_profile
            vote = PublicVote(
                voter_first_name="Marie",
                voter_last_name="Pierre",
                voter_fingerprint="test_fp_2",
                artist_id=artist.id,
                session_id=vote_session.id,
                mode="PER_SESSION",
                edition="4e"
            )
            db.session.add(vote)
            db.session.commit()

            assert vote.session_id == vote_session.id
            assert vote.mode == "PER_SESSION"

    def test_unique_vote_per_session(self, app, db, artist_user, vote_session):
        """Un même fingerprint ne peut voter qu'une fois par session"""
        with app.app_context():
            artist = artist_user.artist_profile
            fingerprint = "same_fp"

            vote1 = PublicVote(
                voter_first_name="A",
                voter_last_name="B",
                voter_fingerprint=fingerprint,
                artist_id=artist.id,
                session_id=vote_session.id,
                mode="PER_SESSION"
            )
            db.session.add(vote1)
            db.session.commit()

            vote2 = PublicVote(
                voter_first_name="C",
                voter_last_name="D",
                voter_fingerprint=fingerprint,
                artist_id=artist.id,
                session_id=vote_session.id,
                mode="PER_SESSION"
            )
            db.session.add(vote2)

            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()


# ============================================================
# Tests Routes
# ============================================================

class TestVoteRoutes:

    def test_vote_page_accessible(self, client, db):
        """La page /vote est accessible"""
        response = client.get('/vote')
        assert response.status_code == 200

    def test_vote_page_mode_global(self, client, db):
        """La page /vote en mode GLOBAL"""
        config = VoteConfig(mode="GLOBAL", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        response = client.get('/vote')
        assert response.status_code == 200

    def test_vote_page_mode_per_session(self, client, db, vote_session):
        """La page /vote en mode PER_SESSION"""
        config = VoteConfig(mode="PER_SESSION", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        response = client.get('/vote')
        assert response.status_code == 200


# ============================================================
# Tests API
# ============================================================

class TestVoteAPI:

    def test_vote_global_success(self, client, db, artist_user):
        """Voter en mode GLOBAL"""
        config = VoteConfig(mode="GLOBAL", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        artist = artist_user.artist_profile

        response = client.post('/api/vote', json={
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'artist_id': artist.id,
            'edition': '4e'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_vote_per_session_success(self, client, db, artist_user, vote_session):
        """Voter en mode PER_SESSION"""
        config = VoteConfig(mode="PER_SESSION", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        artist = artist_user.artist_profile

        response = client.post('/api/vote', json={
            'first_name': 'Marie',
            'last_name': 'Pierre',
            'artist_id': artist.id,
            'session_id': vote_session.id,
            'edition': '4e'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_vote_missing_fields(self, client, db):
        """Vote sans champs obligatoires"""
        response = client.post('/api/vote', json={
            'first_name': 'Jean'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_vote_when_disabled(self, client, db, artist_user):
        """Vote quand désactivé"""
        config = VoteConfig(mode="PER_SESSION", is_enabled=False)
        db.session.add(config)
        db.session.commit()

        artist = artist_user.artist_profile

        response = client.post('/api/vote', json={
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'artist_id': artist.id
        })
        assert response.status_code == 403
        data = response.get_json()
        assert data.get('vote_closed') is True


# ============================================================
# Tests VoteSession
# ============================================================

class TestVoteSessionModel:

    def test_create_session(self, app, db):
        """Créer une soirée de vote"""
        with app.app_context():
            session = VoteSession(
                number=10,
                title="Dimanche 10",
                is_open=True
            )
            db.session.add(session)
            db.session.commit()

            assert session.id is not None
            assert session.number == 10
            assert session.is_open is True

    def test_session_unique_number(self, app, db):
        """Le numéro de soirée est unique"""
        with app.app_context():
            s1 = VoteSession(number=15, title="Test", is_open=True)
            db.session.add(s1)
            db.session.commit()

            s2 = VoteSession(number=15, title="Doublon", is_open=True)
            db.session.add(s2)

            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()