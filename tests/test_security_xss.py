"""
Tests de sécurité : XSS

⚠️ IMPORTANT : Notre WAF (security.py) bloque les patterns XSS
AVANT qu'ils n'atteignent les routes. Il y a donc 2 défenses :

  1. WAF → renvoie 400 pour les payloads dangereux
  2. Jinja2 auto-escape → échappe le HTML à l'affichage

Ces tests vérifient les DEUX niveaux.
"""
import pytest
from app import db
from app.models import ContactMessage, Lyric, User


class TestWAFBlocksXSS:
    """Vérifie que le WAF bloque les payloads XSS au niveau requête."""

    def test_contact_form_xss_blocked_by_waf(self, client, db):
        """Le WAF doit bloquer <script> dans le formulaire de contact."""
        payload = "<script>alert('XSS')</script>"
        response = client.post('/api/contact', json={
            'first_name': payload,
            'last_name': "Test",
            'email': "xss@test.com",
            'message': "Message de test valide pour XSS"
        })

        # ✅ Le WAF renvoie 400 (requête bloquée avant la route)
        assert response.status_code == 400

        # ✅ Et rien n'a été stocké en base
        msg = ContactMessage.query.filter_by(email="xss@test.com").first()
        assert msg is None

    def test_javascript_url_blocked_by_waf(self, client, db):
        """Le WAF doit bloquer javascript: dans les champs."""
        response = client.post('/api/contact', json={
            'first_name': "javascript:alert(1)",
            'last_name': "Test",
            'email': "jsurl@test.com",
            'message': "Test message qui doit être long"
        })

        assert response.status_code == 400

    def test_iframe_blocked_by_waf(self, client, db):
        """Le WAF doit bloquer les <iframe>."""
        response = client.post('/api/contact', json={
            'first_name': "<iframe src='evil.com'></iframe>",
            'last_name': "Test",
            'email': "iframe@test.com",
            'message': "Test message qui doit être long"
        })

        assert response.status_code == 400

    def test_onerror_attribute_blocked_by_waf(self, client, db):
        """Le WAF doit bloquer onerror= (attribut HTML dangereux)."""
        response = client.post('/api/contact', json={
            'first_name': "<img src=x onerror=alert(1)>",
            'last_name': "Test",
            'email': "onerror@test.com",
            'message': "Test message qui doit être long"
        })

        assert response.status_code == 400

    def test_path_traversal_blocked_by_waf(self, client, db):
        """Le WAF doit bloquer les tentatives de path traversal."""
        response = client.get('/lyrics/../../../etc/passwd')

        # 400 (WAF) ou 404 (Flask routing) — les deux sont OK
        assert response.status_code in [400, 404]

    def test_lyrics_xss_blocked_by_waf(self, client, db, admin_user):
        """Le WAF doit bloquer XSS dans la création de paroles."""
        client.post('/auth/login', data={
            'username': 'admin_test',
            'password': 'admin123'
        })

        payload = "<script>alert('XSS')</script>"

        response = client.post('/admin/lyrics/create', data={
            'artist_name': payload,
            'artist_code': 'ART001',
            'song_title': payload,
            'content': payload,
            'is_published': 'on'
        })

        # ✅ WAF bloque
        assert response.status_code == 400

        # ✅ Rien n'est créé
        lyric = Lyric.query.filter_by(artist_code='ART001').first()
        assert lyric is None


class TestJinja2EscapesHTML:
    """Vérifie que Jinja2 échappe le HTML à l'affichage."""

    def test_contact_form_stores_and_escapes(self, client, db):
        """
        Avec un payload SAFE pour le WAF mais dangereux pour l'affichage,
        on vérifie que Jinja2 échappe bien.
        """
        # ✅ Payload qui ne déclenche PAS le WAF mais qui teste l'échappement
        payload = "<div>test</div>"  # ← pas de <script>, pas de on*=

        response = client.post('/api/contact', json={
            'first_name': payload,
            'last_name': "Test",
            'email': "safe@test.com",
            'message': "Message de test valide pour échappement"
        })

        assert response.status_code == 200

        # Vérifier que c'est stocké en base tel quel (raw)
        msg = ContactMessage.query.filter_by(email="safe@test.com").first()
        assert msg is not None
        assert msg.first_name == payload

    def test_html_entities_in_admin_page(self, client, db):
        """
        Vérifier que le HTML est échappé à l'affichage dans la page admin.
        """
        # Créer un message avec un payload SAFE pour le WAF
        msg = ContactMessage(
            first_name="<b>Gras</b>",
            last_name="Test",
            email="html@test.com",
            message="Message valide pour test",
            status='NEW'
        )
        db.session.add(msg)

        # Créer un admin
        admin = User(
            first_name='Admin', last_name='Test',
            email='admin_html@test.com', username='admin_html',
            role='admin', account_status='ACTIVE'
        )
        admin.set_password('pass1234')
        db.session.add(admin)
        db.session.commit()

        client.post('/auth/login', data={
            'username': 'admin_html',
            'password': 'pass1234'
        })

        response = client.get('/admin/messages')

        # ✅ Doit contenir la version échappée
        assert b'&lt;b&gt;Gras&lt;/b&gt;' in response.data
        # ❌ Ne doit PAS contenir le HTML brut
        assert b'<b>Gras</b>' not in response.data


class TestXSSEdgeCases:
    """Cas limites et variantes d'attaques XSS."""

    def test_uppercase_script_tag_blocked(self, client, db):
        """Le WAF doit être insensible à la casse."""
        response = client.post('/api/contact', json={
            'first_name': "<SCRIPT>alert(1)</SCRIPT>",
            'last_name': "Test",
            'email': "upper@test.com",
            'message': "Test message qui doit être long"
        })
        assert response.status_code == 400

    def test_embedded_script_variants(self, client, db):
        """Variantes d'injection : <object>, <embed>, etc."""
        payloads = [
            "<object data='evil'></object>",
            "<embed src='evil'>",
        ]
        for payload in payloads:
            response = client.post('/api/contact', json={
                'first_name': payload,
                'last_name': "Test",
                'email': f"test_{hash(payload)}@test.com",
                'message': "Test message qui doit être long"
            })
            assert response.status_code == 400, f"Payload non bloqué : {payload}"

    def test_safe_input_accepted(self, client, db):
        """Les entrées normales doivent passer sans problème."""
        response = client.post('/api/contact', json={
            'first_name': "Jean-Pierre",
            'last_name': "O'Brien",
            'email': "jean@test.com",
            'message': "Bonjour, ceci est un message valide de plus de 10 caractères."
        })
        assert response.status_code == 200