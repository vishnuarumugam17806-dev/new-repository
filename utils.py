"""
SMART DB — Utility and Helper Functions
Shared helper methods for SQL translation, analytics tracking, and input validation.
"""
import re
import json
from flask import request
from models import db, AnalyticsEvent

def _track(event_type: str, schema_id=None):
    """Log an analytics event to the database."""
    try:
        ev = AnalyticsEvent(
            event_type=event_type,
            schema_id=schema_id,
            ip_address=request.remote_addr
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        db.session.rollback()


def translate_sql(sql_code: str, db_type: str) -> str:
    """Translate SQLite syntax to the target DBMS dialect (specifically SQL Server)."""
    t = sql_code
    
    # Standard translation to MS SQL Server
    if db_type == 'mssql' or db_type == 'sqlserver':
        # Replace Primary Key Autoincrement syntaxes
        t = re.sub(r'(\b\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
                   r'\1 INT IDENTITY(1,1) PRIMARY KEY', t, flags=re.IGNORECASE)
        t = re.sub(r'(\b\w+)\s+INT\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
                   r'\1 INT IDENTITY(1,1) PRIMARY KEY', t, flags=re.IGNORECASE)
        t = re.sub(r'(\b\w+)\s+INTEGER\s+PRIMARY\s+KEY',
                   r'\1 INT IDENTITY(1,1) PRIMARY KEY', t, flags=re.IGNORECASE)
        
        # Replace generic BOOLEAN type with SQL Server BIT
        t = re.sub(r'\bBOOLEAN\b', 'BIT', t, flags=re.IGNORECASE)
        
        # Replace TEXT type with VARCHAR(MAX) (more modern and standard in MS SQL)
        t = re.sub(r'\bTEXT\b', 'VARCHAR(MAX)', t, flags=re.IGNORECASE)
        
        # Date and Time defaults translation
        t = t.replace('DEFAULT CURRENT_TIMESTAMP', 'DEFAULT GETDATE()')
        t = t.replace('DEFAULT CURRENT_DATE', 'DEFAULT CAST(GETDATE() AS DATE)')
        t = t.replace('DEFAULT CURRENT_TIME', 'DEFAULT CAST(GETDATE() AS TIME)')
        t = t.replace('CURRENT_DATE', 'CAST(GETDATE() AS DATE)')
        t = t.replace('CURRENT_TIME', 'CAST(GETDATE() AS TIME)')
        
        # MySQL or PostgreSQL style backticks to SQL Server square brackets
        # But only if it surrounds identifiers. Simple regex is usually sufficient:
        t = re.sub(r'`(\w+)`', r'[\1]', t)
    
    elif db_type == 'mysql':
        t = re.sub(r'(\b\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
                   r'\1 INT AUTO_INCREMENT PRIMARY KEY', t, flags=re.IGNORECASE)
        t = t.replace('DEFAULT CURRENT_DATE', 'DEFAULT (CURDATE())')
    elif db_type == 'postgresql':
        t = re.sub(r'(\b\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
                   r'\1 SERIAL PRIMARY KEY', t, flags=re.IGNORECASE)
        
    return t


def _safe_json(s):
    """Safely parse a JSON string, returning None if parsing fails."""
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def validate_table_spec(table_name, columns_spec):
    """Validate user input for direct table generation specification."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table_name):
        return False, 'Table name must start with a letter/underscore and contain only letters, numbers, underscores.'
    columns = [c.strip() for c in re.split(r'[\n,]+', columns_spec) if c.strip()]
    if not columns:
        return False, 'Provide at least one column specification.'
    for col in columns:
        name = col.split(':')[0].split(' ')[0].strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            return False, f'Invalid column name: {name}'
    return True, ''


def generate_sql_from_spec(table_name, columns_spec):
    """Generate basic SQL CREATE TABLE statements from raw specification."""
    raw = [c.strip() for c in re.split(r'[\n,]+', columns_spec) if c.strip()]
    cols = []
    for item in raw:
        if ':' in item:
            name, dtype = item.split(':', 1)
        elif ' ' in item:
            name, dtype = item.split(' ', 1)
        else:
            name, dtype = item, ''
        name  = name.strip()
        dtype = dtype.strip().upper() or 'VARCHAR(100)'
        if dtype in ('INT', 'INTEGER'):
            dtype = 'INTEGER'
        elif dtype in ('STR', 'STRING'):
            dtype = 'VARCHAR(100)'
        cols.append(f'{name} {dtype}')
    return f'CREATE TABLE {table_name} (\n    ' + ',\n    '.join(cols) + '\n);'


def split_sql_statements(sql: str) -> list:
    """Robustly split SQL statements by semicolon, avoiding splitting inside comments, strings or quotes."""
    statements = []
    current = []
    in_single_quote = False
    in_double_quote = False
    in_comment = False
    in_multiline_comment = False
    
    chars = list(sql)
    i = 0
    n = len(chars)
    while i < n:
        c = chars[i]
        
        # Check for comments
        if not in_single_quote and not in_double_quote:
            if not in_comment and not in_multiline_comment:
                if c == '-' and i + 1 < n and chars[i+1] == '-':
                    in_comment = True
                    current.append(c)
                    i += 1
                    current.append(chars[i])
                    i += 1
                    continue
                elif c == '/' and i + 1 < n and chars[i+1] == '*':
                    in_multiline_comment = True
                    current.append(c)
                    i += 1
                    current.append(chars[i])
                    i += 1
                    continue
            elif in_comment:
                if c == '\n':
                    in_comment = False
            elif in_multiline_comment:
                if c == '*' and i + 1 < n and chars[i+1] == '/':
                    in_multiline_comment = False
                    current.append(c)
                    i += 1
                    current.append(chars[i])
                    i += 1
                    continue
        
        if not in_comment and not in_multiline_comment:
            if c == "'" and (i == 0 or chars[i-1] != '\\'):
                in_single_quote = not in_single_quote
            elif c == '"' and (i == 0 or chars[i-1] != '\\'):
                in_double_quote = not in_double_quote
            elif c == ';' and not in_single_quote and not in_double_quote:
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue
                
          
        current.append(c)
        i += 1
        
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements
