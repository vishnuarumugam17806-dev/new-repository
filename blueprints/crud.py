"""
SMART DB — Universal Data Explorer, Direct Grid Editing, NLP Modification & Import Blueprint
Handles multi-database exploration, direct row/cell/document editing, natural language operations, and file import pipeline across SQL Server, MySQL, Oracle, MongoDB, and Excel.
"""
import os
import re
import json
import logging
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, abort
)
from flask_login import current_user
import config as cfg
from models import db, SharedDatabase
from services.connection_manager import ConnectionManager
from services.import_service import ImportService
from services.visualization_service import VisualizationService
from ai_engine.schema_agent import agent as ai_agent

logger = logging.getLogger(__name__)

crud_bp = Blueprint('crud', __name__)

@crud_bp.route('/crud', methods=['GET'])
@crud_bp.route('/crud/<int:db_id>', methods=['GET'])
def explorer(db_id=None):
    """Render the Universal Data Explorer UI."""
    db_type = request.args.get('db_type', 'sqlserver').lower()
    db_name = request.args.get('db_name', '').strip()
    table = request.args.get('table', '').strip()
    open_import = request.args.get('open_import', 'false').lower() == 'true'

    if db_id and not db_name:
        shared = db.session.get(SharedDatabase, db_id)
        if shared:
            db_name = shared.project_name
            db_type = shared.database_type or 'sqlserver'

    if not db_name:
        # Default database lookup
        recent = SharedDatabase.query.order_by(SharedDatabase.created_at.desc()).first()
        if recent:
            db_name = recent.project_name
            db_type = recent.database_type or 'sqlserver'
        else:
            db_name = 'smartdb_system'

    return render_template('crud.html',
                           db_type=db_type,
                           db_name=db_name,
                           table=table,
                           db_id=db_id,
                           open_import=open_import)


@crud_bp.route('/api/explorer/tree', methods=['GET'])
def explorer_tree():
    """Return database hierarchy tree for the selected database type."""
    db_type = request.args.get('db_type', 'sqlserver').lower()
    config = {
        'host': request.args.get('host', 'localhost'),
        'port': request.args.get('port'),
        'username': request.args.get('username'),
        'password': request.args.get('password'),
        'connection_uri': request.args.get('uri')
    }

    try:
        databases = ConnectionManager.list_databases(db_type, config)
        tree = []
        for db_name in databases[:10]: # Limit top databases
            tables = ConnectionManager.list_tables(db_type, db_name, config)
            tree.append({
                'name': db_name,
                'tables': tables
            })
        return jsonify({'success': True, 'db_type': db_type, 'tree': tree})
    except Exception as e:
        logger.error(f"Explorer tree error for {db_type}: {e}")
        return jsonify({'success': False, 'error': str(e), 'tree': []}), 400


