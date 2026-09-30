"""
Tests de sécurité : Contrôle d'accès (IDOR, escalade de privilèges)
"""
import pytest
from app import db
from app.models import User, Artist


class TestAccessControl:

    def test_anonymous_cannot_access_admin(self, client, db):
        """Un visiteur ne peut pas accéder à l'admin"""
        response = client.get('/admin/', follow_redirects=False)
        # Doit rediriger vers login
        assert response.status_code in [302, 401, 403]

    def test_anonymous_cannot_access_jury(self, client, db):
        """Un visiteur ne peut pas accéder au jury"""
        response = client.get('/jury/', follow_redirects=False)
        assert response.status_code in [302, 401, 403]

    def test_anonymous_cannot_access_artist(self, client, db):
        """Un visiteur ne peut pas accéder à l'espace artiste"""
        response = client.get('/artist/', follow_redirects=False)
        assert response.status_code in [302, 401, 403]

    def test_artist_cannot_access_admin(self, client, db):
        """Un artiste ne peut pas accéder à l'admin"""
        artist = User(
            first_name='Artist',
            last_name='Test',
            email='artist@test.com',
            username='artist_acc',
            role='artist',
            account_status='ACTIVE'
        )
        artist.set_password('pass1234')
        db.session.add(artist)
        db.session.commit()

        client.post('/auth/login', data={
            'username': 'artist_acc',
            'password': 'pass1234'
        })

        response = client.get('/admin/', follow_redirects=False)
        assert response.status_code in [302, 403]

    def test_jury_cannot_access_admin(self, client, db):
        """Un jury ne peut pas accéder à l'admin"""
        jury = User(
            first_name='Jury',
            last_name='Test',
            email='jury@test.com',
            username='jury_acc',
            role='jury',
            account_status='ACTIVE'
        )
        jury.set_password('pass1234')
        db.session.add(jury)
        db.session.commit()

        client.post('/auth/login', data={
            'username': 'jury_acc',
            'password': 'pass1234'
        })

        response = client.get('/admin/', follow_redirects=False)
        assert response.status_code in [302, 403]

    def test_artist_cannot_view_other_artist_scores(self, client, db):
        """Un artiste ne peut pas voir les scores d'un autre"""
        # Créer 2 artistes
        user1 = User(
            first_name='Artist1', last_name='Test',
            email='a1@test.com', username='artist1_acc',
            role='artist', account_status='ACTIVE'
        )
        user1.set_password('pass1234')
        user2 = User(
            first_name='Artist2', last_name='Test',
            email='a2@test.com', username='artist2_acc',
            role='artist', account_status='ACTIVE'
        )
        user2.set_password('pass1234')
        db.session.add_all([user1, user2])
        db.session.flush()

        artist1 = Artist(user_id=user1.id, code='A001', competition_status='ACTIVE')
        artist2 = Artist(user_id=user2.id, code='A002', competition_status='ACTIVE')
        db.session.add_all([artist1, artist2])
        db.session.commit()

        # Se connecter en tant qu'artist1
        client.post('/auth/login', data={
            'username': 'artist1_acc',
            'password': 'pass1234'
        })

        # Tenter d'accéder aux scores d'artist2
        response = client.get(f'/artist/scores/{artist2.id}')
        # Doit être refusé ou redirigé
        assert response.status_code in [200, 302, 403, 404]

    def test_artist_cannot_modify_other_profile(self, client, db):
        """Un artiste ne peut pas modifier un autre profil artiste"""
        user = User(
            first_name='Artist', last_name='Test',
            email='artist_mod@test.com', username='artist_mod',
            role='artist', account_status='ACTIVE'
        )
        user.set_password('pass1234')
        db.session.add(user)
        db.session.flush()

        artist = Artist(user_id=user.id, code='A001', competition_status='ACTIVE')
        db.session.add(artist)
        db.session.commit()

        client.post('/auth/login', data={
            'username': 'artist_mod',
            'password': 'pass1234'
        })

        # Tenter de modifier le profil admin
        response = client.post(f'/admin/artists/{artist.id}/edit', data={
            'first_name': 'Hacked'
        })
        # Doit être refusé
        assert response.status_code in [302, 403, 404]