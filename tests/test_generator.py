"""
DB VITHRA — Generator Tests
Tests SQL dialect translation, spec validation, and basic parsing.
"""
from utils import translate_sql, validate_table_spec, generate_sql_from_spec
from ai_engine.fallback_engine import FallbackEngine

def test_translate_sql():
    sql = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # Test PostgreSQL serialization
    pg_sql = translate_sql(sql, "postgresql")
    assert "SERIAL PRIMARY KEY" in pg_sql
    
    # Test MySQL serialization
    mysql_sql = translate_sql(sql, "mysql")
    assert "INT AUTO_INCREMENT PRIMARY KEY" in mysql_sql
    
    # Test MSSQL identity
    mssql_sql = translate_sql(sql, "mssql")
    assert "INT IDENTITY(1,1) PRIMARY KEY" in mssql_sql


def test_validate_table_spec():
    # Valid specification
    is_valid, err = validate_table_spec("users", "username: varchar(80)\nemail: varchar(255)")
    assert is_valid
    assert err == ""

    # Invalid table name
    is_valid, err = validate_table_spec("123users", "username: varchar(80)")
    assert not is_valid
    assert "Table name must start with" in err

    # Invalid column specification
    is_valid, err = validate_table_spec("users", "123col: varchar(80)")
    assert not is_valid
    assert "Invalid column name" in err


def test_generate_sql_from_spec():
    sql = generate_sql_from_spec("customers", "name: string, age: integer")
    assert "CREATE TABLE customers" in sql
    assert "name VARCHAR(100)" in sql
    assert "age INTEGER" in sql


def test_fallback_engine():
    engine = FallbackEngine()
    
    # Test general entity parsing fallback
    reqs = "I want a blogging platform with users, posts, and comments."
    extracted = engine.extract_entities(reqs)
    
    assert "entities" in extracted
    assert len(extracted["entities"]) > 0
    
    # Check that users, posts, and comments tables are parsed
    table_names = [e["name"].lower() for e in extracted["entities"]]
    assert any("user" in t for t in table_names)


def test_split_sql_statements():
    from utils import split_sql_statements
    sql = """
    -- Comment with a semicolon; inside it
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) DEFAULT 'some;value'
    );
    /* Another multiline; comment */
    CREATE TABLE posts (
        id INT
    );
    """
    stmts = split_sql_statements(sql)
    assert len(stmts) == 2
    assert "CREATE TABLE users" in stmts[0]
    assert "CREATE TABLE posts" in stmts[1]


def test_fallback_nl_to_sql():
    engine = FallbackEngine()
    
    # Test general NLP parsing
    result1 = engine.nl_to_sql("Show all active users registered this month", "", "sqlite")
    assert "users" in result1["tables_used"]
    assert "is_active" in result1["sql"]
    
    # Test a general query
    result2 = engine.nl_to_sql("Find all doctors in the department", "", "sqlite")
    assert "doctors" in result2["tables_used"]
    assert "departments" in result2["tables_used"]
    assert "SELECT" in result2["sql"]
