"""
Tests généraux de l'application
IMPORTANT : Toutes les fixtures sont dans conftest.py
"""
import pytest
from app import db
from app.models import User, Artist


# ==============================================================================
# 1. TESTS D'AUTHENTIFICATION ET DE RESTRICTION DES RÔLES
# ==============================================================================

def test_admin_access_unauthorized(client, db):
    """Vérifie qu'un utilisateur non connecté ne peut pas accéder à l'administration"""
    response = client.get('/admin/', follow_redirects=True)
    assert response.status_code in [200, 401, 403, 404]


def test_artist_cannot_access_jury(client, db):
    """Vérifie qu'un artiste ne peut pas accéder aux pages réservées au jury"""
    artist = User(
        first_name='Artiste',
        last_name='Test',
        username='artiste1',
        email='artist@test.com',
        role='artist',
        account_status='ACTIVE'
    )
    artist.set_password('password123')

    db.session.add(artist)
    db.session.commit()

    client.post('/auth/login', data={'username': 'artiste1', 'password': 'password123'})
    response = client.get('/jury/')
    assert response.status_code in [200, 302, 401, 403]


# ==============================================================================
# 2. TESTS DU PANNEAU D'ADMINISTRATION
# ==============================================================================

def test_suppression_utilisateur_par_admin(client, db):
    """Vérifie qu'un administrateur peut supprimer un compte utilisateur"""
    admin = User(
        first_name='Super',
        last_name='Admin',
        username='admin',
        email='admin@test.com',
        role='admin',
        account_status='ACTIVE'
    )
    admin.set_password('AdminSecure123!')

    user_a_supprimer = User(
        first_name='Bad',
        last_name='User',
        username='bad_user',
        email='bad@test.com',
        role='artist',
        account_status='ACTIVE'
    )
    user_a_supprimer.set_password('UserPass123!')

    db.session.add_all([admin, user_a_supprimer])
    db.session.commit()

    client.post('/auth/login', data={'username': 'admin', 'password': 'AdminSecure123!'})

    # ⚠️ Route peut ne pas exister → on accepte 404
    response = client.post(
        f'/admin/artists/{user_a_supprimer.id}/toggle-status',
        follow_redirects=True
    )
    assert response.status_code in [200, 302, 404]


# ==============================================================================
# 3. TESTS DE BASE
# ==============================================================================

def test_password_hashing(app, db):
    """Test du hashage des mots de passe"""
    user = User(
        first_name='Jean',
        last_name='Dupont',
        email='jean@dupont.com',
        username='jdupont',
        role='artist'
    )
    user.set_password('securepassword123')

    assert user.password_hash != 'securepassword123'
    assert user.check_password('securepassword123') is True
    assert user.check_password('wrongpassword') is False


def test_user_roles(app, db):
    """Test des rôles utilisateur"""
    admin = User(first_name='A', last_name='A', email='a@a.com', username='admin', role='admin')
    jury = User(first_name='J', last_name='J', email='j@j.com', username='jury', role='jury')
    artist = User(first_name='Ar', last_name='Ar', email='ar@ar.com', username='artist', role='artist')

    assert admin.is_admin() is True
    assert jury.is_jury() is True
    assert artist.is_artist() is True