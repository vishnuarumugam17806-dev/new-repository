"""
SMART DB — Pytest Conftest
Configures Flask app testing instance with an in-memory SQLite database.
SQL Server is bypassed using an in-memory SQLite URI for unit tests.
"""
import os
import pytest

# Override database URI BEFORE app.py imports config (must be done at module level)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app import app as flask_app
from models import db as _db

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_ENGINE_OPTIONS": {}
    })
    
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db(app):
    return _db
