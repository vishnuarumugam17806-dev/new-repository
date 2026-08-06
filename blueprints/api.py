"""
SMART DB — API and Query Assistant Blueprint
Handles query assistant and NLP Natural Language to SQL generation.
"""
from flask import Blueprint, render_template, request, jsonify
import config as cfg
from models import SharedDatabase
from ai_engine.schema_agent import agent as ai_agent

api_bp = Blueprint('api', __name__)

@api_bp.route('/query-assistant')
def query_assistant():
    schemas = SharedDatabase.query.order_by(SharedDatabase.created_at.desc()).all()
    return render_template('query_assistant.html', schemas=schemas, ai_enabled=cfg.AI_ENABLED)


@api_bp.route('/api/nl-to-sql', methods=['POST'])
def nl_to_sql():
    data      = request.get_json()
    query     = data.get('query', '').strip()
    schema_id = data.get('schema_id')
    db_type   = data.get('db_type', 'sqlite')

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    schema_context = ''
    if schema_id:
        schema = SharedDatabase.query.get(schema_id)
        if schema:
            schema_context = schema.sql_code

    result = ai_agent.nl_to_sql(query, schema_context, db_type)
    return jsonify(result)
