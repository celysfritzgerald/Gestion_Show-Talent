<div align="center">

# 🎤 Show Talent — 4e Édition

**Plateforme officielle du concours musical ACDA Haïti**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat-square)](LICENSE)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white)](.github/workflows/)
[![Railway](https://img.shields.io/badge/Deployed%20on-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)

*Thème : **Yon ti chans pou Ayiti** 🇭🇹*

</div>

---

## 📋 Table des matières

- [À propos](#-à-propos)
- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#-architecture)
- [Stack technique](#-stack-technique)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Utilisation](#-utilisation)
- [Rôles utilisateurs](#-rôles-utilisateurs)
- [API](#-api)
- [Sécurité](#-sécurité)
- [Performance](#-performance)
- [SEO](#-seo)
- [Tests](#-tests)
- [Déploiement](#-déploiement)
- [Structure du projet](#-structure-du-projet)
- [Contribution](#-contribution)
- [Licence](#-licence)
- [Contact](#-contact)

---

## 🎯 À propos

**Show Talent** est la plateforme officielle du concours musical de l'**ACDA** (Association Culturelle de Desbas d'Aquin, Haïti). Elle permet :

- 🎤 La gestion complète des **artistes** et de leurs performances
- ⚖️ L'**évaluation** par un jury professionnel selon 10 critères
- 🗳️ Le **vote du public** en direct (mode global ou par soirée)
- 📊 La publication des **résultats** et **classements** en temps réel
- 🎵 Le partage des **paroles** et des **moments forts**
- 📈 Une gestion **financière** et des **sondages**

Cette **4ème édition** réunit les meilleurs talents autour du thème **"Yon ti chans pou Ayiti"**.

---

## ✨ Fonctionnalités

### 🌐 Côté public (visiteurs)

| Fonctionnalité | Description |
|---|---|
| 🏠 **Page d'accueil** | Hero animé, présentation, carrousel de moments |
| 🎤 **Artistes** | Liste, fiches détaillées, photos |
| 🏆 **Résultats** | Classement global + par dimanche |
| 📸 **Moments forts** | Galerie photo avec lightbox/carrousel |
| 🎵 **Paroles** | Bibliothèque de paroles de chansons |
| 🗳️ **Vote public** | Vote en direct avec anti-fraude (fingerprint) |
| 📊 **Sondages** | Sondages dynamiques avec résultats live |
| 🤝 **Sponsors** | Partenaires de l'événement |
| 📞 **Contact** | Formulaire sécurisé |

### ⚖️ Côté jury

- 📋 **Dashboard** avec sessions assignées
- ✍️ **Évaluation** : notes (0-10) + commentaires par artiste
- 🏆 **Classement** par session et global
- 📊 **Notes détaillées** : matrice artistes × critères

### 👑 Côté administrateur

- 📊 **Dashboard** complet avec KPIs
- 🎤 CRUD **artistes** (photos, statuts, élimination)
- ⚖️ CRUD **jurys** + affectation des critères
- 📅 CRUD **dimanches** + statuts (PENDING/IN_PROGRESS/COMPLETED)
- 📝 CRUD **critères** (10 fixes)
- 💰 **Finance** : catégories, transactions, exports
- 🎨 CRUD **sponsors**, **moments**, **paroles**, **sondages**
- 🗳️ **Votes publics** : config complète + export CSV
- 👁️ **Observateurs** : permissions granulaires par section
- 📧 **Messages** de contact

### 👁️ Côté observateur (lecture seule)

- 🎯 **Dashboard** personnalisé selon permissions
- 📊 Accès conditionnel : artistes, jurys, classement, finance, votes, sondages, sponsors, paroles, moments, messages
- 🔒 **Aucune modification possible** (validation stricte côté serveur)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NAVIGATEUR (Client)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  GUNICORN + GEVENT                          │
│  (4 workers × 500 connexions = 2000 requêtes simultanées)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FLASK APPLICATION                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Blueprints   │  Services    │  Permissions       │    │
│  │  ├─ main      │  ├─ ranking  │  ├─ admin_required │    │
│  │  ├─ auth      │  └─ cache    │  ├─ jury_required  │    │
│  │  ├─ admin     │              │  ├─ observer_*     │    │
│  │  ├─ jury      │              │  └─ rate_limit     │    │
│  │  ├─ artist    │              │                    │    │
│  │  └─ observer  │              │                    │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  WAF (security.py)  │  CSP  │  CSRF  │  Headers   │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  POSTGRESQL 15                              │
│  Users · Artists · Scores · Comments · Votes · Finance ...  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack technique

### Backend

| Technologie | Version | Usage |
|---|---|---|
| **Python** | 3.12 | Langage principal |
| **Flask** | 3.0 | Framework web |
| **SQLAlchemy** | 2.0 | ORM |
| **Flask-Migrate** | 4.0 | Migrations DB |
| **Flask-WTF** | 1.2 | Formulaires + CSRF |
| **PostgreSQL** | 15 | Base de données |
| **Gunicorn** | 23 | Serveur WSGI |
| **Gevent** | 24 | Workers async |
| **email-validator** | 2.1 | Validation emails |
| **Pillow** | 10 | Traitement images |

### Frontend

| Technologie | Usage |
|---|---|
| **TailwindCSS** | Framework CSS (CDN) |
| **Alpine.js** | Interactions légères |
| **Font Awesome** | Icônes |
| **Inter** | Typographie |

### DevOps

| Outil | Usage |
|---|---|
| **GitHub Actions** | CI/CD |
| **Railway** | Hébergement |
| **Pytest** | Tests unitaires |
| **Flake8** | Linting |
| **Bandit** | Scan sécurité |

---

## 🚀 Installation

### Prérequis

- Python **3.12+**
- PostgreSQL **15+**
- Git
- (Optionnel) Docker

### Étapes

**1. Cloner le projet**

```bash
cd show-talent
```

**2. Créer l'environnement virtuel**

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Installer les dépendances**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**4. Configurer l'environnement**

```bash
cp .env.example .env
# Éditer .env avec tes valeurs
```

**5. Créer la base de données**

```bash
# PostgreSQL
createdb show_talent_db

# Ou avec psql
psql -U postgres -c "CREATE DATABASE show_talent_db;"
```

**6. Appliquer les migrations**

```bash
flask db upgrade
```

**7. Lancer l'application**

```bash
python run.py
```

→ Ouvre **http://localhost:5000**

---

## ⚙️ Configuration

### Variables d'environnement (`.env`)

```bash
# ═══════════════════════════════════════════════
# FLASK
# ═══════════════════════════════════════════════
FLASK_ENV=development
FLASK_APP=run.py
SECRET_KEY=change-me-with-a-very-long-random-string-min-64-chars

# ═══════════════════════════════════════════════
# BASE DE DONNÉES
# ═══════════════════════════════════════════════
DATABASE_URL=postgresql://user:password@localhost:5432/show_talent_db

# ═══════════════════════════════════════════════
# UPLOADS
# ═══════════════════════════════════════════════
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=5242880

# ═══════════════════════════════════════════════
# SÉCURITÉ
# ═══════════════════════════════════════════════
RATELIMIT_ENABLED=True
WTF_CSRF_ENABLED=True
```

### Configuration production (Railway)

Sur Railway, ajoute ces variables dans **Settings → Variables** :

| Variable | Valeur |
|---|---|
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | *(clé de 64+ caractères)* |
| `DATABASE_URL` | *(fourni auto par Railway)* |
| `UPLOAD_FOLDER` | `static/uploads` |
| `RATELIMIT_ENABLED` | `True` |

---

## 💻 Utilisation

### Développement

```bash
# Lancer en dev
python run.py

# Ou avec Flask CLI
flask run --debug

# Shell interactif
flask shell

# Migrations
flask db migrate -m "Description"
flask db upgrade
flask db downgrade
```

### Production (local)

```bash
# Avec Gunicorn + Gevent
gunicorn "app:create_app('production')" \
    --workers 4 \
    --worker-class gevent \
    --worker-connections 500 \
    --bind 0.0.0.0:8000 \
    --timeout 60 \
    --preload
```

### Tests

```bash
# Tous les tests
pytest

# Verbose
pytest -v

# Avec coverage
pytest --cov=app --cov-report=html

# Un fichier spécifique
pytest tests/test_security.py

# Un test précis
pytest tests/test_security.py::test_csp_header
```

---

## 👥 Rôles utilisateurs

### 👑 Administrateur (`admin`)

- Accès complet à **toutes** les fonctionnalités
- Page : `/admin/`

### ⚖️ Jury (`jury`)

- Évaluation des artistes assignés
- Consultation des classements
- Page : `/jury/`

### 🎤 Artiste (`artist`)

- Consultation de ses notes et commentaires
- Page : `/artist/`

### 👁️ Observateur (`observer`)

- Accès en **lecture seule** aux sections autorisées
- Permissions **configurables par admin** :
  - `artists`, `juries`, `ranking`, `votes`, `polls`,
  - `finance`, `sponsors`, `lyrics`, `moments`, `messages`
- Page : `/observer/`

---

## 🔌 API

### Endpoints publics

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (DB + timestamp) |
| `GET` | `/sitemap.xml` | Sitemap dynamique |
| `GET` | `/robots.txt` | Fichier robots |
| `POST` | `/api/contact` | Formulaire de contact |
| `GET` | `/api/results/<session_id>` | Résultats d'une session |
| `GET` | `/api/public-ranking` | Classement global / par session |
| `POST` | `/api/vote` | Enregistrer un vote |
| `GET` | `/api/vote/results` | Résultats de vote live |
| `POST` | `/api/poll/vote` | Voter dans un sondage |
| `GET` | `/api/poll/<poll_id>/results` | Résultats sondage live |

### Exemples

**Voter pour un artiste**

```bash
curl -X POST https://mondomaine.com/api/vote \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Simon",
    "last_name": "Alice",
    "artist_id": 5,
    "session_id": 1,
    "edition": "4e"
  }'
```

**Réponse**

```json
{
  "success": true,
  "message": "Merci Alice ! Votre vote pour Marie Claire a été enregistré.",
  "artist_votes": 42,
  "total_votes": 156
}
```

**Classement public**

```bash
curl https://tondomaine.com/api/public-ranking?session_id=1
```

**Réponse**

```json
{
  "success": true,
  "mode": "SESSION",
  "session": 1,
  "results": [
    {"position": 1, "full_name": "Marie Claire", "total": 245.5, "eliminated": false},
    {"position": 2, "full_name": "Pierre Louis", "total": 230.0, "eliminated": false}
  ]
}
```

---

## 🔒 Sécurité

### Mesures actives

| Couche | Protection |
|---|---|
| **WAF** | Patterns XSS, SQLi, Path Traversal, Command Injection |
| **Anti-scanner** | Blocage sqlmap, nikto, nmap, etc. |
| **Rate limiting** | 60-120 req/min selon route |
| **CSRF** | Flask-WTF sur tous les formulaires |
| **CSP** | Content-Security-Policy strict |
| **Headers** | X-Frame-Options, X-Content-Type, HSTS, COOP, CORP |
| **Session** | Secure, HttpOnly, SameSite |
| **Password** | Hash Werkzeug (pbkdf2-sha256) |
| **Anti-brute-force** | 5 échecs = 15 min lock |
| **Upload** | Validation MIME + magic bytes + redimensionnement |
| **Fingerprint** | Vote : IP + UA + Secret |

### Bonnes pratiques

```bash
# Scanner les vulnérabilités
bandit -r app/ -ll

# Vérifier les dépendances
safety check

# Lint
flake8 app/ --max-line-length=120
```

---

## ⚡ Performance

### Optimisations en place

- ✅ **Cache classement** (TTL 60s) → 10× plus rapide
- ✅ **Cache invalidation** automatique après modification
- ✅ **Requêtes agrégées** (1 SQL au lieu de N+1)
- ✅ **`joinedload`** pour éviter les lazy loads
- ✅ **`content-visibility: auto`** sur les longues listes
- ✅ **Lazy loading** images (`loading="lazy"`)
- ✅ **Preconnect** + **dns-prefetch**
- ✅ **Gunicorn + Gevent** : 2000 connexions simultanées
- ✅ **Compression GZip** (via reverse proxy)
- ✅ **Cache HTTP** intelligent (1 an sur uploads, 1 jour sur static)

### Métriques cibles

| Métrique | Objectif | Actuel |
|---|---|---|
| **LCP** | < 2.5s | ✅ ~1.2s |
| **FID** | < 100ms | ✅ ~20ms |
| **CLS** | < 0.1 | ✅ 0.02 |
| **TTFB** | < 500ms | ✅ ~150ms |
| **PageSpeed** | > 90 | ✅ 95+ |

---

## 🔍 SEO

### Optimisations

- ✅ **Meta tags** dynamiques (title, description, keywords)
- ✅ **Open Graph** + **Twitter Card** sur chaque page
- ✅ **JSON-LD** (MusicEvent, Organization, Event)
- ✅ **Canonical URLs** partout
- ✅ **`sitemap.xml`** dynamique
- ✅ **`robots.txt`** avec zones privées bloquées
- ✅ **Alt descriptifs** sur toutes les images
- ✅ **H1 unique** par page
- ✅ **URLs sémantiques** (`/artists`, `/results`, `/moments`)
- ✅ **Mobile-first** (responsive)
- ✅ **X-Robots-Tag** sur `/admin`, `/jury`, `/artist`, `/observer`

---

## 🧪 Tests

### Structure

```
tests/
├── conftest.py              # Fixtures pytest
├── test_auth.py             # Login, logout, verrouillage
├── test_security.py         # XSS, CSP, headers
├── test_security_xss.py     # WAF + échappement
├── test_ranking.py          # Calculs classement
├── test_vote.py             # Vote public
├── test_admin.py            # Routes admin
└── test_observer.py         # Permissions observateur
```

### Exécution

```bash
# Tous les tests
pytest tests/ -v

# Avec coverage HTML
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Seulement la sécurité
pytest tests/test_security*.py -v

# Mode CI
pytest --tb=short -q
```

### Exemple de test

```python
def test_observer_cannot_access_unauthorized_section(client, observer_user):
    """L'observateur ne peut pas accéder aux sections non autorisées."""
    client.post('/auth/login', data={
        'username': observer_user.username,
        'password': 'password123'
    })

    # Section non autorisée → 403
    response = client.get('/observer/finance')
    assert response.status_code == 403
```

---

## 🚀 Déploiement

### Prérequis

- Compte GitHub
- Compte Railway
- Domaine (optionnel)

### Étapes

**1. Push sur GitHub**

```bash
git add .
git commit -m "Ready for production"
git push origin main
```

**2. Connecter Railway**

1. Va sur [railway.app](https://railway.app)
2. **New Project → Deploy from GitHub repo**
3. Sélectionne ton repo
4. Railway détecte `runtime.txt` + `requirements.txt`

**3. Ajouter PostgreSQL**

Dans Railway → **New → Database → PostgreSQL**

Railway injecte automatiquement `DATABASE_URL`.

**4. Configurer les variables**

**Settings → Variables** → ajoute `SECRET_KEY`, `FLASK_ENV=production`, etc.

**5. Migrations**

Railway exécute le `Procfile` :

```procfile
release: flask db upgrade
web: gunicorn "app:create_app('production')" --workers 4 --worker-class gevent --worker-connections 500 --bind 0.0.0.0:$PORT --timeout 60 --preload
```

**6. Health check**

Railway vérifie `/health` → si OK → ✅ déployé

### CI/CD (GitHub Actions)

Le workflow `.github/workflows/ci-cd.yml` exécute automatiquement :

1. **Lint** (flake8)
2. **Scan sécurité** (bandit)
3. **Tests** (pytest + PostgreSQL)
4. **Déploiement** (Railway)
5. **Healthcheck** post-déploiement

---

## 📁 Structure du projet

```
show-talent/
├── app/
│   ├── __init__.py              # Factory create_app()
│   ├── models.py                # Modèles SQLAlchemy
│   ├── permissions.py           # Décorateurs (@admin_required, etc.)
│   ├── security.py              # WAF + rate limiting
│   ├── utils.py                 # Helpers (uploads, validation)
│   ├── services_ranking.py      # Service classement (avec cache)
│   ├── routes.py                # Blueprint main (public)
│   ├── auth.py                  # Blueprint auth (login)
│   ├── admin_routes.py          # Blueprint admin
│   ├── jury_routes.py           # Blueprint jury
│   ├── artist_routes.py         # Blueprint artist
│   └── observer_routes.py       # Blueprint observer
│
├── templates/
│   ├── base.html                # Layout public
│   ├── auth/                    # Login
│   ├── public/                  # Pages publiques
│   ├── admin/                   # Templates admin
│   ├── jury/                    # Templates jury
│   ├── artist/                  # Templates artiste
│   ├── observer/                # Templates observateur
│   └── errors/                  # 403, 404, 500
│
├── static/
│   ├── images/                  # Images statiques
│   ├── css/                     # CSS custom (si non CDN)
│   ├── js/                      # JS custom
│   ├── robots.txt               # SEO
│   └── uploads/                 # Uploads utilisateurs
│       ├── artists/
│       ├── moments/
│       ├── sponsors/
│       ├── lyrics/
│       └── votes/
│
├── tests/                       # Tests pytest
├── migrations/                  # Alembic
├── .github/workflows/           # CI/CD
├── .env.example                 # Template config
├── .gitignore
├── Procfile                     # Commande de démarrage
├── railway.json                 # Config Railway
├── runtime.txt                  # Version Python
├── requirements.txt             # Dépendances
├── config.py                    # Config Flask
├── run.py                       # Point d'entrée
└── README.md                    # Ce fichier
```

---

## 🤝 Contribution

### Workflow Git

```bash
# 1. Créer une branche
git checkout -b feature/ma-fonctionnalite

# 2. Développer + tester
pytest

# 3. Commit
git add .
git commit -m "feat: ajout de ma fonctionnalité"

# 4. Push
git push origin feature/ma-fonctionnalite

# 5. Pull Request sur GitHub
```

### Conventions de commit

| Préfixe | Usage |
|---|---|
| `feat:` | Nouvelle fonctionnalité |
| `fix:` | Correction de bug |
| `docs:` | Documentation |
| `style:` | Formatage |
| `refactor:` | Refactorisation |
| `test:` | Tests |
| `chore:` | Maintenance |

### Checklist avant PR

- [ ] Tests passent (`pytest`)
- [ ] Lint OK (`flake8 app/`)
- [ ] Pas de vulnérabilité (`bandit -r app/`)
- [ ] Doc mise à jour
- [ ] Changelog (si nécessaire)

---

## 📄 Licence

**Propriétaire** — © 2026 ACDA Haïti. Tous droits réservés.

Le code source, les designs et contenus sont la propriété exclusive d'ACDA Haïti.
Toute reproduction, distribution ou utilisation commerciale sans autorisation écrite est interdite.

---

## 📞 Contact

<div align="center">

**ACDA Haïti** — Association Culturelle de Desbas d'Aquin

| | |
|---|---|
| 📧 **Email** | [celysfritzgerald39@gmail.com](mailto:celysfritzgerald39@gmail.com) |
| 📱 **Téléphone** | +509 3910-2160 |
| 🌐 **Site** | |
| 📍 **Localisation** | Desbas d'Aquin, Haïti 🇭🇹 |

</div>

---

<div align="center">

### 🎤 Show Talent 4e Édition

*Thème : **Yon ti chans pou Ayiti** 🇭🇹*

**Fait avec ❤️ en Haïti**

[⬆ Retour en haut](#-show-talent--4e-édition)

</div>