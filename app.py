"""
DB VITHRA — AI-Powered Universal Database & Data Management Platform
Main Flask application entry point.
"""
import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user

# ── Load env & config ──────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()
import config as cfg

# ── Flask App Initialization ──────────────────────────────────────────────────
app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.secret_key = cfg.SECRET_KEY

app.config['SQLALCHEMY_DATABASE_URI']        = cfg.DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS']      = {'pool_pre_ping': True}

# ── Database & Models ─────────────────────────────────────────────────────────
from models import (
    db, User, SharedDatabase, DownloadLog, DatabaseInstance
)
db.init_app(app)

# ── Flask-Login Setup ─────────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ── Register Blueprints ───────────────────────────────────────────────────────
from blueprints.auth import auth_bp
from blueprints.generator import generator_bp
from blueprints.marketplace import marketplace_bp
from blueprints.analytics import analytics_bp
from blueprints.api import api_bp
from blueprints.crud import crud_bp

app.register_blueprint(auth_bp)
app.register_blueprint(generator_bp)
app.register_blueprint(marketplace_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(api_bp)
app.register_blueprint(crud_bp)


# ── Home Landing Route ────────────────────────────────────────────────────────
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return render_template('login.html', active_tab='register')


# ── Favicon Handlers ──────────────────────────────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return '', 204


# ── Application Context Database Bootstrap ───────────────────────────────────
with app.app_context():
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if 'mssql' in db_uri:
            from services.sqlserver_service import SqlServerService
            SqlServerService.init_system_db()
        db.create_all()

        # Dynamic safe schema migration for existing SQLite / Postgres / MySQL databases
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        if 'users' in table_names:
            user_cols = [c['name'] for c in inspector.get_columns('users')]
            if 'full_name' not in user_cols:
                try:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(120);"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    try:
                        db.session.execute(text("ALTER TABLE users ADD full_name VARCHAR(120);"))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

        if 'shared_databases' in table_names:
            sd_cols = [c['name'] for c in inspector.get_columns('shared_databases')]
            if 'database_type' not in sd_cols:
                try:
                    db.session.execute(text("ALTER TABLE shared_databases ADD COLUMN database_type VARCHAR(50) DEFAULT 'sqlserver';"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    try:
                        db.session.execute(text("ALTER TABLE shared_databases ADD database_type VARCHAR(50) DEFAULT 'sqlserver';"))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
    except Exception as boot_err:
        app.logger.warning(f"Database bootstrap notice: {boot_err}")


# ── Main Entry ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=cfg.DEBUG, host='0.0.0.0', port=cfg.PORT)

