"""
SMART DB — AI Schema Agent
Multi-step GPT-4o pipeline for intelligent database schema generation.
Falls back to the rule-based engine when no API key is configured.
"""
import re
import json
import logging
from typing import Optional

import config
from ai_engine.prompt_templates import (
    ENTITY_EXTRACTION_PROMPT,
    SQL_GENERATION_PROMPT,
    ER_DIAGRAM_PROMPT,
    DATA_DICTIONARY_PROMPT,
    SAMPLE_DATA_PROMPT,
    API_DOCS_PROMPT,
    IMPROVEMENTS_PROMPT,
    NOSQL_SCHEMA_PROMPT,
    NL_TO_SQL_PROMPT,
)
from ai_engine.fallback_engine import FallbackEngine

logger = logging.getLogger(__name__)


def _get_pk_syntax(db_type: str) -> str:
    return {
        'sqlite':     'id INTEGER PRIMARY KEY AUTOINCREMENT',
        'mysql':      'id INT AUTO_INCREMENT PRIMARY KEY',
        'postgresql': 'id SERIAL PRIMARY KEY',
        'mssql':      'id INT IDENTITY(1,1) PRIMARY KEY',
    }.get(db_type, 'id INTEGER PRIMARY KEY AUTOINCREMENT')


class SchemaAgent:
    """
    Orchestrates the full AI pipeline:
      1. analyze_requirements  → entities + relationships (JSON)
      2. generate_sql          → CREATE TABLE SQL
      3. generate_er_diagram   → Mermaid erDiagram source
      4. generate_data_dict    → data dictionary (JSON)
      5. generate_sample_data  → INSERT statements
      6. generate_api_docs     → REST API docs (JSON)
      7. generate_improvements → optimization suggestions (JSON)
      8. generate_nosql        → MongoDB schema (JSON)
    """

    def __init__(self):
        self.ai_enabled = config.AI_ENABLED
        self.model      = config.OPENAI_MODEL
        self.fallback   = FallbackEngine()
        self._client    = None

    def _get_client(self):
        if self._client is None and self.ai_enabled:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=config.OPENAI_API_KEY)
            except ImportError:
                logger.warning("openai package not installed — using fallback engine.")
                self.ai_enabled = False
        return self._client

    def _call_gpt(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        """Call the OpenAI API and return the text response."""
        client = self._get_client()
        if not client:
            return None
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4096,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None

    def _parse_json(self, text: Optional[str]) -> Optional[dict]:
        """Safely parse JSON from GPT response, stripping markdown fences."""
        if not text:
            return None
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            cleaned = '\n'.join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON substring
            start = cleaned.find('{')
            end   = cleaned.rfind('}') + 1
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except Exception:
                    pass
        logger.warning("Could not parse JSON from GPT response.")
        return None

    # ── Public Pipeline Methods ────────────────────────────────────────────────

    def analyze_requirements(self, requirements: str) -> dict:
        """Step 1: Extract entities, attributes, relationships."""
        if not self.ai_enabled:
            return self.fallback.extract_entities(requirements)

        prompt   = ENTITY_EXTRACTION_PROMPT.format(requirements=requirements)
        response = self._call_gpt(prompt)
        result   = self._parse_json(response)

        if result and 'entities' in result:
            return result
        # GPT failed — fall back
        logger.warning("Entity extraction failed — using fallback.")
        return self.fallback.extract_entities(requirements)

    def generate_sql(self, schema: dict, db_type: str = 'sqlite') -> str:
        """Step 2: Generate CREATE TABLE SQL from schema dict."""
        if not self.ai_enabled:
            return self.fallback.generate_sql_from_entities(schema, db_type)

        schema_json = json.dumps(schema, indent=2)
        pk_syntax   = _get_pk_syntax(db_type)
        prompt      = SQL_GENERATION_PROMPT.format(
            db_type=db_type,
            schema_json=schema_json,
            pk_syntax=pk_syntax
        )
        response = self._call_gpt(prompt, temperature=0.1)

        if response:
            # Strip any markdown code fences
            sql = response.strip()
            for fence in ['```sql', '```SQL', '```']:
                sql = sql.replace(fence, '')
            return sql.strip()

        logger.warning("SQL generation failed — using fallback.")
        return self.fallback.generate_sql_from_entities(schema, db_type)

    def generate_er_diagram(self, schema: dict) -> str:
        """Step 3: Generate Mermaid erDiagram source."""
        if not self.ai_enabled:
            return self.fallback.generate_er_diagram(schema)

        schema_json = json.dumps(schema, indent=2)
        prompt      = ER_DIAGRAM_PROMPT.format(schema_json=schema_json)
        response    = self._call_gpt(prompt, temperature=0.1)

        if response:
            mmd = response.strip()
            for fence in ['```mermaid', '```']:
                mmd = mmd.replace(fence, '')
            if 'erDiagram' in mmd:
                return mmd.strip()

        logger.warning("ER diagram generation failed — using fallback.")
        return self.fallback.generate_er_diagram(schema)

    def generate_data_dictionary(self, schema: dict) -> Optional[dict]:
        """Step 4: Generate data dictionary JSON."""
        if not self.ai_enabled:
            return self.fallback.generate_data_dictionary(schema)

        schema_json = json.dumps(schema, indent=2)
        prompt      = DATA_DICTIONARY_PROMPT.format(schema_json=schema_json)
        response    = self._call_gpt(prompt)
        result      = self._parse_json(response)

        if result and 'tables' in result:
            return result
        return self.fallback.generate_data_dictionary(schema)

    def generate_sample_data(self, schema: dict) -> str:
        """Step 5: Generate INSERT sample data SQL."""
        if not self.ai_enabled:
            return self.fallback.generate_sample_data(schema)

        schema_json  = json.dumps(schema, indent=2)
        system_name  = schema.get('system_name', 'Application')
        prompt       = SAMPLE_DATA_PROMPT.format(schema_json=schema_json, system_name=system_name)
        response     = self._call_gpt(prompt, temperature=0.7)

        if response:
            sql = response.strip()
            for fence in ['```sql', '```SQL', '```']:
                sql = sql.replace(fence, '')
            return sql.strip()

        return self.fallback.generate_sample_data(schema)

    def generate_api_docs(self, schema: dict) -> Optional[dict]:
        """Step 6: Generate REST API documentation."""
        if not self.ai_enabled:
            return self.fallback.generate_api_docs(schema)

        schema_json = json.dumps(schema, indent=2)
        prompt      = API_DOCS_PROMPT.format(schema_json=schema_json)
        response    = self._call_gpt(prompt)
        result      = self._parse_json(response)

        if result and 'endpoints' in result:
            return result
        return self.fallback.generate_api_docs(schema)

    def generate_improvements(self, schema: dict) -> Optional[dict]:
        """Step 7: Generate optimization/improvement suggestions."""
        if not self.ai_enabled:
            return self.fallback.generate_improvements(schema)

        schema_json = json.dumps(schema, indent=2)
        prompt      = IMPROVEMENTS_PROMPT.format(schema_json=schema_json)
        response    = self._call_gpt(prompt)
        result      = self._parse_json(response)

        if result and 'suggestions' in result:
            return result
        return self.fallback.generate_improvements(schema)

    def generate_nosql_schema(self, schema: dict) -> Optional[dict]:
        """Step 8: Generate MongoDB NoSQL schema."""
        if not self.ai_enabled:
            return self.fallback.generate_nosql_schema(schema)

        schema_json = json.dumps(schema, indent=2)
        prompt      = NOSQL_SCHEMA_PROMPT.format(schema_json=schema_json)
        response    = self._call_gpt(prompt)
        result      = self._parse_json(response)

        if result and 'collections' in result:
            return result
        return self.fallback.generate_nosql_schema(schema)

    def nl_to_sql(self, user_query: str, schema_context: str, db_type: str = 'sqlite') -> Optional[dict]:
        """Query Assistant: Convert natural language to SQL."""
        if not self.ai_enabled:
            return self.fallback.nl_to_sql(user_query, schema_context, db_type)

        context_str = json.dumps(schema_context, indent=2) if isinstance(schema_context, dict) else str(schema_context)
        prompt   = NL_TO_SQL_PROMPT.format(
            db_type=db_type,
            schema_context=context_str,
            user_query=user_query
        )
        response = self._call_gpt(prompt, temperature=0.2)
        result   = self._parse_json(response)

        if result and 'sql' in result:
            return result
        return self.fallback.nl_to_sql(user_query, schema_context, db_type)

    def parse_table_structure(self, table_name: str, description: str) -> list[dict]:
        """Convert natural language table column description into structured list of columns."""
        if not description or not description.strip():
            return []

        # Simple regex heuristic if AI is disabled or fails
        cols = []
        raw_words = re.findall(r'\w+', description.lower())
        
        # Look for column hints
        known_types = {
            'id': 'INT IDENTITY(1,1) PRIMARY KEY',
            'name': 'NVARCHAR(100)',
            'age': 'INT',
            'gender': 'NVARCHAR(20)',
            'phone': 'NVARCHAR(20)',
            'email': 'NVARCHAR(255)',
            'address': 'NVARCHAR(MAX)',
            'dob': 'DATE',
            'date': 'DATETIME',
            'price': 'DECIMAL(12,2)',
            'amount': 'DECIMAL(12,2)',
            'salary': 'DECIMAL(12,2)',
            'status': 'NVARCHAR(50)',
            'description': 'NVARCHAR(MAX)',
            'notes': 'NVARCHAR(MAX)',
        }
        
        # If AI enabled, call GPT
        if self.ai_enabled:
            prompt = f"""Extract column definitions from this description for table '{table_name}':
"{description}"

Return ONLY JSON array of objects:
[
  {{"name": "column_name", "type": "DATA_TYPE", "primary_key": true/false, "not_null": true/false}}
]
Rules:
- For SQL Server, use INT, NVARCHAR(100), NVARCHAR(MAX), DECIMAL(12,2), DATETIME, DATE, BIT.
- Mark primary key where requested or inferred.
"""
            res = self._call_gpt(prompt, temperature=0.1)
            parsed = self._parse_json(res)
            if isinstance(parsed, list):
                return parsed

        # Heuristic fallback
        for word in raw_words:
            if word in known_types and not any(c['name'] == word for c in cols):
                is_pk = (word == 'id' or f"{table_name[:-1] if table_name.endswith('s') else table_name}_id" in word or 'primary' in description.lower() and 'id' in word)
                cols.append({
                    'name': word,
                    'type': known_types[word],
                    'primary_key': is_pk,
                    'not_null': is_pk or word in ['name', 'email']
                })
        
        if not cols:
            # Basic fallback columns
            pk_col = f"{table_name[:-1] if table_name.endswith('s') else table_name}_id"
            cols = [
                {'name': pk_col, 'type': 'INT IDENTITY(1,1) PRIMARY KEY', 'primary_key': True, 'not_null': True},
                {'name': f"{table_name.lower()}_name", 'type': 'NVARCHAR(100)', 'primary_key': False, 'not_null': True},
                {'name': 'created_at', 'type': 'DATETIME DEFAULT GETDATE()', 'primary_key': False, 'not_null': False}
            ]
            
        return cols


    def run_full_pipeline(self, requirements: str, db_type: str = 'sqlite') -> dict:
        """
        Run the complete 8-step pipeline and return all artifacts.
        """
        result = {
            'ai_used': self.ai_enabled,
            'entities': None,
            'sql_code': '',
            'er_diagram_mmd': '',
            'data_dictionary': None,
            'sample_data': '',
            'api_docs': None,
            'improvements': None,
            'nosql_schema': None,
        }

        # Step 1: Entity extraction
        entities = self.analyze_requirements(requirements)
        result['entities'] = entities

        # Step 2: SQL generation
        result['sql_code'] = self.generate_sql(entities, db_type)

        # Step 3: ER diagram
        result['er_diagram_mmd'] = self.generate_er_diagram(entities)

        # Steps 4-8 run in parallel-ish (sequential for simplicity)
        result['data_dictionary'] = self.generate_data_dictionary(entities)
        result['sample_data']     = self.generate_sample_data(entities)
        result['api_docs']        = self.generate_api_docs(entities)
        result['improvements']    = self.generate_improvements(entities)
        result['nosql_schema']    = self.generate_nosql_schema(entities)

        return result


# Singleton instance
agent = SchemaAgent()
