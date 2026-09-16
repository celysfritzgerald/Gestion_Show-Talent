def test_password_hashing(app, db):
    from app.models import User
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
    from app.models import User
    admin = User(first_name='A', last_name='A', email='a@a.com', username='admin', role='admin')
    jury = User(first_name='J', last_name='J', email='j@j.com', username='jury', role='jury')
    artist = User(first_name='Ar', last_name='Ar', email='ar@ar.com', username='artist', role='artist')

    assert admin.is_admin() is True
    assert jury.is_jury() is True
    assert artist.is_artist() is True