"""
SMART DB — SQL Server Service Module
Handles SQL Server connection lifecycle, system database bootstrapping, validation,
introspection, dynamic query execution, transactions, and cleanup.
"""
import os
import re
import logging
try:
    import pyodbc
except ImportError:
    pyodbc = None
from datetime import datetime

logger = logging.getLogger(__name__)

class SqlServerService:
    @staticmethod
    def get_server() -> str:
        return os.environ.get('MSSQL_SERVER', r'localhost\SQLEXPRESS04')

    @staticmethod
    def get_system_db_name() -> str:
        return os.environ.get('MSSQL_DATABASE', 'smartdb_system')

    @classmethod
    def get_driver(cls) -> str:
        if not pyodbc:
            return 'ODBC Driver 17 for SQL Server'
        try:
            available = [d for d in pyodbc.drivers() if 'SQL Server' in d]
            if not available:
                return 'ODBC Driver 17 for SQL Server'
            return next((d for d in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server', 'SQL Server'] if d in available), available[0])
        except Exception:
            return 'ODBC Driver 17 for SQL Server'

    @classmethod
    def get_connection_string(cls, database: str = 'master', instance_name: str = None) -> str:
        server = instance_name.strip() if instance_name and instance_name.strip() else cls.get_server()
        driver = cls.get_driver()
        # Windows Authentication with connection parameters to ignore local SSL certificate warnings
        return f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"

    @classmethod
    def get_connection(cls, database: str = 'master', autocommit: bool = False, instance_name: str = None):
        if not pyodbc:
            raise RuntimeError("pyodbc is not available in this environment.")
        conn_str = cls.get_connection_string(database, instance_name=instance_name)
        conn = pyodbc.connect(conn_str)
        if autocommit:
            conn.autocommit = True
        return conn

    @classmethod
    def test_connection(cls, instance_name: str) -> tuple[bool, str]:
        """Test SQL Server connectivity for a given instance name."""
        if not instance_name or not instance_name.strip():
            return False, "Instance name cannot be empty."
        try:
            conn = cls.get_connection('master', instance_name=instance_name.strip())
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return True, f"Successfully connected to {instance_name.strip()}"
        except Exception as e:
            logger.error(f"Connection test failed for '{instance_name}': {e}")
            return False, str(e)

    @classmethod
    def init_system_db(cls):
        """Bootstrap the system metadata database on startup."""
        if not pyodbc:
            logger.info("pyodbc is not installed. Skipping SQL Server system database bootstrap.")
            return
        system_db = cls.get_system_db_name()
        logger.info(f"Bootstrapping system metadata database: {system_db}")
        
        try:
            conn = cls.get_connection('master', autocommit=True)
            cursor = conn.cursor()
            
            # Check database presence
            cursor.execute("SELECT 1 FROM sys.databases WHERE name = ?", system_db)
            if not cursor.fetchone():
                logger.info(f"System database '{system_db}' not found. Creating it on SQL Server...")
                # Database name is safe since it's defined in the environment configuration
                cursor.execute(f"CREATE DATABASE [{system_db}]")
                logger.info(f"System database '{system_db}' created successfully.")
            else:
                logger.info(f"System database '{system_db}' already exists.")
            
            cursor.close()
            conn.close()
        except Exception as e:
            logger.critical(f"Failed to bootstrap system database in SQL Server: {e}")
            raise e

    @staticmethod
    def validate_database_name(name: str) -> tuple[bool, str]:
        """Validate database name to prevent SQL injection and comply with SQL Server rules."""
        if not name:
            return False, "Database name cannot be empty."
        
        # SQL Server identifier limits: 128 characters max
        if len(name) > 128:
            return False, "Database name is too long (maximum 128 characters)."
        
        # Valid name: starts with letter/underscore, followed by letters, digits, @, $, #, or _
        # Semicolons, dashes, spaces, and quotes are forbidden to prevent injection
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_@$#]*', name):
            return False, (
                "Database name must start with a letter or underscore, and can "
                "only contain letters, digits, underscores, and characters: @, $, #"
            )
        
        # Blacklist system reserved databases
        blacklisted = {'master', 'tempdb', 'model', 'msdb', 'smartdb_system', 'admin', 'dbo', 'sys'}
        if name.lower() in blacklisted or name.lower() == SqlServerService.get_system_db_name().lower():
            return False, f"'{name}' is a reserved database name and cannot be used."
            
        return True, ""

    @classmethod
    def check_db_exists(cls, name: str, instance_name: str = None) -> bool:
        """Check if a database exists on the SQL Server instance."""
        try:
            conn = cls.get_connection('master', instance_name=instance_name)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM sys.databases WHERE name = ?", name)
            exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"Error checking database existence: {e}")
            return False

    @classmethod
    def list_all_databases(cls, instance_name: str = None) -> list[dict]:
        """Retrieve list of user databases on the SQL Server instance."""
        system_db = cls.get_system_db_name()
        databases = []
        try:
            conn = cls.get_connection('master', instance_name=instance_name)
            cursor = conn.cursor()
            query = """
                SELECT name, create_date 
                FROM sys.databases 
                WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb', ?)
                ORDER BY create_date DESC
            """
            cursor.execute(query, system_db)
            for row in cursor.fetchall():
                databases.append({
                    'name': row[0],
                    'create_date': row[1]
                })
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error listing databases from SQL Server: {e}")
        return databases

    @classmethod
    def create_empty_database(cls, db_name: str, instance_name: str = None) -> tuple[bool, list[str]]:
        """Create an empty database on the specified SQL Server instance."""
        logs = []
        is_valid, err_msg = cls.validate_database_name(db_name)
        if not is_valid:
            return False, [f"Validation Error: {err_msg}"]

        if cls.check_db_exists(db_name, instance_name=instance_name):
            return False, [f"Error: Database '{db_name}' already exists on SQL Server."]

        try:
            inst_str = instance_name or cls.get_server()
            logs.append(f"Connecting to SQL Server instance '{inst_str}'...")
            conn = cls.get_connection('master', autocommit=True, instance_name=instance_name)
            cursor = conn.cursor()
            logs.append(f"Executing: CREATE DATABASE [{db_name}];")
            cursor.execute(f"CREATE DATABASE [{db_name}]")
            cursor.close()
            conn.close()
            logs.append(f"✓ Empty database '{db_name}' successfully created.")
            return True, logs
        except Exception as e:
            logs.append(f"ERROR: {e}")
            return False, logs

    @classmethod
    def verify_database_creation(cls, db_name: str, instance_name: str = None) -> dict:
        """Verify database, tables, PKs, and FKs existence in SQL Server."""
        res = {
            'db_exists': False,
            'db_id': None,
            'tables_count': 0,
            'tables': [],
            'pk_count': 0,
            'fk_count': 0,
            'logs': []
        }
        try:
            conn = cls.get_connection('master', instance_name=instance_name)
            cursor = conn.cursor()
            cursor.execute("SELECT DB_ID(?)", db_name)
            row = cursor.fetchone()
            db_id = row[0] if row else None
            cursor.close()
            conn.close()

            if not db_id:
                res['logs'].append(f"Database '{db_name}' not found on SQL Server.")
                return res

            res['db_exists'] = True
            res['db_id'] = db_id
            res['logs'].append(f"✓ SQL Server connection successful (DB_ID: {db_id})")

            # Check tables, PKs, FKs in target DB
            t_conn = cls.get_connection(db_name, instance_name=instance_name)
            t_cur = t_conn.cursor()
            
            t_cur.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME NOT IN ('sysdiagrams')
            """)
            tables = [r[0] for r in t_cur.fetchall()]
            res['tables'] = tables
            res['tables_count'] = len(tables)
            res['logs'].append(f"✓ Database verified with {len(tables)} tables")

            t_cur.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                WHERE CONSTRAINT_TYPE = 'PRIMARY KEY'
            """)
            res['pk_count'] = t_cur.fetchone()[0]
            res['logs'].append(f"✓ {res['pk_count']} primary keys verified")

            t_cur.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                WHERE CONSTRAINT_TYPE = 'FOREIGN KEY'
            """)
            res['fk_count'] = t_cur.fetchone()[0]
            if res['fk_count'] > 0:
                res['logs'].append(f"✓ {res['fk_count']} foreign key relationships verified")

            t_cur.close()
            t_conn.close()
        except Exception as e:
            res['logs'].append(f"Verification error: {e}")
        return res

    @classmethod
    def execute_schema_in_db(cls, db_name: str, sql_statements: list[str], instance_name: str = None) -> tuple[bool, list[str]]:
        """
        Execute multiple SQL statements (tables, keys, indexes) inside a single transaction.
        Rolls back changes if any statement fails.
        """
        logs = []
        conn = None
        try:
            conn = cls.get_connection(db_name, instance_name=instance_name)
            cursor = conn.cursor()
            logs.append(f"Connected to database '{db_name}'.")
            
            for idx, stmt in enumerate(sql_statements, 1):
                clean_stmt = stmt.strip()
                if not clean_stmt:
                    continue
                logs.append(f"Executing statement {idx}: {clean_stmt[:70]}...")
                cursor.execute(clean_stmt)
            
            conn.commit()
            logs.append("All CREATE TABLE statements executed successfully. Transaction committed.")
            cursor.close()
            conn.close()
            return True, logs
        except Exception as e:
            error_msg = str(e)
            logs.append(f"ERROR executing table statements: {error_msg}")
            if conn:
                try:
                    conn.rollback()
                    logs.append("Transaction rolled back successfully.")
                except Exception as rollback_err:
                    logs.append(f"Rollback failed: {rollback_err}")
                try:
                    conn.close()
                except Exception:
                    pass
            return False, logs

    @classmethod
    def create_database_and_schema(cls, db_name: str, sql_statements: list[str], instance_name: str = None) -> tuple[bool, list[str]]:
        """
        Runs the full database setup process:
        1. CREATE DATABASE
        2. Execute tables inside a transaction
        3. If table execution fails, drops the database to maintain clean rollback state.
        """
        logs = []
        db_created = False
        
        # 1. Validate name
        is_valid, err_msg = cls.validate_database_name(db_name)
        if not is_valid:
            return False, [f"Validation Error: {err_msg}"]

        # 2. Check for duplicate
        if cls.check_db_exists(db_name, instance_name=instance_name):
            return False, [f"Error: Database '{db_name}' already exists on the SQL Server instance."]

        # 3. Create database
        try:
            inst_name = instance_name or cls.get_server()
            logs.append(f"Creating database '{db_name}' on SQL Server instance '{inst_name}'...")
            master_conn = cls.get_connection('master', autocommit=True, instance_name=instance_name)
            master_cur = master_conn.cursor()
            master_cur.execute(f"CREATE DATABASE [{db_name}]")
            master_cur.close()
            master_conn.close()
            db_created = True
            logs.append(f"Database '{db_name}' created in SQL Server.")
        except Exception as e:
            logs.append(f"ERROR creating database: {e}")
            return False, logs

        # 4. Execute tables
        success, exec_logs = cls.execute_schema_in_db(db_name, sql_statements, instance_name=instance_name)
        logs.extend(exec_logs)

        # 5. Rollback database creation on table failure
        if not success and db_created:
            try:
                logs.append(f"Rolling back database creation: Dropping database '{db_name}'...")
                # Kill active connections to db before dropping
                master_conn = cls.get_connection('master', autocommit=True, instance_name=instance_name)
                master_cur = master_conn.cursor()
                kill_query = f"""
                    ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                    DROP DATABASE [{db_name}];
                """
                master_cur.execute(kill_query)
                master_cur.close()
                master_conn.close()
                logs.append(f"Database '{db_name}' dropped successfully. System rolled back to clean state.")
            except Exception as drop_err:
                logs.append(f"WARNING: Could not drop database during rollback: {drop_err}")
            return False, logs

        return True, logs

    @classmethod
    def drop_database(cls, db_name: str, instance_name: str = None) -> tuple[bool, str]:
        """Drops a database from SQL Server instance by killing active sessions first."""
        # 1. Validate
        is_valid, err_msg = cls.validate_database_name(db_name)
        if not is_valid:
            return False, f"Validation Error: {err_msg}"
            
        if not cls.check_db_exists(db_name, instance_name=instance_name):
            return False, f"Database '{db_name}' does not exist on the server."
            
        try:
            conn = cls.get_connection('master', autocommit=True, instance_name=instance_name)
            cursor = conn.cursor()
            
            # Terminate connections to avoid 'database in use' locks
            logger.info(f"Setting database [{db_name}] to SINGLE_USER and dropping it...")
            cursor.execute(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
            cursor.execute(f"DROP DATABASE [{db_name}]")
            
            cursor.close()
            conn.close()
            return True, f"Database '{db_name}' was successfully dropped from SQL Server."
        except Exception as e:
            logger.error(f"Error dropping database '{db_name}': {e}")
            return False, str(e)

    @classmethod
    def get_tables(cls, db_name: str, instance_name: str = None) -> list[str]:
        """List all user-defined tables in a specific database."""
        tables = []
        try:
            conn = cls.get_connection(db_name, instance_name=instance_name)
            cursor = conn.cursor()
            query = """
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME NOT IN ('sysdiagrams')
                ORDER BY TABLE_NAME
            """
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error listing tables in {db_name}: {e}")
        return tables

    @classmethod
    def get_columns(cls, db_name: str, table_name: str, instance_name: str = None) -> list[dict]:
        """Introspect columns, data types, and primary key status for a specific table."""
        columns = []
        try:
            conn = cls.get_connection(db_name, instance_name=instance_name)
            cursor = conn.cursor()
            query = """
                SELECT 
                    c.COLUMN_NAME AS name, 
                    c.DATA_TYPE + COALESCE('(' + CAST(c.CHARACTER_MAXIMUM_LENGTH AS VARCHAR(10)) + ')', '') AS type,
                    CASE WHEN c.IS_NULLABLE = 'YES' THEN 0 ELSE 1 END AS notnull,
                    c.COLUMN_DEFAULT AS dflt_value,
                    CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS pk
                FROM INFORMATION_SCHEMA.COLUMNS c
                LEFT JOIN (
                    SELECT ku.TABLE_NAME, ku.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    INNER JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc ON ku.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                ) pk ON c.TABLE_NAME = pk.TABLE_NAME AND c.COLUMN_NAME = pk.COLUMN_NAME
                WHERE c.TABLE_NAME = ?
                ORDER BY c.ORDINAL_POSITION
            """
            cursor.execute(query, table_name)
            for idx, row in enumerate(cursor.fetchall()):
                columns.append({
                    'cid': idx,
                    'name': row[0],
                    'type': row[1].upper(),
                    'notnull': row[2],
                    'dflt_value': row[3],
                    'pk': row[4]
                })
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name} in {db_name}: {e}")
        return columns

    @classmethod
    def get_full_schema(cls, db_name: str, instance_name: str = None) -> dict:
        """Introspect full schema (tables, columns, types, keys, relationships) for AI prompt context."""
        tables = cls.get_tables(db_name, instance_name=instance_name)
        schema_dict = {
            'database_name': db_name,
            'tables': {}
        }
        try:
            conn = cls.get_connection(db_name, instance_name=instance_name)
            cursor = conn.cursor()

            for tbl in tables:
                cols = cls.get_columns(db_name, tbl, instance_name=instance_name)
                schema_dict['tables'][tbl] = {
                    'columns': cols,
                    'foreign_keys': []
                }
                
                # Fetch foreign keys for tbl
                fk_query = """
                    SELECT 
                        kcu1.COLUMN_NAME AS fk_column,
                        kcu2.TABLE_NAME AS referenced_table,
                        kcu2.COLUMN_NAME AS referenced_column
                    FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu1 ON rc.CONSTRAINT_NAME = kcu1.CONSTRAINT_NAME
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME
                    WHERE kcu1.TABLE_NAME = ?
                """
                cursor.execute(fk_query, tbl)
                for fk_row in cursor.fetchall():
                    schema_dict['tables'][tbl]['foreign_keys'].append({
                        'column': fk_row[0],
                        'ref_table': fk_row[1],
                        'ref_column': fk_row[2]
                    })
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error retrieving full schema for {db_name}: {e}")
        return schema_dict

    @classmethod
    def execute_read_only_query(cls, db_name: str, sql_query: str, instance_name: str = None) -> tuple[bool, dict, float, str]:
        """
        Execute a read-only SELECT query against SQL Server database.
        Returns: (success, result_dict, duration_ms, error_message)
        """
        import time
        clean_sql = sql_query.strip()
        
        # Security check: Block any modifying/destructive keywords
        forbidden = [r'\bDROP\b', r'\bTRUNCATE\b', r'\bDELETE\b', r'\bALTER\b', r'\bINSERT\b', r'\bUPDATE\b', r'\bEXEC\b', r'\bEXECUTE\b', r'\bGRANT\b', r'\bREVOKE\b']
        for pattern in forbidden:
            if re.search(pattern, clean_sql, re.IGNORECASE):
                kw = pattern.replace(r'\b', '')
                return False, {}, 0.0, f"Query blocked for security reasons (destructive command detected: {kw}). Read-only queries only."

        start_time = time.time()
        try:
            conn = cls.get_connection(db_name, instance_name=instance_name)
            cursor = conn.cursor()
            cursor.execute(clean_sql)
            
            headers = [col[0] for col in cursor.description] if cursor.description else []
            rows_raw = cursor.fetchall() if cursor.description else []
            
            # Format row values cleanly (dates, decimals, None)
            formatted_rows = []
            for r in rows_raw:
                formatted_rows.append([str(val) if val is not None else 'NULL' for val in r])

            duration_ms = round((time.time() - start_time) * 1000, 2)
            cursor.close()
            conn.close()

            result_dict = {
                'headers': headers,
                'rows': formatted_rows,
                'row_count': len(formatted_rows)
            }
            return True, result_dict, duration_ms, ""
        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return False, {}, duration_ms, str(e)

