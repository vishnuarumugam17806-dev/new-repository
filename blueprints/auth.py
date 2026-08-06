"""
SMART DB — Authentication Blueprint
Handles user registration, login, logout, and profile management.
"""
import re
import bcrypt
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, SharedDatabase

auth_bp = Blueprint('auth', __name__)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('auth.register'))

        # Check existing user
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # Random beautiful avatar color for glassmorphism layout
        import random
        colors = ['#00f2fe', '#4facfe', '#ff0844', '#ffb199', '#f093fb', '#f5576c', '#b1f2ff', '#a8efff']
        avatar_color = random.choice(colors)

        new_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role='user',
            avatar_color=avatar_color
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if not user or not check_password(password, user.password_hash):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Your account has been deactivated.', 'danger')
            return redirect(url_for('auth.login'))

        user.last_login = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=True)
        flash(f'Welcome back, {user.username}! 👋', 'success')
        
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()
        avatar_color = request.form.get('avatar_color', current_user.avatar_color)
        
        current_user.bio = bio
        current_user.avatar_color = avatar_color
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
        
    user_schemas = current_user.schemas.order_by(
        __import__('models').SharedDatabase.created_at.desc()
    ).all()
    return render_template('profile.html', user_schemas=user_schemas)


@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """System dashboard listing all databases on the SQL Server instance."""
    from models import SharedDatabase
    from services.sqlserver_service import SqlServerService
    
    # 1. Fetch all databases from SQL Server instance
    server_dbs = SqlServerService.list_all_databases()
    
    # 2. Get history mapping from shared_databases metadata (case-insensitive key mapping)
    history_records = SharedDatabase.query.all()
    history_map = {rec.project_name.lower(): rec for rec in history_records}
    
    # 3. Cross-reference
    server_databases = []
    for db_info in server_dbs:
        db_name = db_info['name']
        match = history_map.get(db_name.lower())
        
        creator = "System/External"
        managed = False
        db_id = None
        
        if match:
            managed = True
            db_id = match.id
            if match.author:
                creator = match.author.username
            else:
                creator = "Anonymous"
                
        server_databases.append({
            'name': db_name,
            'create_date': db_info['create_date'],
            'creator': creator,
            'managed': managed,
            'db_id': db_id
        })

    # Stats cards summary based on metadata records
    user_schemas = current_user.schemas.all() if current_user.is_authenticated else []
    total_schemas = len(user_schemas)
    total_views = sum(s.views_count or 0 for s in user_schemas)
    total_downloads = sum(s.downloads_count or 0 for s in user_schemas)
    total_likes = sum(s.likes_count or 0 for s in user_schemas)
    deployed_count = sum(1 for s in user_schemas if s.is_deployed)
    ai_count = sum(1 for s in user_schemas if s.ai_generated)

    # Industry breakdown from metadata
    industry_map = {}
    for s in user_schemas:
        ind = s.industry or 'General'
        industry_map[ind] = industry_map.get(ind, 0) + 1

    return render_template('dashboard.html',
        server_databases=server_databases,
        total_schemas=total_schemas,
        total_views=total_views,
        total_downloads=total_downloads,
        total_likes=total_likes,
        deployed_count=deployed_count,
        ai_count=ai_count,
        industry_map=industry_map
    )


def _get_or_register_db(db_name: str) -> SharedDatabase:
    """Helper to auto-register external SQL Server databases to schema history."""
    from models import SharedDatabase
    from services.sqlserver_service import SqlServerService
    
    schema = SharedDatabase.query.filter(
        db.func.lower(SharedDatabase.project_name) == db_name.lower()
    ).first()
    
    if not schema:
        # Introspect tables and columns to generate mock DDL
        tables = SqlServerService.get_tables(db_name)
        sql_parts = []
        for tbl in tables:
            cols = SqlServerService.get_columns(db_name, tbl)
            col_strs = []
            for c in cols:
                pk_str = " PRIMARY KEY" if c['pk'] else ""
                null_str = " NOT NULL" if c['notnull'] else " NULL"
                col_strs.append(f"    [{c['name']}] {c['type']}{pk_str}{null_str}")
            sql_parts.append(f"CREATE TABLE [{tbl}] (\n" + ",\n".join(col_strs) + "\n);")
        
        generated_sql = "\n\n".join(sql_parts)
        schema = SharedDatabase(
            project_name = db_name,
            requirements = f"Auto-imported external database '{db_name}' from SQL Server.",
            sql_code = generated_sql or f"-- Database {db_name} exists but contains no user tables.",
            industry = "Imported",
            tags = "imported, sqlserver",
            is_deployed = True,
            deployed_to = f"SQL Server -> {db_name}",
            user_id = current_user.id if current_user.is_authenticated else None
        )
        db.session.add(schema)
        db.session.commit()
    return schema


