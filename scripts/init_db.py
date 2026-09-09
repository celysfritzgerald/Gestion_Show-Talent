#!/usr/bin/env python
"""
Script d'initialisation de la base de données
Crée les tables et un compte administrateur par défaut
"""
import os
import sys
from datetime import datetime

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, CompetitionSession, Criterion

def init_database():
    """Initialiser la base de données"""
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    
    with app.app_context():
        print("📊 Création des tables...")
        db.create_all()
        print("✅ Tables créées avec succès")
        
        # Créer un compte administrateur
        if not User.query.filter_by(role='admin').first():
            print("👤 Création du compte administrateur...")
            admin = User(
                username='admin',
                email='admin@showtalent.com',
                first_name='Admin',
                last_name='Show Talent',
                role='admin',
                account_status='ACTIVE'
            )
            admin.set_password('admin123')  # Changez ce mot de passe !
            db.session.add(admin)
            print("✅ Compte administrateur créé")
            print("   Username: admin")
            print("   Password: admin123 (À CHANGER!)")
        
        # Créer les 6 dimanches par défaut
        print("📅 Création des dimanches...")
        for i in range(1, 7):
            if not CompetitionSession.query.filter_by(number=i).first():
                session = CompetitionSession(
                    number=i,
                    date=datetime(2026, 9, 6 + (i-1)*7).date(),  # Dates approximatives
                    status='PENDING'
                )
                db.session.add(session)
        print("✅ 6 dimanches créés")
        
        # Créer les 10 critères par défaut
        print("📋 Création des critères...")
        default_criteria = [
            ("Technique vocale", "Qualité technique de la voix"),
            ("Interprétation", "Capacité à interpréter la chanson"),
            ("Présence scénique", "Charisme et présence sur scène"),
            ("Maîtrise du rythme", "Respect du rythme et du timing"),
            ("Justesse", "Précision des notes"),
            ("Originalité", "Originalité de l'interprétation"),
            ("Expression", "Capacité à transmettre des émotions"),
            ("Qualité vocale", "Timbre et qualité de la voix"),
            ("Contrôle vocal", "Maîtrise des techniques vocales"),
            ("Impact", "Impact global de la performance")
        ]
        
        for name, description in default_criteria:
            if not Criterion.query.filter_by(name=name).first():
                criterion = Criterion(
                    name=name,
                    description=description,
                    max_score=10
                )
                db.session.add(criterion)
        print("✅ 10 critères créés")
        
        # Commit final
        db.session.commit()
        
        print("\n✅ Base de données initialisée avec succès!")
        print(f"   Environnement: {os.environ.get('FLASK_ENV', 'development')}")
        print(f"   Base: {app.config['SQLALCHEMY_DATABASE_URI']}")

if __name__ == '__main__':
    init_database()