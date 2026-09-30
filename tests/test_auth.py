"""
Tests d'authentification
"""
import pytest
from app import db
from app.models import User


def test_successful_login(client, init_database):
    """Test de connexion réussie"""
    response = client.post('/auth/login', data={
        'username': 'admintest',
        'password': 'password123'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Bienvenue' in response.data or b'bienvenue' in response.data


def test_failed_login(client, init_database):
    """Test de connexion échouée"""
    response = client.post('/auth/login', data={
        'username': 'admintest',
        'password': 'wrongpassword'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert (b'incorrect' in response.data.lower() or
            b'erreur' in response.data.lower())


def test_logout(client, init_database):
    """Test de déconnexion"""
    # 1. Connexion préalable
    client.post('/auth/login', data={
        'username': 'admintest',
        'password': 'password123'
    })

    # 2. Essayer GET d'abord
    response = client.get('/auth/logout', follow_redirects=True)

    # 3. Si 405 (Method Not Allowed), essayer POST
    if response.status_code == 405:
        response = client.post('/auth/logout', follow_redirects=True)

    # 4. Vérifier le résultat
    assert response.status_code == 200