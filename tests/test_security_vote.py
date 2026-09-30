"""
Tests de sécurité : Système de vote
"""
import pytest
from app import db
from app.models import VoteConfig, PublicVote


class TestVoteSecurity:

    def test_duplicate_vote_prevented(self, client, db, artist_user):
        """Un même utilisateur ne peut pas voter 2 fois"""
        config = VoteConfig(mode="GLOBAL", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        artist = artist_user.artist_profile

        # Premier vote
        response1 = client.post('/api/vote', json={
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'artist_id': artist.id,
            'edition': '4e'
        })
        assert response1.status_code == 200

        # Tentative de second vote
        response2 = client.post('/api/vote', json={
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'artist_id': artist.id,
            'edition': '4e'
        })
        # Doit être refusé (409 Conflict)
        assert response2.status_code == 409

    def test_vote_on_inactive_artist_rejected(self, client, db):
        """Voter pour un artiste inactif doit être refusé"""
        from app.models import User, Artist

        # Créer un artiste éliminé
        user = User(
            first_name='Inactive', last_name='Artist',
            email='inactive@test.com', username='inactive_artist',
            role='artist', account_status='ACTIVE'
        )
        user.set_password('pass1234')
        db.session.add(user)
        db.session.flush()

        artist = Artist(user_id=user.id, code='INA001', competition_status='ELIMINATED')
        db.session.add(artist)
        db.session.commit()

        config = VoteConfig(mode="GLOBAL", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        response = client.post('/api/vote', json={
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'artist_id': artist.id,
            'edition': '4e'
        })
        # Doit être refusé
        assert response.status_code == 404

    def test_vote_missing_fields_rejected(self, client, db):
        """Vote sans champs obligatoires doit être refusé"""
        response = client.post('/api/vote', json={
            'first_name': 'Jean'
            # Manque last_name et artist_id
        })
        assert response.status_code == 400

    def test_vote_with_invalid_artist_id(self, client, db):
        """Vote avec ID artiste invalide"""
        config = VoteConfig(mode="GLOBAL", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        response = client.post('/api/vote', json={
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'artist_id': 99999,
            'edition': '4e'
        })
        assert response.status_code == 404

    def test_sql_injection_in_vote(self, client, db, artist_user):
        """Tentative d'injection SQL via API vote"""
        config = VoteConfig(mode="GLOBAL", is_enabled=True)
        db.session.add(config)
        db.session.commit()

        artist = artist_user.artist_profile

        response = client.post('/api/vote', json={
            'first_name': "'; DROP TABLE public_votes; --",
            'last_name': "Test",
            'artist_id': artist.id,
            'edition': '4e'
        })
        # Ne doit pas planter
        assert response.status_code in [200, 400]

        # Table toujours là
        count = PublicVote.query.count()
        assert count >= 0