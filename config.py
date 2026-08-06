"""
SMART DB — Configuration Management
Loads settings from environment variables with sensible defaults.
"""
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

# ── Core ──────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
FLASK_ENV  = os.environ.get('FLASK_ENV', 'development')
DEBUG      = FLASK_ENV == 'development'
PORT       = int(os.environ.get('PORT', 5000))

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL   = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
AI_ENABLED     = bool(OPENAI_API_KEY)

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL      = os.environ.get('REDIS_URL', '')
CACHE_ENABLED  = bool(REDIS_URL)

# ── Database ──────────────────────────────────────────────────────────────────
import pyodbc

def get_database_uri() -> str:
    url = os.environ.get('DATABASE_URL')
    if url:
        return url

    # Default to localhost\SQLEXPRESS04 for SQL Server 2022 Express instance
    server   = os.environ.get('MSSQL_SERVER', r'localhost\SQLEXPRESS04')
    database = os.environ.get('MSSQL_DATABASE', 'smartdb_system')
    
    # Detect available drivers
    available = [d for d in pyodbc.drivers() if 'SQL Server' in d]
    if not available:
        driver = 'ODBC Driver 17 for SQL Server'
    else:
        # Prefer ODBC 17 or 18, fallback to whatever is available
        driver = next((d for d in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server', 'SQL Server'] if d in available), available[0])

    # Build Connection String with Windows Authentication (Trusted_Connection=yes)
    # Encrypt=no;TrustServerCertificate=yes; ensures local connection issues are bypassed
    conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"


DATABASE_URI = get_database_uri()

# ── Security ──────────────────────────────────────────────────────────────────
RATE_LIMIT_DEFAULT    = '200 per day, 50 per hour'
RATE_LIMIT_AI         = '30 per hour'
WTF_CSRF_ENABLED      = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True

# ── Pagination ────────────────────────────────────────────────────────────────
SCHEMAS_PER_PAGE = 12
