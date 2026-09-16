def test_index_page(client):
    response = client.get('/')
    assert response.status_code == 200

def test_about_page(client):
    response = client.get('/about')
    assert response.status_code == 200

def test_contact_api_success(client, db):
    response = client.post('/api/contact', json={
        'first_name': 'Alice',
        'last_name': 'Martin',
        'email': 'alice@example.com',
        'message': 'Ceci est un message de test suffisamment long.'
    })
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True

def test_contact_api_invalid(client):
    response = client.post('/api/contact', json={
        'first_name': 'Alice',
        'last_name': 'Martin',
        'email': 'invalid-email',
        'message': 'Court'
    })
    assert response.status_code == 400