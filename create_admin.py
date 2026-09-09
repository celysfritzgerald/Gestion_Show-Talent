from app import create_app, db
from app.models import User
import os

def create_admin():
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    
    with app.app_context():
        # Vérifier si un admin existe déjà
        admin_exists = User.query.filter_by(role='admin').first()
        
        if admin_exists:
            print(f"⚠️ Un admin existe déjà: {admin_exists.username}")
            print("   Pas besoin d'en créer un nouveau.")
            return
        
        # Créer l'admin
        admin = User(
            username='admin',
            email='admin@showtalent.com',
            first_name='Admin',
            last_name='Show Talent',
            role='admin',
            account_status='ACTIVE'
        )
        admin.set_password('admin123')
        
        db.session.add(admin)
        db.session.commit()
        
        print("✅ Admin créé avec succès!")
        print("   👤 Username: admin")
        print("   🔑 Password: admin123")
        print("   📧 Email: admin@showtalent.com")
        print("\n⚠️ CHANGEZ CE MOT DE PASSE APRÈS LA PREMIÈRE CONNEXION!")

if __name__ == '__main__':
    create_admin()