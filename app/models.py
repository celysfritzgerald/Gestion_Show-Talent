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
        db.CheckConstraint(
            "role IN ('admin', 'jury', 'artist', 'observer')",
            name="check_user_role"
        ),
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

    def is_admin(self):    return self.role == "admin"
    def is_jury(self):     return self.role == "jury"
    def is_artist(self):   return self.role == "artist"
    def is_observer(self): return self.role == "observer"

    def is_active_account(self): return self.account_status == "ACTIVE"
    def is_locked(self):         return bool(self.locked_until and datetime.utcnow() < self.locked_until)

    def full_name(self): return f"{self.first_name} {self.last_name}"
    def __repr__(self):  return f"<User {self.username} ({self.role})>"


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
    __tablename__ = "lyrics"

    id = db.Column(db.Integer, primary_key=True)
    artist_name = db.Column(db.String(150), nullable=False)
    artist_code = db.Column(db.String(20), nullable=False)
    artist_photo = db.Column(db.String(255))
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


class VoteConfig(db.Model):
    """Configuration globale du vote — Mode flexible + personnalisation complète."""
    __tablename__ = "vote_configs"

    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(20), nullable=False, default="PER_SESSION")
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    closed_message = db.Column(db.String(300), default="Le vote du public est actuellement fermé.")

    # ─── Personnalisation de la page ───
    title = db.Column(db.String(200), default="Qui va gagner cette édition ?")
    subtitle = db.Column(db.String(300), default="Votez pour votre artiste préféré")
    cta_text = db.Column(db.String(100), default="Voter pour cet artiste")
    hero_image = db.Column(db.String(255))
    primary_color = db.Column(db.String(20), default="#facc15")

    # ─── Affichage ───
    show_results_live = db.Column(db.Boolean, default=True, nullable=False)
    show_vote_counts = db.Column(db.Boolean, default=True, nullable=False)
    show_percentages = db.Column(db.Boolean, default=True, nullable=False)
    show_progress_bars = db.Column(db.Boolean, default=True, nullable=False)
    show_ranking_badge = db.Column(db.Boolean, default=True, nullable=False)

    # ─── Validation ───
    require_first_name = db.Column(db.Boolean, default=True, nullable=False)
    require_last_name = db.Column(db.Boolean, default=True, nullable=False)
    max_votes_per_session = db.Column(db.Integer, default=1, nullable=False)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint("mode IN ('GLOBAL', 'PER_SESSION')", name="check_vote_mode"),
        db.CheckConstraint("max_votes_per_session >= 1 AND max_votes_per_session <= 10", name="check_max_votes"),
    )

    def __repr__(self):
        return f"<VoteConfig mode={self.mode} enabled={self.is_enabled}>"

class VoteSession(db.Model):
    __tablename__ = "vote_sessions"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False, unique=True, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    is_open = db.Column(db.Boolean, default=True, nullable=False, index=True)
    closed_message = db.Column(db.String(300), default="Le vote pour cette soirée est actuellement fermé.")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    votes = db.relationship('PublicVote', backref='session', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<VoteSession {self.number} - {self.title}>"


class PublicVote(db.Model):
    __tablename__ = "public_votes"

    id = db.Column(db.Integer, primary_key=True)
    voter_first_name = db.Column(db.String(100), nullable=False)
    voter_last_name = db.Column(db.String(100), nullable=False)
    voter_fingerprint = db.Column(db.String(64), nullable=False, index=True)
    voter_ip = db.Column(db.String(45))
    voter_user_agent = db.Column(db.String(255))
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("vote_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    mode = db.Column(db.String(20), nullable=False, default="PER_SESSION", index=True)
    edition = db.Column(db.String(20), nullable=False, default="4e", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('voter_fingerprint', 'session_id', name='unique_vote_per_session'),
        db.UniqueConstraint('voter_fingerprint', 'edition', name='unique_vote_per_edition'),
    )

    artist = db.relationship('Artist', backref=db.backref('public_votes', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<PublicVote {self.voter_first_name} {self.voter_last_name} → S{self.session_id} A{self.artist_id}>"


class FinanceCategory(db.Model):
    __tablename__ = "finance_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    type = db.Column(db.String(10), nullable=False, index=True)
    icon = db.Column(db.String(50), default='fa-tag')
    color = db.Column(db.String(20), default='#facc15')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint("type IN ('income', 'expense')", name="check_finance_type"),
    )


class FinanceTransaction(db.Model):
    __tablename__ = "finance_transactions"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(5), nullable=False, default='HTG')
    description = db.Column(db.String(500), nullable=False)
    source = db.Column(db.String(200))
    reference = db.Column(db.String(100))
    transaction_date = db.Column(db.Date, nullable=False, index=True, default=lambda: datetime.utcnow().date())
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = db.relationship('FinanceCategory', backref=db.backref('transactions', lazy='dynamic'))
    author = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.CheckConstraint("type IN ('income', 'expense')", name="check_transaction_type"),
        db.CheckConstraint("amount > 0", name="check_amount_positive"),
    )


class Poll(db.Model):
    __tablename__ = "polls"

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    allow_multiple = db.Column(db.Boolean, default=False, nullable=False)
    author_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    closes_at = db.Column(db.DateTime)

    options = db.relationship('PollOption', backref='poll', lazy='dynamic', cascade='all, delete-orphan')
    poll_votes = db.relationship('PollVote', backref='poll', lazy='dynamic', cascade='all, delete-orphan')


class PollOption(db.Model):
    __tablename__ = "poll_options"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    text = db.Column(db.String(200), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    option_votes = db.relationship('PollVote', backref='option', lazy='dynamic', cascade='all, delete-orphan')


class PollVote(db.Model):
    __tablename__ = "poll_votes"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = db.Column(db.Integer, db.ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False, index=True)
    voter_fingerprint = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('poll_id', 'voter_fingerprint', name='unique_vote_per_poll'),
    )


# ============================================================
# PERMISSIONS OBSERVATEUR — 100% CONFIGURABLE
# ============================================================

class ObserverPermission(db.Model):
    """
    Permissions granulaires pour chaque observateur.
    Une ligne par utilisateur observateur.
    """
    __tablename__ = "observer_permissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # ─── Sections activables ───
    artists  = db.Column(db.Boolean, default=False, nullable=False)
    juries   = db.Column(db.Boolean, default=False, nullable=False)
    ranking  = db.Column(db.Boolean, default=False, nullable=False)
    votes    = db.Column(db.Boolean, default=False, nullable=False)
    polls    = db.Column(db.Boolean, default=False, nullable=False)
    finance  = db.Column(db.Boolean, default=False, nullable=False)
    sponsors = db.Column(db.Boolean, default=False, nullable=False)
    lyrics   = db.Column(db.Boolean, default=False, nullable=False)
    moments  = db.Column(db.Boolean, default=False, nullable=False)
    messages = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref("observer_permission", uselist=False, cascade="all, delete-orphan")
    )

    SECTIONS = ('artists', 'juries', 'ranking', 'votes', 'polls',
                'finance', 'sponsors', 'lyrics', 'moments', 'messages')

    def has(self, section: str) -> bool:
        """Retourne True si la section est activée."""
        return bool(getattr(self, section, False))

    def enabled_sections(self) -> list:
        """Retourne la liste des sections activées."""
        return [s for s in self.SECTIONS if self.has(s)]

    def __repr__(self):
        return f"<ObserverPermission user_id={self.user_id}>"