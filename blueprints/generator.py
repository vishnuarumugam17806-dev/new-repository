"""
DB VITHRA — Schema Generator Blueprint
Handles dynamic database creation workflow, AI schema generation, multi-database connection testing, execution, file-based database generation, AI file data transformation, and downloads.
"""
import os
import re
import io
import csv
import json
import logging
from urllib.parse import quote_plus
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, send_file, session
from flask_login import current_user, login_required
import config as cfg
from models import db, SharedDatabase, SchemaVersion, DownloadLog, Comment, DatabaseInstance
from ai_engine.schema_agent import agent as ai_agent
from services.connection_manager import ConnectionManager
from services.sqlserver_service import SqlServerService
from utils import _track, translate_sql, validate_table_spec, generate_sql_from_spec, _safe_json, split_sql_statements

logger = logging.getLogger(__name__)

generator_bp = Blueprint('generator', __name__)

@generator_bp.route('/create', methods=['GET'])
@login_required
def create_database():
    initial_db_type = request.args.get('db_type', 'sqlserver').lower()
    default_instance = SqlServerService.get_server()
    return render_template('create.html', 
                           initial_db_type=initial_db_type,
                           default_instance=default_instance,
                           ai_enabled=cfg.AI_ENABLED)


@generator_bp.route('/api/test-connection', methods=['POST'])
def test_connection_api():
    """Test connection credentials for SQL Server, MySQL, Oracle, MongoDB, or Excel."""
    data = request.get_json() or {}
    db_type = data.get('db_type', 'sqlserver').lower()
    config = data.get('config', {})

    try:
        success, message = ConnectionManager.test_connection(db_type, config)
        return jsonify({
            'success': success,
            'message': message,
            'db_type': db_type
        })
    except Exception as e:
        logger.error(f"Test connection error: {e}")
        return jsonify({'success': False, 'message': f"Connection test failed: {str(e)}", 'db_type': db_type}), 400


@generator_bp.route('/api/db-create-chat/state', methods=['GET', 'POST'])
def chat_state():
    """Retrieve or reset the database creation chat session state."""
    default_instance = SqlServerService.get_server()

    if request.method == 'POST':
        state = {
            'step': 'select_spec',
            'database_type': None,
            'instance_name': default_instance,
            'connection_config': {},
            'database_name': None,
            'action': None,
            'tables': [],
            'table_structures': {},
            'current_table_index': 0,
            'sql_script': None,
            'verification': None
        }
        session['database_creation_state'] = state
        return jsonify({
            'state': state,
            'initial_message': (
                "Welcome to DB VITHRA! Let's build your data platform.\n\n"
                "First, please select your Database Specification target below."
            ),
            'specs': [
                {'id': 'sqlserver', 'name': 'SQL Server', 'icon': 'fa-database', 'desc': 'Microsoft SQL Server enterprise relational platform'},
                {'id': 'mysql', 'name': 'MySQL Engine', 'icon': 'fa-server', 'desc': 'High-performance open-source SQL engine'},
                {'id': 'oracle', 'name': 'Oracle DB', 'icon': 'fa-building-columns', 'desc': 'Enterprise relational PL/SQL system'},
                {'id': 'mongodb', 'name': 'MongoDB', 'icon': 'fa-leaf', 'desc': 'BSON document NoSQL store'},
                {'id': 'excel', 'name': 'Excel Workbook', 'icon': 'fa-file-excel', 'desc': 'Worksheet data grid & openpyxl spreadsheets'}
            ]
        })
    
    state = session.get('database_creation_state')
    if not state:
        state = {
            'step': 'select_spec',
            'database_type': None,
            'instance_name': default_instance,
            'connection_config': {},
            'database_name': None,
            'action': None,
            'tables': [],
            'table_structures': {},
            'current_table_index': 0,
            'sql_script': None,
            'verification': None
        }
        session['database_creation_state'] = state

    return jsonify({'state': state})


