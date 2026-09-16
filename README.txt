# Show Talent - 4e Édition

Plateforme web pour le concours de chant Show Talent organisé par l'ACDA.

## 🎤 À propos

Show Talent est un concours de chant qui se déroule sur 6 dimanches. Cette plateforme permet de gérer les artistes, les jurys, les critères de notation, les résultats, les sponsors et les moments forts du concours.

## 🚀 Fonctionnalités

- Gestion complète des artistes (création, modification, activation/élimination)
- Gestion des jurys
- 10 critères de notation configurables
- Système d'affectation des critères aux jurys
- Notation sur 0-10 points
- Calcul automatique des totaux
- Classements par dimanche
- Espace artiste privé
- Gestion des sponsors
- Galerie des moments forts

## 🛠️ Technologies

- **Backend**: Python, Flask, SQLAlchemy
- **Frontend**: HTML5, Tailwind CSS
- **Base de données**: SQLite (dev), PostgreSQL (prod)
- **Déploiement**: Railway, Gunicorn

## 🔒 Sécurité

- Mots de passe hashés (Werkzeug)
- Protection CSRF (Flask-WTF)
- Rate Limiting
- Comptes verrouillés après 5 tentatives
- Upload sécurisé (validation MIME, taille, contenu)
- Headers de sécurité (CSP, HSTS, X-Frame-Options)
- Sessions sécurisées (HttpOnly, Secure, SameSite)
- Validation serveur de toutes les entrées
- Protection contre les injections SQL (SQLAlchemy)
- Protection contre XSS (Jinja2 auto-escape)

## 📦 Installation

### Prérequis

- Python 3.10+
- pip
- virtualenv (recommandé)

### Étapes

1. Cloner le dépôt:
```bash
git clone https://github.com/yourusername/show-talent.git
cd show-talent

SECURITE / PRODUCTION
- Ne jamais committer .env, credentials, DB ou venv.
- Créer l'administrateur avec: python create_admin.py
- En production, définir SECRET_KEY, CSRF_SECRET_KEY et DATABASE_URL PostgreSQL.
- Les uploads sont validés par extension + MIME + contenu réel + dimensions et noms UUID.
- Toutes les mutations sont protégées par CSRF.
- Les rôles sont contrôlés côté serveur.
- Les notes sont limitées à 0..10 et uniquement à l'évaluateur affecté.
- Utiliser HTTPS en production.
- Les fichiers uploads locaux nécessitent un stockage persistant en production.
