#!/usr/bin/env python

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask_migrate import upgrade
from app import create_app, db
from app.models import CompetitionSession, Criterion
from datetime import date


def init_database():
    app = create_app(os.environ.get("FLASK_ENV", "development"))
    with app.app_context():
        print("📊 Application des migrations...")
        upgrade()
        print("✅ Migrations appliquées")

        dates = [
            date(2026, 11, 29), date(2026, 12, 6), date(2026, 12, 13),
            date(2026, 12, 20), date(2026, 12, 27), date(2027, 1, 3),
        ]
        for number, session_date in enumerate(dates, start=1):
            if not CompetitionSession.query.filter_by(number=number).first():
                db.session.add(CompetitionSession(number=number, date=session_date, status="PENDING"))

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
            ("Impact", "Impact global de la performance"),
        ]
        for name, description in default_criteria:
            if not Criterion.query.filter_by(name=name).first():
                db.session.add(Criterion(name=name, description=description, max_score=10))

        db.session.commit()
        print("✅ Base initialisée. Créez l'administrateur avec: python create_admin.py")


if __name__ == "__main__":
    init_database()