@auth_bp.route('/open-db/<db_name>')
@login_required
def open_db(db_name):
    """Auto-register (if external) and redirect to CRUD browser."""
    try:
        schema = _get_register_db_safely(db_name)
        return redirect(url_for('crud.crud_home', db_id=schema.id))
    except Exception as e:
        flash(f"Error opening database '{db_name}': {e}", "danger")
        return redirect(url_for('auth.dashboard'))


@auth_bp.route('/view-db/<db_name>')
@login_required
def view_db(db_name):
    """Auto-register (if external) and redirect to Schema details page."""
    try:
        schema = _get_register_db_safely(db_name)
        return redirect(url_for('generator.database_details', db_id=schema.id))
    except Exception as e:
        flash(f"Error viewing database details: {e}", "danger")
        return redirect(url_for('auth.dashboard'))


def _get_register_db_safely(db_name: str):
    # Sanitize database name
    from services.sqlserver_service import SqlServerService
    is_valid, err = SqlServerService.validate_database_name(db_name)
    if not is_valid:
        raise ValueError(err)
    if not SqlServerService.check_db_exists(db_name):
        raise ValueError(f"Database '{db_name}' does not exist on SQL Server.")
    return _get_or_register_db(db_name)


@auth_bp.route('/delete-db/<db_name>', methods=['POST'])
@login_required
def delete_db(db_name):
    """Drop database from SQL Server and delete metadata records."""
    from services.sqlserver_service import SqlServerService
    from models import SharedDatabase
    
    # 1. Drop database on SQL Server (kills connections, drops tables, drops db)
    success, msg = SqlServerService.drop_database(db_name)
    if not success:
        flash(f"Failed to drop SQL Server database: {msg}", "danger")
        return redirect(url_for('auth.dashboard'))
        
    # 2. Drop from history metadata
    try:
        match = SharedDatabase.query.filter(
            db.func.lower(SharedDatabase.project_name) == db_name.lower()
        ).first()
        if match:
            db.session.delete(match)
            db.session.commit()
        flash(f"Database '{db_name}' was successfully dropped from SQL Server and history.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Database dropped from SQL Server, but failed to clear history: {e}", "warning")
        
    return redirect(url_for('auth.dashboard'))


@auth_bp.route('/export-db-sql/<db_name>')
@login_required
def export_db_sql(db_name):
    """Generate and download SQL script for SQL Server database."""
    try:
        schema = _get_register_db_safely(db_name)
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', db_name.lower())
        
        # Build script header
        ddl_script = f"-- SMART DB Auto-Generated Script\n"
        ddl_script += f"-- Target DBMS: Microsoft SQL Server\n"
        ddl_script += f"-- Database: [{db_name}]\n"
        ddl_script += f"-- Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        ddl_script += f"USE [master];\nGO\n"
        ddl_script += f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{db_name}')\n"
        ddl_script += f"BEGIN\n"
        ddl_script += f"    CREATE DATABASE [{db_name}];\n"
        ddl_script += f"END\nGO\n\n"
        ddl_script += f"USE [{db_name}];\nGO\n\n"
        ddl_script += schema.sql_code
        
        return Response(
            ddl_script,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={safe_name}_export.sql'}
        )
    except Exception as e:
        flash(f"Failed to export SQL script: {e}", "danger")
        return redirect(url_for('auth.dashboard'))
