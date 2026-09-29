from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="artist")
    account_status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    artist_profile = db.relationship("Artist", backref="user", uselist=False, cascade="all, delete-orphan")
    jury_assignments = db.relationship("Assignment", backref="evaluator", lazy="dynamic", foreign_keys="Assignment.evaluator_user_id")
    scores_given = db.relationship("Score", backref="evaluator", lazy="dynamic")
    comments_given = db.relationship("Comment", backref="jury", lazy="dynamic")

    __table_args__ = (
        db.CheckConstraint("role IN ('admin', 'jury', 'artist')", name="check_user_role"),
        db.CheckConstraint("account_status IN ('ACTIVE', 'INACTIVE')", name="check_account_status"),
        db.CheckConstraint("login_attempts >= 0", name="check_login_attempts"),
    )

    def set_password(self, password):
        if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
            raise ValueError("Le mot de passe doit contenir entre 8 et 128 caractères")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash or not isinstance(password, str):
            return False
        try:
            return check_password_hash(self.password_hash, password)
        except ValueError:
            return False

    def is_admin(self): return self.role == "admin"
    def is_jury(self): return self.role == "jury"
    def is_artist(self): return self.role == "artist"
    def is_active_account(self): return self.account_status == "ACTIVE"
    def is_locked(self): return bool(self.locked_until and datetime.utcnow() < self.locked_until)
    def full_name(self): return f"{self.first_name} {self.last_name}"
    def __repr__(self): return f"<User {self.username} ({self.role})>"


class Artist(db.Model):
    __tablename__ = "artists"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    address = db.Column(db.String(500))
    biography = db.Column(db.Text)
    photo = db.Column(db.String(255))
    competition_status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    scores = db.relationship("Score", backref="artist", lazy="dynamic", cascade="all, delete-orphan")
    comments_received = db.relationship("Comment", backref="artist", lazy="dynamic", cascade="all, delete-orphan")
    __table_args__ = (db.CheckConstraint("competition_status IN ('ACTIVE', 'ELIMINATED')", name="check_competition_status"),)
    def is_eliminated(self): return self.competition_status == "ELIMINATED"
    def is_active_in_competition(self): return self.competition_status == "ACTIVE"
    def __repr__(self): return f"<Artist {self.code} - {self.user.full_name()}>"


class CompetitionSession(db.Model):
    __tablename__ = "competition_sessions"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    assignments = db.relationship("Assignment", backref="session", lazy="dynamic", cascade="all, delete-orphan")
    scores = db.relationship("Score", backref="session", lazy="dynamic", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="session", lazy="dynamic", cascade="all, delete-orphan")
    moments = db.relationship("Moment", backref="session", lazy="dynamic")
    __table_args__ = (
        db.UniqueConstraint("number", name="unique_session_number"),
        db.CheckConstraint("number BETWEEN 1 AND 6", name="check_session_number"),
        db.CheckConstraint("status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')", name="check_session_status"),
    )


class Criterion(db.Model):
    __tablename__ = "criteria"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    max_score = db.Column(db.Integer, nullable=False, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    assignments = db.relationship("Assignment", backref="criterion", lazy="dynamic", cascade="all, delete-orphan")
    scores = db.relationship("Score", backref="criterion", lazy="dynamic")
    __table_args__ = (db.CheckConstraint("max_score = 10", name="check_max_score"),)


class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("competition_sessions.id", ondelete="CASCADE"), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey("criteria.id", ondelete="CASCADE"), nullable=False)
    evaluator_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("session_id", "criterion_id", name="unique_assignment_per_criterion"),)


class Score(db.Model):
    __tablename__ = "scores"
    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("competition_sessions.id", ondelete="CASCADE"), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey("criteria.id", ondelete="CASCADE"), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("artist_id", "session_id", "criterion_id", name="unique_score"),
        db.CheckConstraint("score >= 0 AND score <= 10", name="check_score_range"),
    )


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    jury_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("competition_sessions.id", ondelete="CASCADE"), nullable=False)
    comment = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("jury_id", "artist_id", "session_id", name="unique_comment"),)


class Sponsor(db.Model):
    __tablename__ = "sponsors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    logo = db.Column(db.String(255), nullable=False)
    website = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Moment(db.Model):
    __tablename__ = "moments"
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(500))
    session_id = db.Column(db.Integer, db.ForeignKey("competition_sessions.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="NEW")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.CheckConstraint("status IN ('NEW', 'READ', 'REPLIED')", name="check_contact_status"),)
    def full_name(self): return f"{self.first_name} {self.last_name}"


class Lyric(db.Model):
    """Modèle Paroles de chanson — Totalement indépendant"""
    __tablename__ = "lyrics"

    id = db.Column(db.Integer, primary_key=True)
    artist_name = db.Column(db.String(150), nullable=False)      # Nom saisi manuellement
    artist_code = db.Column(db.String(20), nullable=False)       # Code saisi manuellement
    artist_photo = db.Column(db.String(255))                     # Photo uploadée
    song_title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False, index=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint("view_count >= 0", name="check_view_count"),
    )

    def __repr__(self):
        return f"<Lyric {self.song_title} - {self.artist_name}>"