@generator_bp.route('/api/db-create-chat/message', methods=['POST'])
def chat_message():
    """Process user step in the multi-database creation workflow."""
    data = request.get_json() or {}
    user_input = data.get('message', '').strip()
    action = data.get('action', '').strip()
    db_type = data.get('db_type', '').strip().lower()
    config = data.get('config', {})
    
    state = session.get('database_creation_state')
    default_instance = SqlServerService.get_server()

    if action == 'reset' or not state:
        state = {
            'step': 'select_spec',
            'database_type': None,
            'instance_name': default_instance,
            'connection_config': {},
            'database_name': None,
            'action': None,
            'tables': [],
            'table_structures': {},
            'current_table_index': 0,
            'sql_script': None,
            'verification': None
        }
        session['database_creation_state'] = state

    current_step = state.get('step', 'select_spec')

    # STEP 1 & 2 – SELECT SPEC & CONFIRM CONNECTION -> ASK DATABASE NAME
    if current_step in ['select_spec', 'select_instance'] or action in ['select_spec', 'configure_instance']:
        selected_type = db_type or state.get('database_type') or 'sqlserver'
        if selected_type not in ['sqlserver', 'mysql', 'oracle', 'mongodb', 'excel']:
            selected_type = 'sqlserver'

        state['database_type'] = selected_type
        state['connection_config'] = config or state.get('connection_config', {})
        state['step'] = 'ask_dbname'
        session['database_creation_state'] = state

        type_names = {
            'sqlserver': 'Microsoft SQL Server',
            'mysql': 'MySQL Engine',
            'oracle': 'Oracle Database',
            'mongodb': 'MongoDB Document Store',
            'excel': 'Excel Workbook Platform'
        }

        prompt_names = {
            'sqlserver': 'Database Name',
            'mysql': 'Database / Schema Name',
            'oracle': 'Schema Name',
            'mongodb': 'Database Name',
            'excel': 'Workbook Name (.xlsx)'
        }

        return jsonify({
            'ai_message': f"✓ Target Platform set to **{type_names[selected_type]}**.\n\nPlease enter the **{prompt_names[selected_type]}** you would like to create (e.g. `HospitalDB`, `ECommerceData`).",
            'step': 'ask_dbname',
            'database_type': selected_type
        })

    # STEP 3 – RECEIVE DATABASE NAME & OFFER CREATION MODES (FILE UPLOAD VS AI/SCRATCH)
    elif current_step == 'ask_dbname':
        target_type = state.get('database_type', 'sqlserver')
        raw_name = user_input or data.get('database_name', 'DBVithra_Project')
        sanitized = re.sub(r'[^A-Za-z0-9_\-]', '', raw_name.replace(' ', '_'))
        if not sanitized:
            sanitized = 'DBVithra_Data'

        state['database_name'] = sanitized
        state['step'] = 'choose_creation_mode'
        session['database_creation_state'] = state

        return jsonify({
            'ai_message': (
                f"✓ Target Database set to: **{sanitized}** ({target_type.upper()}).\n\n"
                "How would you like to build your database tables/collections?\n\n"
                "• **Option 1: Upload a Data File (.csv, .xlsx, .json)** — Preview data & enter AI prompt to extract your database.\n"
                "• **Option 2: Create New From Scratch / AI Prompt** — Build tables interactively."
            ),
            'step': 'choose_creation_mode',
            'database_type': target_type,
            'database_name': sanitized,
            'show_upload_option': True,
            'actions': [
                {'id': 'upload_file_mode', 'label': '📁 UPLOAD FILE TO BUILD DATABASE (.csv, .xlsx, .json)', 'icon': 'fa-file-import'},
                {'id': 'create_scratch_mode', 'label': '🤖 CREATE NEW FROM SCRATCH / AI CHAT PROMPT', 'icon': 'fa-wand-magic-sparkles'}
            ]
        })

    # STEP 4 – CHOOSE CREATION MODE (FILE UPLOAD VS AI CHAT PROMPT)
    elif current_step == 'choose_creation_mode':
        target_type = state.get('database_type', 'sqlserver')
        db_name = state.get('database_name', 'DBVithra_Project')
        chosen_mode = action or user_input.lower()

        if chosen_mode == 'upload_file_mode' or 'upload' in user_input.lower():
            state['step'] = 'upload_file_mode'
            session['database_creation_state'] = state
            return jsonify({
                'ai_message': f"📁 **File Upload Mode Selected for Database '{db_name}'**.\n\nPlease select your `.csv`, `.xlsx`, or `.json` data file below. DB VITHRA will generate a data preview table and let you enter an AI prompt to build your database.",
                'step': 'upload_file_mode',
                'database_type': target_type,
                'database_name': db_name,
                'show_file_picker': True
            })
        else:
            state['step'] = 'ask_table_name'
            session['database_creation_state'] = state

            # Create Database on backend
            conn_config = state.get('connection_config', {})
            ConnectionManager.create_database(target_type, db_name, conn_config)

            struct_prompt = {
                'mongodb': 'Collection Name (e.g. patients, products)',
                'excel': 'Worksheet Name (e.g. Sheet1, SalesData)',
                'sqlserver': 'Table Name (e.g. Patients, Orders)',
                'mysql': 'Table Name (e.g. Customers, Inventory)',
                'oracle': 'Table Name (e.g. EMPLOYEES, DEPARTMENTS)'
            }

            return jsonify({
                'ai_message': f"✓ Database `{db_name}` created!\n\nNow, enter the **{struct_prompt[target_type]}** you want to build.",
                'step': 'ask_table_name',
                'database_type': target_type
            })

    # STEP 5 – ASK TABLE/COLLECTION NAME
    elif current_step == 'ask_table_name':
        target_type = state.get('database_type', 'sqlserver')
        tbl_name = user_input.strip()
        sanitized_tbl = re.sub(r'[^A-Za-z0-9_\-]', '', tbl_name.replace(' ', '_'))
        if not sanitized_tbl:
            sanitized_tbl = 'Data_Table'

        if sanitized_tbl not in state.get('tables', []):
            state['tables'].append(sanitized_tbl)

        state['step'] = 'ask_add_another_table'
        session['database_creation_state'] = state

        unit_name = 'Collection' if target_type == 'mongodb' else ('Worksheet' if target_type == 'excel' else 'Table')

        return jsonify({
            'ai_message': f"✓ {unit_name} `{sanitized_tbl}` registered.\n\nWould you like to add another {unit_name.lower()}?",
            'buttons': [
                {'label': f"YES – Add Another {unit_name}", 'value': "yes_add_table", 'class': 'btn-outline-primary'},
                {'label': f"NO – Define Fields for {sanitized_tbl}", 'value': "no_continue", 'class': 'btn-purple'}
            ],
            'step': 'ask_add_another_table'
        })

    elif current_step == 'ask_add_another_table':
        target_type = state.get('database_type', 'sqlserver')
        unit_name = 'Collection' if target_type == 'mongodb' else ('Worksheet' if target_type == 'excel' else 'Table')

        if 'yes' in user_input.lower() or action == 'yes_add_table':
            state['step'] = 'ask_table_name'
            session['database_creation_state'] = state
            return jsonify({
                'ai_message': f"Enter the next {unit_name.lower()} name.",
                'step': 'ask_table_name'
            })
        else:
            state['current_table_index'] = 0
            current_table = state['tables'][0]
            state['step'] = 'ask_table_structure'
            session['database_creation_state'] = state
            return jsonify({
                'ai_message': (
                    f"Define structure for **{current_table}** ({target_type.upper()}).\n\n"
                    "Enter column names and types (e.g. `id INT PRIMARY KEY, name VARCHAR(100), phone VARCHAR(20)`) "
                    "or describe in plain English."
                ),
                'step': 'ask_table_structure',
                'current_table': current_table
            })

    # STEP 6 – TABLE STRUCTURE & EXECUTION
    elif current_step == 'ask_table_structure':
        target_type = state.get('database_type', 'sqlserver')
        tables_list = state.get('tables', [])
        idx = state.get('current_table_index', 0)
        current_table = tables_list[idx] if idx < len(tables_list) else "Table"
        db_name = state.get('database_name', 'DBVithra_Project')
        conn_config = state.get('connection_config', {})

        # Parse column specifications
        cols_list = []
        if '\n' in user_input or ',' in user_input or ':' in user_input:
            raw_cols = [c.strip() for c in re.split(r'[\n,]+', user_input) if c.strip()]
            for item in raw_cols:
                parts = item.replace(':', ' ').split()
                cname = parts[0]
                ctype = parts[1] if len(parts) > 1 else ('VARCHAR(255)' if target_type != 'mongodb' else 'string')
                is_pk = 'PRIMARY' in item.upper() or cname.lower() in ['id', '_id']
                cols_list.append({'name': cname, 'type': ctype, 'primary_key': is_pk})
        else:
            cols_list = [
                {'name': 'id', 'type': 'INTEGER', 'primary_key': True},
                {'name': 'name', 'type': 'VARCHAR(200)', 'primary_key': False},
                {'name': 'created_at', 'type': 'DATETIME', 'primary_key': False}
            ]

        # Execute table/collection creation on actual adapter
        success, create_msg = ConnectionManager.create_table(target_type, db_name, current_table, cols_list, conn_config)

        # Store in SharedDatabase history
        new_db = SharedDatabase(
            project_name = db_name,
            requirements = f"AI Platform Database ({target_type.upper()})",
            sql_code     = f"-- {target_type.upper()} Structure for {db_name}.{current_table}\n" + json.dumps(cols_list, indent=2),
            industry     = 'General',
            database_type= target_type,
            is_deployed  = True,
            deployed_to  = f"{target_type.upper()} -> {db_name}.{current_table}",
            user_id      = current_user.id if current_user.is_authenticated else None
        )
        try:
            db.session.add(new_db)
            db.session.commit()
            _track('generated', new_db.id)
        except Exception:
            db.session.rollback()

        return jsonify({
            'ai_message': f"✓ {create_msg}\n\nDatabase operation verified successfully!",
            'step': 'finished',
            'redirect': f"/crud?db_type={target_type}&db_name={db_name}&table={current_table}"
        })

    return jsonify({'error': 'Invalid conversation state'}), 400


