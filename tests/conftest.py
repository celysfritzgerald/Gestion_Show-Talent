import pytest
from app import create_app, db as _db
from app.models import User, Artist, CompetitionSession, Criterion, Assignment

@pytest.fixture(scope='session')
def app():
    """Crée l'application en utilisant la configuration de test."""
    app = create_app('testing')  # Charge automatiquement TestingConfig (SQLite en mémoire, CSRF désactivé)
    
    with app.app_context():
        yield app

@pytest.fixture(scope='function')
def db(app):
    """Crée une base de données propre pour chaque test."""
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()

@pytest.fixture(scope='function')
def client(app, db):
    """Un client de test pour les requêtes HTTP."""
    return app.test_client()

@pytest.fixture
def init_database(db):
    """Ajoute des données initiales (rôles de base, etc.)."""
    admin = User(
        first_name='Admin',
        last_name='Test',
        email='admin@test.com',
        username='admintest',
        role='admin',
        account_status='ACTIVE'
    )
    admin.set_password('password123')
    db.session.add(admin)
    db.session.commit()
    return db