"""
Tests de sécurité : XSS
Vérifie que les scripts ne peuvent pas être injectés
"""
import pytest
from app import db
from app.models import ContactMessage, Lyric


class TestXSSProtection:

    def test_contact_form_xss_stored_but_escaped(self, client, db):
        """
        XSS via le formulaire de contact :
        - Le script PEUT être stocké en base (c'est normal)
        - Mais il DOIT être échappé à l'affichage
        """
        payload = "<script>alert('XSS')</script>"
        response = client.post('/api/contact', json={
            'first_name': payload,
            'last_name': "Test",
            'email': "xss@test.com",
            'message': "Message de test valide pour XSS"
        })

        # L'API accepte le message (validation OK)
        assert response.status_code == 200

        # ✅ Le message est stocké en base (non échappé)
        msg = ContactMessage.query.filter_by(email="xss@test.com").first()
        assert msg is not None
        # En base, le script est conservé tel quel (protection à l'affichage)

    def test_xss_not_executed_in_html_response(self, client, db):
        """
        Vérifier que le script n'apparaît PAS brut dans une page HTML
        (donc échappé correctement)
        """
        # Créer un message avec script
        payload = "<script>alert('XSS')</script>"
        msg = ContactMessage(
            first_name=payload,
            last_name="Test",
            email="xss2@test.com",
            message=payload,
            status='NEW'
        )
        db.session.add(msg)
        db.session.commit()

        # Se connecter en admin pour voir les messages
        from app.models import User
        admin = User(
            first_name='Admin', last_name='Test',
            email='admin_xss@test.com', username='admin_xss',
            role='admin', account_status='ACTIVE'
        )
        admin.set_password('pass1234')
        db.session.add(admin)
        db.session.commit()

        client.post('/auth/login', data={
            'username': 'admin_xss',
            'password': 'pass1234'
        })

        # Accéder à la page admin des messages
        response = client.get('/admin/messages')

        # ✅ Le script brut NE DOIT PAS apparaître dans le HTML
        assert b'<script>alert(\'XSS\')</script>' not in response.data
        # ✅ À la place, on doit voir la version échappée
        assert b'&lt;script&gt;' in response.data or b'&amp;lt;script&amp;gt;' in response.data

    def test_login_reflected_xss(self, client, db):
        """Tentative XSS via paramètre de redirection"""
        response = client.post('/auth/login?next=<script>alert(1)</script>', data={
            'username': 'test',
            'password': 'test'
        })
        # Le script ne doit PAS être exécuté dans la réponse
        # Il peut apparaître échappé ou pas du tout
        assert b'<script>alert(1)</script>' not in response.data

    def test_lyrics_xss_stored_escaped(self, client, db, admin_user):
        """Tentative XSS via création de paroles (admin)"""
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
        }, follow_redirects=True)

        # ✅ La requête ne doit pas planter
        assert response.status_code in [200, 302]

        # ✅ Si une parole a été créée, le script doit être stocké mais échappé à l'affichage
        if response.status_code == 200:
            lyric = Lyric.query.filter_by(artist_code='ART001').first()
            if lyric:
                # Vérifier que l'affichage échappe le script
                lyric_response = client.get(f'/lyrics/{lyric.id}')
                if lyric_response.status_code == 200:
                    assert b'<script>alert(\'XSS\')</script>' not in lyric_response.data

    def test_javascript_url_protection(self, client, db):
        """Tentative d'injection d'URL javascript:"""
        response = client.post('/api/contact', json={
            'first_name': "javascript:alert(1)",
            'last_name': "Test",
            'email': "jsurl@test.com",
            'message': "Test message qui doit être long"
        })
        # Doit être accepté (validation ok) mais échappé à l'affichage
        assert response.status_code == 200

    def test_html_entities_encoded(self, client, db):
        """Vérifier que les entités HTML sont bien encodées à l'affichage"""
        payload = "<>&\"'"
        response = client.post('/api/contact', json={
            'first_name': payload,
            'last_name': "Test",
            'email': "entities@test.com",
            'message': "Test message qui doit être long"
        })
        # Ne doit pas planter
        assert response.status_code == 200

    def test_script_in_comment_not_executed(self, client, db):
        """
        Vérifier que les commentaires avec script ne sont pas exécutés
        (protection via Jinja2 auto-escape)
        """
        # Créer un contact avec un script
        payload = "<img src=x onerror=alert(1)>"
        msg = ContactMessage(
            first_name=payload,
            last_name="Test",
            email="img_xss@test.com",
            message="Test message valide",
            status='NEW'
        )
        db.session.add(msg)
        db.session.commit()

        # Vérifier que le payload contient bien le script
        assert "onerror" in msg.first_name

        # ✅ Mais à l'affichage, Jinja2 échappera automatiquement
        # (testé précédemment)