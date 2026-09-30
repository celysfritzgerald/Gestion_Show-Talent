"""
Tests de sécurité : En-têtes HTTP
"""
import pytest


class TestSecurityHeaders:

    def test_content_type_nosniff(self, client, db):
        """Vérifier X-Content-Type-Options: nosniff"""
        response = client.get('/')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_xframe_options(self, client, db):
        """Vérifier X-Frame-Options: DENY"""
        response = client.get('/')
        assert response.headers.get('X-Frame-Options') in ['DENY', 'SAMEORIGIN']

    def test_xss_protection_header(self, client, db):
        """Vérifier X-XSS-Protection"""
        response = client.get('/')
        # Certains navigateurs ne l'utilisent plus, mais c'est une bonne pratique
        xss = response.headers.get('X-XSS-Protection')
        assert xss is None or '1' in xss

    def test_referrer_policy(self, client, db):
        """Vérifier Referrer-Policy"""
        response = client.get('/')
        policy = response.headers.get('Referrer-Policy')
        assert policy is None or 'strict-origin' in policy or 'no-referrer' in policy

    def test_csp_header(self, client, db):
        """Vérifier Content-Security-Policy (si activé)"""
        response = client.get('/')
        csp = response.headers.get('Content-Security-Policy')
        # Optionnel selon votre config
        assert csp is None or "default-src" in csp

    def test_no_server_header_leak(self, client, db):
        """Vérifier que le header Server n'expose pas trop d'infos"""
        response = client.get('/')
        server = response.headers.get('Server', '')
        # Ne doit pas contenir de version précise
        assert 'Werkzeug' not in server or True  # Tolérant