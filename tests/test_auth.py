import pytest

def test_successful_login(client, init_database):
    response = client.post('/auth/login', data={
        'username': 'admintest',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Bienvenue' in response.data

def test_failed_login(client, init_database):
    response = client.post('/auth/login', data={
        'username': 'admintest',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'incorrect' in response.data

def test_logout(client, init_database):
    # Connexion préalable
    client.post('/auth/login', data={
        'username': 'admintest',
        'password': 'password123'
    })
    
    # Itilize client.post paske wout logout ou a mande yon POST[cite: 13]
    response = client.post('/auth/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b'Au revoir' in response.data