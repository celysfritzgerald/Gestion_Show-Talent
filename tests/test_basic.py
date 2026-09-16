import pytest

from app import create_app, db
from app.models import Artist, Assignment, CompetitionSession, Criterion, Score, User


def make_user(role, username):
    user = User(first_name="Test", last_name=role, email=f"{username}@example.com", username=username, role=role, account_status="ACTIVE")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.flush()
    return user


def test_app_starts():
    app = create_app("testing")
    assert app.config["TESTING"] is True


def test_password_hashing(app):
    with app.app_context():
        user = make_user("artist", "artist1")
        assert user.password_hash != "StrongPass123!"
        assert user.check_password("StrongPass123!")
        assert not user.check_password("wrong")


def test_role_protection(app, client):
    with app.app_context():
        user = make_user("artist", "artist2")
        user_id = user.id
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in (302, 403)


def test_score_nan_rejected(app, client):
    with app.app_context():
        jury = make_user("jury", "jury1")
        artist_user = make_user("artist", "artist3")
        artist = Artist(user_id=artist_user.id, code="ST-TEST", competition_status="ACTIVE")
        session_obj = CompetitionSession(number=1, date=__import__('datetime').date(2026, 11, 29), status="IN_PROGRESS")
        criterion = Criterion(name="Test criterion", max_score=10)
        db.session.add_all([artist, session_obj, criterion]); db.session.flush()
        db.session.add(Assignment(session_id=session_obj.id, criterion_id=criterion.id, evaluator_user_id=jury.id)); db.session.commit()
        jury_id=jury.id; artist_id=artist.id; session_id=session_obj.id; criterion_id=criterion.id
    with client.session_transaction() as sess: sess["user_id"] = jury_id
    r=client.post("/jury/api/save-score", json={"artist_id":artist_id,"session_id":session_id,"criterion_id":criterion_id,"score":"NaN"})
    assert r.status_code == 400


@pytest.fixture
def app():
    app=create_app("testing")
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()

