"""
SMART DB — Prompt Engineering Templates
All GPT-4o prompts for the multi-agent AI pipeline.
"""

# ── Phase 1: Entity & Relationship Extraction ─────────────────────────────────
ENTITY_EXTRACTION_PROMPT = """You are a Senior Database Architect with 20 years of experience designing enterprise-grade databases.

Analyze the following business requirements and extract all entities, their attributes, and relationships.

REQUIREMENTS:
{requirements}

Return ONLY valid JSON with this exact structure:
{{
  "system_name": "string (name of the system)",
  "industry": "string (Healthcare|Finance|E-commerce|Education|HR|Social|General|Manufacturing|Real Estate|Transportation)",
  "entities": [
    {{
      "name": "string (singular noun, snake_case)",
      "display_name": "string (human-readable)",
      "description": "string (what this entity represents)",
      "attributes": [
        {{
          "name": "string (snake_case column name)",
          "display_name": "string",
          "data_type": "string (INTEGER|VARCHAR(n)|TEXT|DECIMAL(10,2)|DATE|DATETIME|BOOLEAN|FLOAT)",
          "constraints": ["NOT NULL", "UNIQUE", "DEFAULT value", "CHECK (condition)"],
          "is_primary_key": false,
          "is_foreign_key": false,
          "description": "string (what this attribute stores)"
        }}
      ]
    }}
  ],
  "relationships": [
    {{
      "from_entity": "string",
      "to_entity": "string",
      "relationship_type": "ONE_TO_ONE|ONE_TO_MANY|MANY_TO_MANY",
      "description": "string",
      "through_table": "string (only for MANY_TO_MANY)"
    }}
  ],
  "summary": "string (brief description of the overall system)"
}}

Rules:
- Every entity MUST have an auto-increment primary key column (id or entity_name_id)
- Include created_at and updated_at timestamps for major entities
- Normalize to at least 3NF
- For MANY_TO_MANY relationships, include a junction table
- Use realistic, industry-standard column names
"""

# ── Phase 2: SQL Schema Generation ────────────────────────────────────────────
SQL_GENERATION_PROMPT = """You are an expert DBA specializing in {db_type} database design.

Generate production-ready CREATE TABLE SQL statements for the following schema.

SCHEMA:
{schema_json}

TARGET DATABASE: {db_type}

Return ONLY valid SQL with no markdown formatting. Follow these rules:
- Use {pk_syntax} for auto-increment primary keys
- Add appropriate indexes on foreign key columns and commonly searched fields
- Add foreign key constraints with ON DELETE CASCADE or RESTRICT as appropriate
- Add CHECK constraints for data validation where relevant
- Add NOT NULL on all mandatory fields
- Add UNIQUE constraints where needed
- Comment each table with its purpose
- Order tables so foreign key dependencies are created first

Example primary key syntax by DB type:
- SQLite: id INTEGER PRIMARY KEY AUTOINCREMENT
- MySQL: id INT AUTO_INCREMENT PRIMARY KEY
- PostgreSQL: id SERIAL PRIMARY KEY
- MSSQL: id INT IDENTITY(1,1) PRIMARY KEY
"""

# ── Phase 3: ER Diagram Generation ────────────────────────────────────────────
ER_DIAGRAM_PROMPT = """You are a database documentation expert.

Generate a Mermaid.js ER diagram for the following database schema.

SCHEMA:
{schema_json}

Return ONLY valid Mermaid erDiagram syntax. Example format:
erDiagram
    CUSTOMER {{
        int customer_id PK
        string name
        string email
    }}
    ORDER {{
        int order_id PK
        int customer_id FK
        date order_date
        decimal total_amount
    }}
    CUSTOMER ||--o{{ ORDER : places

Rules:
- Use correct Mermaid erDiagram syntax
- Mark PK and FK columns
- Show all relationships with correct cardinality (||--||, ||--o{{, }}o--o{{)
- Use simple type names: int, string, date, decimal, boolean, text
- Include ALL tables from the schema
"""

# ── Phase 4: Data Dictionary Generation ───────────────────────────────────────
DATA_DICTIONARY_PROMPT = """You are a technical documentation specialist.

Generate a comprehensive data dictionary for the following database schema.

SCHEMA:
{schema_json}

Return ONLY valid JSON with this exact structure:
{{
  "tables": [
    {{
      "name": "string (table name)",
      "display_name": "string",
      "description": "string (purpose of this table)",
      "estimated_rows": "string (e.g., '10K-100K', 'millions')",
      "columns": [
        {{
          "name": "string",
          "display_name": "string",
          "data_type": "string",
          "constraints": "string (e.g., 'NOT NULL, UNIQUE')",
          "description": "string (detailed description)",
          "example_values": ["value1", "value2", "value3"],
          "notes": "string (any special notes or business rules)"
        }}
      ],
      "indexes": ["string (description of each index)"],
      "relationships": ["string (description of each relationship)"]
    }}
  ]
}}
"""

