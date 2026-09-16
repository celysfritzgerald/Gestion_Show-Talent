import os
import getpass

from app import create_app, db
from app.models import User


def create_admin():
    app = create_app(
        os.environ.get("FLASK_ENV", "development")
    )

    with app.app_context():

        print("\n=== CRÉATION D'UN NOUVEL ADMINISTRATEUR ===\n")

        # Récupération des informations
        username = input("Nom d'utilisateur admin: ").strip()
        email = input("Email admin: ").strip().lower()
        first_name = input("Prénom: ").strip()
        last_name = input("Nom: ").strip()

        password = getpass.getpass("Mot de passe: ")
        confirmation = getpass.getpass(
            "Confirmer le mot de passe: "
        )

        # Validation des champs obligatoires
        if not all([
            username,
            email,
            first_name,
            last_name,
            password
        ]):
            raise SystemExit(
                "Erreur : tous les champs sont obligatoires."
            )

        # Validation du mot de passe
        if password != confirmation:
            raise SystemExit(
                "Erreur : les mots de passe ne correspondent pas."
            )

        if len(password) < 8:
            raise SystemExit(
                "Erreur : le mot de passe doit contenir "
                "au moins 8 caractères."
            )

        # Vérification du username et de l'email
        existing_user = User.query.filter(
            (User.username == username) |
            (User.email == email)
        ).first()

        if existing_user:
            raise SystemExit(
                "Erreur : ce nom d'utilisateur ou cet email "
                "est déjà utilisé."
            )

        # Désactivation des anciens administrateurs
        old_admins = User.query.filter_by(
            role="admin",
            account_status="ACTIVE"
        ).all()

        for old_admin in old_admins:
            old_admin.account_status = "INACTIVE"

        if old_admins:
            print(
                f"{len(old_admins)} ancien(s) "
                "administrateur(s) désactivé(s)."
            )

        # Création du nouvel administrateur
        new_admin = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            username=username,
            role="admin",
            account_status="ACTIVE"
        )

        # Hachage sécurisé du mot de passe
        new_admin.set_password(password)

        # Ajout du nouvel administrateur
        db.session.add(new_admin)

        try:
            # Enregistrement de toutes les modifications
            db.session.commit()

            print(
                "\n✓ Nouvel administrateur créé avec succès."
            )
            print(
                "✓ Les anciens administrateurs sont désactivés."
            )

        except Exception as error:
            # Annulation en cas d'erreur
            db.session.rollback()

            raise SystemExit(
                f"\nErreur lors de la création : {error}"
            )


if __name__ == "__main__":
    create_admin()
