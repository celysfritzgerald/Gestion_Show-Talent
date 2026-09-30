"""
Configuration centralisée pour tous les tests
"""
import os
import pytest
from app import create_app, db as _db


# ============================================================
# FIXTURE APP
# ============================================================
@pytest.fixture(scope='session')
def app():
    """Crée l'application en mode test."""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test-secret-key-32-chars-minimum!!'
    os.environ['CSRF_SECRET_KEY'] = 'test-csrf-key-32-chars-minimum!!!!'

    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['UPLOAD_FOLDER'] = app.config.get('UPLOAD_FOLDER', 'uploads')

    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_path, exist_ok=True)

    with app.app_context():
        yield app


# ============================================================
# FIXTURE DB
# ============================================================
@pytest.fixture(scope='function')
def db(app):
    """Crée une base de données propre pour chaque test."""
    # ✅ Importer UNIQUEMENT les modèles présents dans app/models.py
    from app.models import (
        User, Artist, CompetitionSession, Criterion, Assignment, Score,
        Comment, Sponsor, Moment, ContactMessage, Lyric,
        VoteConfig, VoteSession, PublicVote,
        Poll, PollOption, PollVote,
    )

    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


# ============================================================
# FIXTURE CLIENT
# ============================================================
@pytest.fixture(scope='function')
def client(app, db):
    """Client HTTP de test."""
    return app.test_client()


# ============================================================
# FIXTURES DE DONNÉES
# ============================================================
@pytest.fixture
def admin_user(db):
    """Utilisateur admin pour les tests."""
    from app.models import User

    user = User(
        first_name='Admin',
        last_name='Test',
        email='admin@test.com',
        username='admin_test',
        role='admin',
        account_status='ACTIVE'
    )
    user.set_password('admin123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def jury_user(db):
    """Utilisateur jury pour les tests."""
    from app.models import User

    user = User(
        first_name='Jury',
        last_name='Test',
        email='jury@test.com',
        username='jury_test',
        role='jury',
        account_status='ACTIVE'
    )
    user.set_password('jury123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def artist_user(db):
    """Utilisateur artiste avec profil."""
    from app.models import User, Artist

    user = User(
        first_name='Artist',
        last_name='Test',
        email='artist@test.com',
        username='artist_test',
        role='artist',
        account_status='ACTIVE'
    )
    user.set_password('artist123')
    db.session.add(user)
    db.session.flush()

    artist = Artist(
        user_id=user.id,
        code='ART001',
        competition_status='ACTIVE'
    )
    db.session.add(artist)
    db.session.commit()
    return user


@pytest.fixture
def vote_session(db):
    """Soirée de vote pour les tests."""
    from app.models import VoteSession

    session = VoteSession(
        number=1,
        title="Test Soirée 1",
        is_open=True
    )
    db.session.add(session)
    db.session.commit()
    return session


@pytest.fixture
def vote_config(db):
    """Config de vote pour les tests."""
    from app.models import VoteConfig

    config = VoteConfig(
        mode="PER_SESSION",
        is_enabled=True
    )
    db.session.add(config)
    db.session.commit()
    return config


@pytest.fixture
def init_database(db):
    """Ajoute un admin de test avec username='admintest'."""
    from app.models import User

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