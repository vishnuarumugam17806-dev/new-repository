"""
SMART DB — SQLAlchemy Models
All database models for the full platform.
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


def _utcnow():
    """Return current UTC time (timezone-aware, Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class BaseModel(db.Model):
    __abstract__ = True
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ── Users ─────────────────────────────────────────────────────────────────────
class User(UserMixin, BaseModel):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), default='user')   # 'user' | 'admin'
    bio           = db.Column(db.Text, default='')
    avatar_color  = db.Column(db.String(20), default='#00f2fe')
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=_utcnow)
    last_login    = db.Column(db.DateTime, nullable=True)

    schemas   = db.relationship('SharedDatabase', backref='author', lazy='dynamic')
    ratings   = db.relationship('Rating',         backref='user',   lazy='dynamic')
    comments  = db.relationship('Comment',        backref='user',   lazy='dynamic')
    favorites = db.relationship('Favorite',       backref='user',   lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'


# ── Projects ──────────────────────────────────────────────────────────────────
class Project(BaseModel):
    __tablename__ = 'projects'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    industry    = db.Column(db.String(100), default='General')
    is_public   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=_utcnow)
    updated_at  = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    schemas = db.relationship('SharedDatabase', backref='project', lazy='dynamic')


# ── Schemas ───────────────────────────────────────────────────────────────────
class SharedDatabase(BaseModel):
    __tablename__    = 'shared_databases'
    id               = db.Column(db.Integer, primary_key=True)
    project_id       = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    project_name     = db.Column(db.String(200), nullable=False)
    requirements     = db.Column(db.Text, nullable=False)
    industry         = db.Column(db.String(100), default='General')
    tags             = db.Column(db.String(500), default='')

    # Core outputs
    sql_code         = db.Column(db.Text, nullable=False)
    normalized_sql   = db.Column(db.Text, nullable=True)
    nosql_schema     = db.Column(db.Text, nullable=True)   # JSON string

    # AI-generated artifacts
    er_diagram_mmd   = db.Column(db.Text, nullable=True)   # Mermaid source
    entities_json    = db.Column(db.Text, nullable=True)   # JSON string
    data_dictionary  = db.Column(db.Text, nullable=True)   # JSON string
    sample_data      = db.Column(db.Text, nullable=True)   # SQL INSERT statements
    api_docs         = db.Column(db.Text, nullable=True)   # JSON string
    improvements     = db.Column(db.Text, nullable=True)   # Text suggestions

    # Versioning
    version          = db.Column(db.Integer, default=1)
    is_public        = db.Column(db.Boolean, default=True)
    ai_generated     = db.Column(db.Boolean, default=False)

    # Stats
    likes_count      = db.Column(db.Integer, default=0)
    downloads_count  = db.Column(db.Integer, default=0)
    views_count      = db.Column(db.Integer, default=0)

    is_deployed      = db.Column(db.Boolean, default=False)
    deployed_to      = db.Column(db.String(255), nullable=True)

    created_at       = db.Column(db.DateTime, default=_utcnow)
    updated_at       = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    ratings   = db.relationship('Rating',        backref='schema', lazy='dynamic', cascade='all, delete-orphan')
    comments  = db.relationship('Comment',       backref='schema', lazy='dynamic', cascade='all, delete-orphan')
    versions  = db.relationship('SchemaVersion', backref='schema', lazy='dynamic', cascade='all, delete-orphan')
    favorites = db.relationship('Favorite',      backref='schema', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def avg_rating(self):
        ratings = self.ratings.all()
        if not ratings:
            return 0
        return round(sum(r.score for r in ratings) / len(ratings), 1)

    @property
    def tags_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()] if self.tags else []

    def __repr__(self):
        return f'<Schema {self.project_name}>'


# ── Schema Versions ───────────────────────────────────────────────────────────
class SchemaVersion(BaseModel):
    __tablename__    = 'schema_versions'
    id               = db.Column(db.Integer, primary_key=True)
    schema_id        = db.Column(db.Integer, db.ForeignKey('shared_databases.id'), nullable=False)
    version_number   = db.Column(db.Integer, nullable=False)
    sql_code         = db.Column(db.Text, nullable=False)
    er_diagram_mmd   = db.Column(db.Text, nullable=True)
    changes          = db.Column(db.Text, default='Initial version')
    created_at       = db.Column(db.DateTime, default=_utcnow)


# ── Ratings ───────────────────────────────────────────────────────────────────
class Rating(BaseModel):
    __tablename__ = 'ratings'
    id        = db.Column(db.Integer, primary_key=True)
    schema_id = db.Column(db.Integer, db.ForeignKey('shared_databases.id'), nullable=False)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    score     = db.Column(db.Integer, nullable=False)   # 1-5
    created_at = db.Column(db.DateTime, default=_utcnow)
    __table_args__ = (db.UniqueConstraint('schema_id', 'user_id', name='unique_rating'),)


# ── Comments ──────────────────────────────────────────────────────────────────
class Comment(BaseModel):
    __tablename__ = 'comments'
    id        = db.Column(db.Integer, primary_key=True)
    schema_id = db.Column(db.Integer, db.ForeignKey('shared_databases.id'), nullable=False)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author_name = db.Column(db.String(100), default='Anonymous')
    content   = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


# ── Industry Templates ────────────────────────────────────────────────────────
class IndustryTemplate(BaseModel):
    __tablename__   = 'industry_templates'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(200), nullable=False)
    category        = db.Column(db.String(100), nullable=False)   # Healthcare, Finance, etc.
    description     = db.Column(db.Text, default='')
    icon            = db.Column(db.String(50), default='🗄️')
    sql_code        = db.Column(db.Text, nullable=False)
    er_diagram_mmd  = db.Column(db.Text, nullable=True)
    requirements    = db.Column(db.Text, default='')
    tags            = db.Column(db.String(500), default='')
    downloads       = db.Column(db.Integer, default=0)
    is_featured     = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=_utcnow)


# ── Download Logs ─────────────────────────────────────────────────────────────
class DownloadLog(BaseModel):
    __tablename__ = 'download_logs'
    id            = db.Column(db.Integer, primary_key=True)
    schema_id     = db.Column(db.Integer, db.ForeignKey('shared_databases.id'), nullable=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address    = db.Column(db.String(45), default='')
    file_type     = db.Column(db.String(20), default='sql')   # sql | sqlite | nosql
    downloaded_at = db.Column(db.DateTime, default=_utcnow)


# ── Favorites ─────────────────────────────────────────────────────────────────
class Favorite(BaseModel):
    __tablename__ = 'favorites'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    schema_id  = db.Column(db.Integer, db.ForeignKey('shared_databases.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'schema_id', name='unique_favorite'),)


# ── Analytics Events ──────────────────────────────────────────────────────────
class AnalyticsEvent(BaseModel):
    __tablename__ = 'analytics_events'
    id         = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # generated|deployed|downloaded|viewed
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    schema_id  = db.Column(db.Integer, db.ForeignKey('shared_databases.id'), nullable=True)
    event_metadata = db.Column(db.Text, default='{}')   # JSON
    ip_address = db.Column(db.String(45), default='')
    created_at = db.Column(db.DateTime, default=_utcnow)