# ── Phase 5: Sample Data Generation ───────────────────────────────────────────
SAMPLE_DATA_PROMPT = """You are a database testing specialist.

Generate realistic sample INSERT statements for the following database schema.
Generate 5-7 rows per table with realistic, domain-appropriate data.

SCHEMA:
{schema_json}
SYSTEM TYPE: {system_name}

Return ONLY valid SQL INSERT statements. Rules:
- Insert data in foreign key dependency order (parent tables first)
- Use realistic names, dates, amounts, and descriptions for the domain
- Ensure referential integrity (FK values match existing PKs)
- Skip auto-increment primary key columns (they auto-generate)
- Add a comment line before each table's inserts: -- Sample data for table_name
"""

# ── Phase 6: API Documentation Generation ────────────────────────────────────
API_DOCS_PROMPT = """You are a REST API documentation expert.

Generate complete REST API documentation for the following database schema.
The API uses Python Flask/FastAPI conventions.

SCHEMA:
{schema_json}

Return ONLY valid JSON with this exact structure:
{{
  "api_version": "v1",
  "base_url": "/api/v1",
  "endpoints": [
    {{
      "table": "string (table name)",
      "resource": "string (plural resource name)",
      "endpoints": [
        {{
          "method": "POST|GET|PUT|DELETE",
          "path": "string",
          "description": "string",
          "request_body": {{}},
          "response_example": {{}},
          "status_codes": {{"200": "OK", "201": "Created", "404": "Not Found", "422": "Validation Error"}}
        }}
      ]
    }}
  ]
}}
"""

# ── Phase 7: Improvement Suggestions ─────────────────────────────────────────
IMPROVEMENTS_PROMPT = """You are a senior database performance consultant.

Review the following database schema and suggest improvements.

SCHEMA:
{schema_json}

Return ONLY valid JSON with this exact structure:
{{
  "overall_assessment": "string (brief quality assessment)",
  "normalization_status": "1NF|2NF|3NF|BCNF (current status)",
  "suggestions": [
    {{
      "category": "Performance|Security|Normalization|Indexing|Naming|Constraints",
      "priority": "High|Medium|Low",
      "issue": "string (what the issue is)",
      "suggestion": "string (what to do)",
      "sql_example": "string (optional SQL snippet showing the fix)"
    }}
  ],
  "missing_tables": ["string (tables that should be added)"],
  "recommended_indexes": [
    {{
      "table": "string",
      "columns": ["string"],
      "reason": "string"
    }}
  ]
}}
"""

# ── Phase 8: NoSQL Schema Generation ─────────────────────────────────────────
NOSQL_SCHEMA_PROMPT = """You are a NoSQL database architect specializing in MongoDB.

Convert the following relational schema to a MongoDB document schema.

RELATIONAL SCHEMA:
{schema_json}

Return ONLY valid JSON with this exact structure:
{{
  "database": "string (db name)",
  "collections": [
    {{
      "name": "string (collection name)",
      "description": "string",
      "document_schema": {{
        "_id": "ObjectId",
        "field_name": "type or nested object"
      }},
      "example_document": {{}},
      "indexes": [
        {{
          "fields": {{}},
          "options": {{}}
        }}
      ],
      "embedding_strategy": "string (embedded vs referenced decision and why)"
    }}
  ]
}}
"""

# ── Phase 9: Multi-Database NL Query Assistant Prompt ──────────────────────────
NL_TO_SQL_PROMPT = """You are an expert Senior Database Architect specializing in SQL Server, MySQL, Oracle, MongoDB, and Excel Automation.

Convert the user's natural language question or requirement into an accurate query or command tailored specifically for the target database specification ({db_type}).

TARGET DATABASE PLATFORM: {db_type}
DATABASE SCHEMA / METADATA CONTEXT:
{schema_context}

USER REQUIREMENT / QUESTION:
{user_query}

Return ONLY valid JSON with this exact structure:
{{
  "sql": "string (the generated query/command syntax tailored for {db_type})",
  "explanation": "string (detailed explanation of how the query works or conceptual answer to user's doubt)",
  "tables_used": ["string (list of tables/collections/sheets referenced)"],
  "optimization_tips": ["string (indexing or performance suggestions for {db_type})"],
  "alternative_approaches": ["string (alternative syntax or approaches)"]
}}

Rules per platform specification:
1. SQL Server:
   - Use T-SQL dialect syntax with bracketed identifiers `[Table].[Column]`, `TOP N`, `GETDATE()`, `ISNULL()`.
2. MySQL:
   - Use MySQL dialect syntax with backtick identifiers `` `Table`.`Column` ``, `LIMIT N`, `NOW()`, `IFNULL()`.
3. Oracle:
   - Use Oracle PL/SQL dialect syntax with uppercase double quote identifiers `"TABLE"."COLUMN"`, `FETCH NEXT N ROWS ONLY`, `SYSDATE`, `NVL()`.
4. MongoDB:
   - Generate PyMongo or MongoDB shell query filter/aggregation pipeline JSON string (e.g. `db.collection.find({"age": {"$gt": 50}})` or `[{"$match": {...}}, {"$group": {...}}]`).
5. Excel:
   - Generate Python pandas / openpyxl expression snippet (e.g. `df[df['age'] > 50]`).
"""