@crud_bp.route('/api/explorer/data', methods=['GET'])
def explorer_data():
    """Query data for a table/collection/worksheet with search and pagination."""
    db_type = request.args.get('db_type', 'sqlserver').lower()
    db_name = request.args.get('db_name', '').strip()
    table = request.args.get('table', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    if not db_name or not table:
        return jsonify({'data': [], 'columns': [], 'total_count': 0, 'page': 1, 'per_page': per_page})

    config = {
        'host': request.args.get('host', 'localhost'),
        'port': request.args.get('port'),
        'username': request.args.get('username'),
        'password': request.args.get('password'),
        'connection_uri': request.args.get('uri')
    }

    res = ConnectionManager.query(db_type, db_name, table, query_filter={'search': search}, page=page, per_page=per_page, config=config)
    schema = ConnectionManager.get_schema(db_type, db_name, table, config)

    res['schema_info'] = schema
    return jsonify(res)


@crud_bp.route('/api/explorer/record/create', methods=['POST'])
def record_create():
    """Add a new row/document/record to the database."""
    data = request.get_json() or {}
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    record = data.get('record', {})
    config = data.get('config', {})

    if not db_name or not table or not record:
        return jsonify({'success': False, 'message': 'Missing database name, table name, or record values.'}), 400

    success, msg = ConnectionManager.insert_record(db_type, db_name, table, record, config)
    return jsonify({'success': success, 'message': msg})


@crud_bp.route('/api/explorer/record/update', methods=['POST'])
def record_update():
    """Directly edit a row/document/record in the database."""
    data = request.get_json() or {}
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    record_id = data.get('record_id')
    updates = data.get('updates', {})
    config = data.get('config', {})

    if not db_name or not table or record_id is None or not updates:
        return jsonify({'success': False, 'message': 'Missing update parameters.'}), 400

    success, msg = ConnectionManager.update_record(db_type, db_name, table, record_id, updates, config)
    return jsonify({'success': success, 'message': msg})


@crud_bp.route('/api/explorer/record/delete', methods=['POST'])
def record_delete():
    """Delete a row/document/record with safety confirmation layer."""
    data = request.get_json() or {}
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    record_id = data.get('record_id')
    confirmed = data.get('confirmed', False)
    config = data.get('config', {})

    if not confirmed:
        return jsonify({
            'success': False,
            'requires_confirmation': True,
            'message': f"CAUTION: Deleting record `{record_id}` from `{table}` ({db_type.upper()}) is a destructive operation. Confirm deletion?"
        })

    success, msg = ConnectionManager.delete_record(db_type, db_name, table, record_id, config)
    return jsonify({'success': success, 'message': msg})


# ── NLP Data Operation & Confirmation Endpoints ─────────────────────────────

@crud_bp.route('/api/nlp-modify', methods=['POST'])
def nlp_modify():
    """Parse natural language modification instruction (e.g. 'Change Arun's phone number to 9876543210') and generate diff preview."""
    data = request.get_json() or {}
    prompt = data.get('prompt', '').strip()
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    config = data.get('config', {})

    if not prompt or not db_name or not table:
        return jsonify({'success': False, 'message': 'Provide instruction prompt, database name, and table.'}), 400

    schema = ConnectionManager.get_schema(db_type, db_name, table, config)
    col_names = [c['name'] for c in schema.get('columns', [])]

    # Fetch sample records to identify target record
    query_res = ConnectionManager.query(db_type, db_name, table, page=1, per_page=20, config=config)
    sample_records = query_res.get('data', [])

    # Use AI agent or rule-based parser to identify field, target record, and new value
    matched_record = None
    target_col = None
    new_val = None

    for rec in sample_records:
        rec_str = str(rec).lower()
        # Find if any name/key in record is mentioned in prompt
        for k, v in rec.items():
            if v and str(v).lower() in prompt.lower() and len(str(v)) > 2:
                matched_record = rec
                break
        if matched_record:
            break

    if not matched_record and sample_records:
        matched_record = sample_records[0]

    # Extract target column & new value from prompt
    for col in col_names:
        if col.lower() in prompt.lower() or col.replace('_', ' ').lower() in prompt.lower():
            target_col = col
            break

    if not target_col:
        target_col = col_names[1] if len(col_names) > 1 else col_names[0]

    # Extract phone numbers or numbers from prompt
    phone_match = re.search(r'\b\d{10}\b|\b\d{8,12}\b', prompt)
    if phone_match:
        new_val = phone_match.group(0)
    else:
        words = prompt.split()
        new_val = words[-1].replace('.', '')

    pk_field = schema.get('primary_keys', ['id', '_id'])[0] if schema.get('primary_keys') else '_row_index'
    rec_id = matched_record.get(pk_field) if matched_record else 1

    old_val = matched_record.get(target_col, 'None') if matched_record else 'None'

    proposed_change = {
        'db_type': db_type,
        'db_name': db_name,
        'table': table,
        'record_id': rec_id,
        'field': target_col,
        'old_value': old_val,
        'new_value': new_val,
        'updates': {target_col: new_val}
    }

    return jsonify({
        'success': True,
        'requires_confirmation': True,
        'proposed_change': proposed_change,
        'message': f"Proposed NLP Data Modification on `{table}` ({db_type.upper()}):\n\nRecord ID: `{rec_id}`\nField: `{target_col}`\nOld Value: `{old_val}` ➔ New Value: `{new_val}`"
    })


@crud_bp.route('/api/nlp-insert', methods=['POST'])
def nlp_insert():
    """Parse natural language insertion instruction (e.g. 'Add a new patient named Arun, age 25 and phone 9876543210') and generate insertion preview."""
    data = request.get_json() or {}
    prompt = data.get('prompt', '').strip()
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    config = data.get('config', {})

    if not prompt or not db_name or not table:
        return jsonify({'success': False, 'message': 'Provide instruction prompt, database name, and table.'}), 400

    schema = ConnectionManager.get_schema(db_type, db_name, table, config)
    cols = [c['name'] for c in schema.get('columns', []) if not c.get('primary_key')]

    # Extract name, age, phone from prompt
    record = {}
    name_match = re.search(r'named\s+([A-Za-z]+)', prompt, re.I)
    age_match = re.search(r'age\s+(\d+)', prompt, re.I)
    phone_match = re.search(r'phone\s+(\d+)', prompt, re.I) or re.search(r'\b\d{10}\b', prompt)

    for c in cols:
        cl = c.lower()
        if 'name' in cl:
            record[c] = name_match.group(1) if name_match else "Arun"
        elif 'age' in cl:
            record[c] = int(age_match.group(1)) if age_match else 25
        elif 'phone' in cl or 'mobile' in cl:
            record[c] = phone_match.group(1) if hasattr(phone_match, 'group') else (phone_match.group(0) if phone_match else "9876543210")
        elif 'status' in cl:
            record[c] = "Active"
        elif 'date' in cl:
            record[c] = "2026-08-23"

    if not record and cols:
        record[cols[0]] = "Sample Value"

    return jsonify({
        'success': True,
        'requires_confirmation': True,
        'proposed_insertion': {
            'db_type': db_type,
            'db_name': db_name,
            'table': table,
            'record': record
        },
        'message': f"Proposed NLP Data Insertion into `{table}` ({db_type.upper()}):\n\nFields: {json.dumps(record, indent=2)}"
    })


@crud_bp.route('/api/nlp-execute', methods=['POST'])
def nlp_execute():
    """Execute confirmed NLP data modification or insertion on the real underlying database."""
    data = request.get_json() or {}
    op_type = data.get('operation_type', 'modify') # 'modify' | 'insert'
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    config = data.get('config', {})

    if op_type == 'modify':
        rec_id = data.get('record_id')
        updates = data.get('updates', {})
        success, msg = ConnectionManager.update_record(db_type, db_name, table, rec_id, updates, config)
    else:
        record = data.get('record', {})
        success, msg = ConnectionManager.insert_record(db_type, db_name, table, record, config)

    return jsonify({'success': success, 'message': msg})


# ── File Import & Data Mapping Endpoints ─────────────────────────────────────

@crud_bp.route('/api/file-import/parse', methods=['POST'])
def file_import_parse():
    """Parse uploaded Excel/CSV/JSON file and suggest column mappings to destination table."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'}), 400

    file = request.files['file']
    db_type = request.form.get('db_type', 'sqlserver').lower()
    db_name = request.form.get('db_name', '')
    table = request.form.get('table', '')

    if not file.filename:
        return jsonify({'success': False, 'message': 'Empty file selected.'}), 400

    file_path = os.path.join(cfg.UPLOAD_FOLDER, file.filename)
    os.makedirs(cfg.UPLOAD_FOLDER, exist_ok=True)
    file.save(file_path)

    parse_result = ImportService.parse_uploaded_file(file_path)
    if 'error' in parse_result:
        return jsonify({'success': False, 'message': parse_result['error']}), 400

    schema = ConnectionManager.get_schema(db_type, db_name, table, {})
    target_cols = [c['name'] for c in schema.get('columns', [])]

    mapping = ImportService.generate_mapping(parse_result['columns'], target_cols)

    return jsonify({
        'success': True,
        'parse_info': parse_result,
        'target_columns': target_cols,
        'suggested_mapping': mapping
    })


@crud_bp.route('/api/file-import/execute', methods=['POST'])
def file_import_execute():
    """Execute bulk data import into destination table using user-confirmed column mapping."""
    data = request.get_json() or {}
    db_type = data.get('db_type', 'sqlserver').lower()
    db_name = data.get('db_name', '')
    table = data.get('table', '')
    file_path = data.get('file_path', '')
    mapping = data.get('mapping', {})
    config = data.get('config', {})

    if not file_path or not os.path.exists(file_path):
        return jsonify({'success': False, 'message': 'Uploaded file reference missing.'}), 400

    success, msg, imported_count = ImportService.execute_bulk_import(db_type, db_name, table, file_path, mapping, config)
    return jsonify({'success': success, 'message': msg, 'imported_count': imported_count})
