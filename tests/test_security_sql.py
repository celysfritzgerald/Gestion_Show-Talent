"""
Tests de sécurité : Injection SQL
Vérifie que l'application est protégée contre les injections SQL
"""
import pytest
from app import db
from app.models import User


class TestSQLInjection:

    def test_login_sql_injection_username(self, client, db):
        """Tentative d'injection SQL sur le login (username)"""
        response = client.post('/auth/login', data={
            'username': "' OR '1'='1",
            'password': "anything"
        }, follow_redirects=True)

        # Ne doit PAS connecter
        assert response.status_code == 200
        # Vérifier qu'on est toujours sur la page de login (pas de redirection vers dashboard)
        assert b'incorrect' in response.data.lower() or b'erreur' in response.data.lower()

    def test_login_sql_injection_password(self, client, db):
        """Tentative d'injection SQL sur le login (password)"""
        response = client.post('/auth/login', data={
            'username': "admin",
            'password': "' OR '1'='1"
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'incorrect' in response.data.lower() or b'erreur' in response.data.lower()

    def test_login_drop_table_attempt(self, client, db):
        """Tentative de DROP TABLE via login"""
        # Créer un user pour vérifier que la table existe toujours après
        user = User(
            first_name='Test',
            last_name='User',
            email='test@test.com',
            username='existing_user',
            role='artist',
            account_status='ACTIVE'
        )
        user.set_password('pass1234')
        db.session.add(user)
        db.session.commit()

        # Tentative d'injection
        response = client.post('/auth/login', data={
            'username': "existing_user'; DROP TABLE users; --",
            'password': "anything"
        }, follow_redirects=True)

        # Vérifier que la table users existe toujours
        with db.session.no_autoflush:
            user_count = User.query.count()
            assert user_count >= 1, "La table users a été supprimée par injection SQL!"

    def test_search_sql_injection(self, client, db):
        """Tentative d'injection SQL via recherche ou filtre"""
        # Tester via une URL avec paramètre
        response = client.get("/artists?search=' OR 1=1 --")
        # Ne doit pas planter
        assert response.status_code in [200, 400, 404]

    def test_url_sql_injection(self, client, db):
        """Injection SQL via paramètres URL"""
        response = client.get("/lyrics/1' OR '1'='1")
        assert response.status_code in [400, 404]

    def test_api_sql_injection(self, client, db):
        """Injection SQL via API"""
        response = client.post('/api/contact', json={
            'first_name': "'; DROP TABLE contact_messages; --",
            'last_name': "Test",
            'email': "test@test.com",
            'message': "Test message qui doit être long"
        })
        # L'API doit valider et insérer sans planter
        assert response.status_code in [200, 400]

        # Vérifier que la table existe toujours
        from app.models import ContactMessage
        count = ContactMessage.query.count()
        assert count >= 0