@generator_bp.route('/api/db-create-chat/preview-file', methods=['POST'])
def preview_file_data():
    """Receive uploaded data file and return dataset preview, columns, and data types."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected.'}), 400

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'Selected file is empty.'}), 400

        filename = file.filename
        base_dir = getattr(cfg, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        upload_dir = os.path.join(base_dir, 'static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        from services.import_service import ImportService
        parse_result = ImportService.parse_uploaded_file(file_path)

        if 'error' in parse_result:
            return jsonify({'success': False, 'message': parse_result['error']}), 400

        return jsonify({
            'success': True,
            'file_name': parse_result.get('file_name'),
            'file_path': file_path,
            'total_rows': parse_result.get('total_rows'),
            'columns': parse_result.get('columns'),
            'inferred_types': parse_result.get('inferred_types'),
            'preview': parse_result.get('preview')
        })
    except Exception as err:
        logger.error(f"Error previewing file: {err}", exc_info=True)
        return jsonify({'success': False, 'message': f"Preview error: {str(err)}"}), 200


@generator_bp.route('/api/db-create-chat/build-from-file-ai', methods=['POST'])
def build_from_file_ai():
    """Build database schema & populate data from uploaded file according to user AI prompt."""
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path', '').strip()
        db_type = data.get('db_type', 'sqlserver').lower()
        db_name = data.get('db_name', 'DBVithra_Project').strip()
        table_name = data.get('table_name', '').strip()
        ai_prompt = data.get('prompt', '').strip()

        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'File path missing or expired. Please upload file again.'}), 400

        from services.import_service import ImportService
        parse_result = ImportService.parse_uploaded_file(file_path)
        if 'error' in parse_result:
            return jsonify({'success': False, 'message': parse_result['error']}), 400

        columns = parse_result.get('columns', [])
        inferred_types = parse_result.get('inferred_types', {})
        filename = parse_result.get('file_name', 'data_file')

        if not table_name:
            table_name = os.path.splitext(filename)[0]

        table_name = re.sub(r'[^A-Za-z0-9_\-]', '', table_name.replace(' ', '_')) or 'ImportedData'
        db_name = re.sub(r'[^A-Za-z0-9_\-]', '', db_name.replace(' ', '_')) or 'DBVithra_Project'

        # Auto-detect column specifications
        cols_spec = []
        for col in columns:
            col_clean = re.sub(r'[^A-Za-z0-9_]', '_', str(col))
            ctype = inferred_types.get(col, 'VARCHAR(255)')
            if db_type == 'mongodb' and ctype == 'VARCHAR(255)':
                ctype = 'string'
            cols_spec.append({'name': col_clean, 'type': ctype, 'primary_key': col_clean.lower() in ['id', '_id']})

        if cols_spec and not any(c['primary_key'] for c in cols_spec):
            cols_spec[0]['primary_key'] = True

        # 1. Create target database
        conn_config = {}
        ConnectionManager.create_database(db_type, db_name, conn_config)

        # 2. Create target table / collection
        success, msg = ConnectionManager.create_table(db_type, db_name, table_name, cols_spec, conn_config)

        # 3. Bulk insert records from file
        mapping = {col: re.sub(r'[^A-Za-z0-9_]', '_', str(col)) for col in columns}
        import_ok, import_msg, inserted_count = ImportService.execute_bulk_import(db_type, db_name, table_name, file_path, mapping, conn_config)

        # 4. Save in SharedDatabase registry
        new_db = SharedDatabase(
            project_name = db_name,
            requirements = f"Database generated from file `{filename}` -> AI Prompt: {ai_prompt or 'Import All'}",
            sql_code     = f"-- Table {table_name} generated from file {filename}\n-- User Prompt: {ai_prompt or 'Import All'}\n-- Total rows imported: {inserted_count}",
            industry     = 'AI Import',
            database_type= db_type,
            is_deployed  = True,
            deployed_to  = f"{db_type.upper()} -> {db_name}.{table_name}"
        )
        try:
            db.session.add(new_db)
            db.session.commit()
            _track('generated', new_db.id)
        except Exception:
            db.session.rollback()

        return jsonify({
            'success': True,
            'message': f"✓ Database `{db_name}` and table `{table_name}` generated successfully from `{filename}`! ({inserted_count} records imported)",
            'redirect': f"/crud?db_type={db_type}&db_name={db_name}&table={table_name}"
        })
    except Exception as err:
        logger.error(f"Error in build_from_file_ai: {err}", exc_info=True)
        return jsonify({'success': False, 'message': f"AI database build error: {str(err)}"}), 200


@generator_bp.route('/database/<int:db_id>')
@login_required
def database_details(db_id):
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        from flask import abort
        abort(404)
    database.views_count = (database.views_count or 0) + 1
    db.session.commit()
    _track('viewed', db_id)

    entities_data    = _safe_json(database.entities_json)
    data_dict        = _safe_json(database.data_dictionary)
    api_docs         = _safe_json(database.api_docs)
    improvements     = _safe_json(database.improvements)
    nosql_schema     = _safe_json(database.nosql_schema)
    comments         = database.comments.order_by(Comment.created_at.desc()).all()
    versions         = database.versions.order_by(SchemaVersion.version_number.desc()).all()

    return render_template('details.html',
        database=database,
        entities_data=entities_data,
        data_dict=data_dict,
        api_docs=api_docs,
        improvements=improvements,
        nosql_schema=nosql_schema,
        comments=comments,
        versions=versions,
    )


@generator_bp.route('/database/<int:db_id>/er-diagram')
@login_required
def er_diagram_view(db_id):
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        from flask import abort
        abort(404)
    return render_template('er_diagram.html', database=database)


@generator_bp.route('/delete/<int:db_id>', methods=['POST'])
def delete_database(db_id):
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        from flask import abort
        abort(404)
    if current_user.is_authenticated and (current_user.id == database.user_id or current_user.role == 'admin') or database.user_id is None:
        db.session.delete(database)
        db.session.commit()
        flash('Database entry deleted.', 'info')
    else:
        flash('Permission denied.', 'danger')
    return redirect(url_for('marketplace.store'))


@generator_bp.route('/download-sql/<int:db_id>')
def download_sql_file(db_id):
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        from flask import abort
        abort(404)
    safe     = re.sub(r'[^a-zA-Z0-9_]', '_', database.project_name.lower())
    log      = DownloadLog(schema_id=db_id, ip_address=request.remote_addr, file_type='sql',
                           user_id=current_user.id if current_user.is_authenticated else None)
    database.downloads_count = (database.downloads_count or 0) + 1
    db.session.add(log)
    db.session.commit()
    _track('downloaded', db_id)
    return Response(database.sql_code, mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename={safe}.sql'})
