from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re

class User(db.Model):
    """Modèle Utilisateur - Sécurisé"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='artist')
    account_status = db.Column(db.String(20), nullable=False, default='ACTIVE')
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    artist_profile = db.relationship('Artist', backref='user', uselist=False)
    jury_assignments = db.relationship('Assignment', backref='evaluator', lazy='dynamic',
                                      foreign_keys='Assignment.evaluator_user_id')
    scores_given = db.relationship('Score', backref='evaluator', lazy='dynamic')
    comments_given = db.relationship('Comment', backref='jury', lazy='dynamic')
    
    def set_password(self, password):
        """Hachage sécurisé du mot de passe"""
        if len(password) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Vérification sécurisée du mot de passe"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_jury(self):
        return self.role == 'jury'
    
    def is_artist(self):
        return self.role == 'artist'
    
    def is_active_account(self):
        return self.account_status == 'ACTIVE'
    
    def is_locked(self):
        if self.locked_until and datetime.utcnow() < self.locked_until:
            return True
        return False
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

class Artist(db.Model):
    """Modèle Artiste"""
    __tablename__ = 'artists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.String(500))
    biography = db.Column(db.Text)
    photo = db.Column(db.String(255))
    competition_status = db.Column(db.String(20), nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    scores = db.relationship('Score', backref='artist', lazy='dynamic', cascade='all, delete-orphan')
    comments_received = db.relationship('Comment', backref='artist', lazy='dynamic', cascade='all, delete-orphan')
    
    def is_eliminated(self):
        return self.competition_status == 'ELIMINATED'
    
    def is_active_in_competition(self):
        return self.competition_status == 'ACTIVE'
    
    def __repr__(self):
        return f"<Artist {self.code} - {self.user.full_name()}>"

class CompetitionSession(db.Model):
    """Modèle Session de Compétition (Dimanche)"""
    __tablename__ = 'competition_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    assignments = db.relationship('Assignment', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    scores = db.relationship('Score', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    moments = db.relationship('Moment', backref='session', lazy='dynamic')
    
    # Contraintes
    __table_args__ = (
        db.UniqueConstraint('number', name='unique_session_number'),
        db.CheckConstraint('number BETWEEN 1 AND 6', name='check_session_number'),
        db.CheckConstraint("status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')", name='check_session_status'),
    )
    
    def __repr__(self):
        return f"<CompetitionSession {self.number} - {self.date}>"

class Criterion(db.Model):
    """Modèle Critère d'évaluation"""
    __tablename__ = 'criteria'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    max_score = db.Column(db.Integer, nullable=False, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    assignments = db.relationship('Assignment', backref='criterion', lazy='dynamic', cascade='all, delete-orphan')
    scores = db.relationship('Score', backref='criterion', lazy='dynamic')
    
    # Contrainte
    __table_args__ = (
        db.CheckConstraint('max_score = 10', name='check_max_score'),
    )
    
    def __repr__(self):
        return f"<Criterion {self.name}>"

class Assignment(db.Model):
    """Modèle Affectation (Critère -> Évaluateur)"""
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('competition_sessions.id', ondelete='CASCADE'), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey('criteria.id', ondelete='CASCADE'), nullable=False)
    evaluator_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Contrainte unique
    __table_args__ = (
        db.UniqueConstraint('session_id', 'criterion_id', 'evaluator_user_id', 
                           name='unique_assignment'),
    )
    
    def __repr__(self):
        return f"<Assignment Session {self.session.number} - {self.criterion.name}>"

class Score(db.Model):
    """Modèle Note"""
    __tablename__ = 'scores'
    
    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('competition_sessions.id', ondelete='CASCADE'), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey('criteria.id', ondelete='CASCADE'), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Contraintes - Ajout de evaluator_id dans l'unicité
    __table_args__ = (
        db.UniqueConstraint('artist_id', 'session_id', 'criterion_id', 'evaluator_id',
                           name='unique_score_per_evaluator'),
        db.CheckConstraint('score >= 0 AND score <= 10', name='check_score_range'),
    )
    
    def __repr__(self):
        return f"<Score {self.artist.code} - {self.criterion.name}: {self.score}>"

class Comment(db.Model):
    """Modèle Commentaire"""
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    jury_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('competition_sessions.id', ondelete='CASCADE'), nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Comment from {self.jury.full_name()}>"

class Sponsor(db.Model):
    """Modèle Sponsor"""
    __tablename__ = 'sponsors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    logo = db.Column(db.String(255), nullable=False)
    website = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Sponsor {self.name}>"

class Moment(db.Model):
    """Modèle Moment Fort"""
    __tablename__ = 'moments'
    
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(500))
    session_id = db.Column(db.Integer, db.ForeignKey('competition_sessions.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Moment {self.id}>"

class ContactMessage(db.Model):
    """Modèle pour les messages de contact"""
    __tablename__ = 'contact_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='NEW')  # NEW, READ, REPLIED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ContactMessage from {self.first_name} {self.last_name}>"
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"