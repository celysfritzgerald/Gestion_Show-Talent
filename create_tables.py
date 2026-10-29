import os
from app import create_app, db

app = create_app(os.environ.get('FLASK_ENV', 'production'))

with app.app_context():
    # Crée toutes les tables qui n'existent pas encore
    db.create_all()
    print("✅ Toutes les tables ont été créées avec succès (ou existaient déjà).")