"""
DB VITHRA — API and Multi-Database Query Assistant Blueprint
Handles natural language query assistant endpoints for SQL Server, MySQL, Oracle, MongoDB, and Excel.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
import config as cfg
from models import SharedDatabase
from ai_engine.schema_agent import agent as ai_agent
from services.connection_manager import ConnectionManager
from services.sqlserver_service import SqlServerService
from services.visualization_service import VisualizationService

api_bp = Blueprint('api', __name__)

@api_bp.route('/query-assistant')
@login_required
def query_assistant():
    return render_template('query_assistant.html', ai_enabled=cfg.AI_ENABLED)


@api_bp.route('/api/visualization/analyze', methods=['GET'])
def visualization_analyze():
    """Return chart payloads and KPIs for target dataset."""
    db_type = request.args.get('db_type', 'sqlserver').lower()
    db_name = request.args.get('db_name', '').strip()
    table = request.args.get('table', '').strip()

    if not db_name or not table:
        return jsonify({'kpis': [], 'charts': [], 'summary': 'Select a target database and table.'})

    res = VisualizationService.analyze_and_build_charts(db_type, db_name, table, {})
    return jsonify(res)


@api_bp.route('/api/nl-to-sql', methods=['POST'])
def nl_to_sql():
    try:
        data        = request.get_json() or {}
        query       = data.get('query', '').strip()
        schema_id   = data.get('schema_id')
        raw_db_name = data.get('db_name', '').strip()
        db_type     = data.get('db_type', 'sqlserver').lower()

        if not query:
            return jsonify({'error': 'Query is required'}), 400

        target_db_name = raw_db_name or 'DBVithra_Project'
        schema_context = ""

        if schema_id:
            try:
                sid = int(schema_id)
                schema = SharedDatabase.query.get(sid)
                if schema:
                    target_db_name = target_db_name or schema.project_name
                    schema_context = schema.sql_code or schema.nosql_schema or ""
            except Exception:
                pass

        if not schema_context and target_db_name:
            try:
                tables = ConnectionManager.list_tables(db_type, target_db_name, {})
                if tables:
                    schemas_list = []
                    for t in tables[:5]:
                        s = ConnectionManager.get_schema(db_type, target_db_name, t, {})
                        schemas_list.append(s)
                    schema_context = str(schemas_list)
            except Exception:
                pass

        result = ai_agent.nl_to_sql(query, schema_context or '', db_type)

        try:
            sql_str = result.get('sql', '').strip().upper()
            is_select_query = sql_str.startswith('SELECT') and db_type in ('sqlserver', 'mssql', 'mysql', 'oracle', 'sqlite')
            if is_select_query and target_db_name:
                table_target = tables[0] if ('tables' in locals() and tables) else (result.get('tables_used', [''])[0] or 'Data')
                query_res = ConnectionManager.query(db_type, target_db_name, table_target, page=1, per_page=10)
                if query_res and not query_res.get('error') and query_res.get('data'):
                    result['executed'] = True
                    result['query_results'] = query_res
                else:
                    result['executed'] = False
                    if query_res and query_res.get('error'):
                        result['execution_notice'] = query_res.get('error')
            else:
                result['executed'] = False
        except Exception as query_err:
            result['executed'] = False
            result['execution_error'] = str(query_err)

        return jsonify(result)
    except Exception as err:
        return jsonify({'error': f"Processing error: {str(err)}"}), 200
