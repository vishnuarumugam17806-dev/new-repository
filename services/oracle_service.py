"""
DB VITHRA — Oracle Service Module
Handles Oracle connection lifecycle, schema management, dictionary introspection, DDL creation, and PL/SQL queries.
"""
import os
import re
import logging
from typing import Dict, List, Tuple, Any, Optional
from services.base_adapter import BaseDatabaseAdapter

logger = logging.getLogger(__name__)

class OracleAdapter(BaseDatabaseAdapter):
    @classmethod
    def get_connection(cls, host: str = 'localhost', port: int = 1521, service: str = 'XE', user: str = 'system', password: str = ''):
        """Get Oracle connection using oracledb or cx_Oracle."""
        try:
            import oracledb
            dsn = f"{host}:{port}/{service}"
            return oracledb.connect(user=user, password=password, dsn=dsn)
        except ImportError:
            import cx_Oracle
            dsn = cx_Oracle.makedsn(host, port, service_name=service)
            return cx_Oracle.connect(user=user, password=password, dsn=dsn)

    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
            ver = cursor.fetchone()
            version_str = ver[0] if ver else "Oracle Database"
            cursor.close()
            conn.close()
            return True, f"Connection Successful! Connected to Oracle {host}:{port}/{service} ({version_str})"
        except Exception as e:
            logger.error(f"Oracle connection failed: {e}")
            return False, f"Oracle Connection Failed: {str(e)}"

    def create_database(self, db_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """In Oracle, creating a database refers to creating a user/schema or tablespace."""
        if not db_name or not re.match(r'^[A-Za-z0-9_]+$', db_name):
            return False, "Invalid Oracle schema name. Use alphanumeric characters and underscores."

        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            # Check if schema user exists
            cursor.execute("SELECT username FROM all_users WHERE username = UPPER(:1)", [db_name])
            if not cursor.fetchone():
                cursor.execute(f"CREATE USER {db_name} IDENTIFIED BY \"OracleSecret123!\"")
                cursor.execute(f"GRANT CONNECT, RESOURCE, CREATE VIEW, UNLIMITED TABLESPACE TO {db_name}")
                cursor.close()
                conn.close()
                return True, f"Oracle Schema/User `{db_name.upper()}` created successfully."
            else:
                cursor.close()
                conn.close()
                return True, f"Oracle Schema `{db_name.upper()}` is ready for use."
        except Exception as e:
            logger.error(f"Oracle create database error: {e}")
            return False, f"Oracle Schema Creation Error: {str(e)}"

    def list_databases(self, config: Dict[str, Any]) -> List[str]:
        host = config.get('host') or 'localhost'
        port = config.get('port') or 1521
        service = config.get('service') or 'XE'
        user = (config.get('username') or 'SYSTEM').upper()
        pwd = config.get('password') or ''
        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM all_users WHERE username NOT IN ('SYS','SYSTEM','OUTLN','DBSNMP','APPQOSSYS','XDB') ORDER BY username")
            rows = cursor.fetchall()
            schemas = [r[0] for r in rows]
            if not schemas:
                schemas = [user]
            cursor.close()
            conn.close()
            return schemas
        except Exception as e:
            logger.error(f"Oracle list databases error: {e}")
            return [user]

    def list_tables(self, db_name: str, config: Dict[str, Any]) -> List[str]:
        host = config.get('host') or 'localhost'
        port = config.get('port') or 1521
        service = config.get('service') or 'XE'
        user = (config.get('username') or 'SYSTEM').upper()
        pwd = config.get('password') or ''
        db_name = (db_name or user).upper()
        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute("SELECT table_name FROM all_tables WHERE owner = UPPER(:1) ORDER BY table_name", [db_name])
            rows = cursor.fetchall()
            tables = [r[0] for r in rows]
            cursor.close()
            conn.close()
            return tables
        except Exception as e:
            logger.error(f"Oracle list tables error: {e}")
            return []

    def get_schema(self, db_name: str, table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')
        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT column_name, data_type, nullable, data_length
                FROM all_tab_columns
                WHERE owner = UPPER(:1) AND table_name = UPPER(:2)
                ORDER BY column_id
            """, [db_name, table_name])
            cols_raw = cursor.fetchall()

            # Record count
            cursor.execute(f"SELECT COUNT(*) FROM {db_name}.{table_name}")
            row_count = cursor.fetchone()[0]

            columns = []
            for col in cols_raw:
                columns.append({
                    'name': col[0],
                    'type': col[1],
                    'nullable': col[2] == 'Y',
                    'primary_key': col[0].upper().endswith('_ID') or col[0].upper() == 'ID'
                })

            cursor.close()
            conn.close()
            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': [c['name'] for c in columns if c['primary_key']],
                'row_count': row_count,
                'db_type': 'oracle'
            }
        except Exception as e:
            logger.error(f"Oracle get schema error: {e}")
            return {'table_name': table_name, 'columns': [], 'primary_keys': [], 'row_count': 0, 'error': str(e)}

    def create_table(self, db_name: str, table_name: str, columns: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        if not re.match(r'^[A-Za-z0-9_]+$', table_name):
            return False, "Invalid Oracle table name."

        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        col_defs = []
        pks = []
        for c in columns:
            cname = c.get('name')
            ctype = c.get('type', 'VARCHAR2(255)')
            if ctype.upper() == 'VARCHAR' or ctype.upper() == 'TEXT':
                ctype = 'VARCHAR2(4000)'
            elif ctype.upper() in ['INT', 'INTEGER']:
                ctype = 'NUMBER(10)'

            nullable = 'NULL' if c.get('nullable', True) else 'NOT NULL'
            if c.get('primary_key'):
                pks.append(cname)
            col_defs.append(f"\"{cname}\" {ctype} {nullable}".strip())

        if pks:
            pk_cols = ", ".join(['"' + p + '"' for p in pks])
            col_defs.append(f"CONSTRAINT PK_{table_name} PRIMARY KEY ({pk_cols})")

        create_sql = f"CREATE TABLE \"{db_name}\".\"{table_name}\" (\n  " + ",\n  ".join(col_defs) + "\n)"

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute(create_sql)
            cursor.close()
            conn.close()
            return True, f"Table `{table_name}` created successfully in Oracle schema `{db_name}`."
        except Exception as e:
            logger.error(f"Oracle create table error: {e}")
            return False, f"Oracle Create Table Error: {str(e)}"

    def query(self, db_name: str, table_name: str, query_filter: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = config or {}
        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        offset = (page - 1) * per_page
        search_term = (query_filter or {}).get('search', '').strip()

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()

            schema = self.get_schema(db_name, table_name, config)
            col_names = [c['name'] for c in schema.get('columns', [])]

            where_clause = ""
            params = []
            if search_term and col_names:
                conditions = [f"UPPER(\"{c}\") LIKE UPPER(:{i+1})" for i, c in enumerate(col_names)]
                where_clause = " WHERE " + " OR ".join(conditions)
                params = [f"%{search_term}%"] * len(col_names)

            count_sql = f"SELECT COUNT(*) FROM \"{db_name}\".\"{table_name}\"{where_clause}"
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()[0]

            data_sql = f"SELECT * FROM \"{db_name}\".\"{table_name}\"{where_clause} OFFSET {offset} ROWS FETCH NEXT {per_page} ROWS ONLY"
            cursor.execute(data_sql, params)
            raw_rows = cursor.fetchall()

            rows = [dict(zip(col_names, r)) for r in raw_rows]

            cursor.close()
            conn.close()
            return {
                'data': rows,
                'columns': col_names,
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': max(1, (total_count + per_page - 1) // per_page)
            }
        except Exception as e:
            logger.error(f"Oracle query error: {e}")
            return {'data': [], 'columns': [], 'total_count': 0, 'page': 1, 'per_page': per_page, 'error': str(e)}

    def insert_record(self, db_name: str, table_name: str, record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        if not record:
            return False, "Record is empty."

        keys = list(record.keys())
        cols = ", ".join([f"\"{k}\"" for k in keys])
        placeholders = ", ".join([f":{i+1}" for i in range(len(keys))])
        vals = [record[k] for k in keys]
        sql = f"INSERT INTO \"{db_name}\".\"{table_name}\" ({cols}) VALUES ({placeholders})"

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute(sql, vals)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record inserted into Oracle table `{table_name}`."
        except Exception as e:
            logger.error(f"Oracle insert record error: {e}")
            return False, f"Oracle Insert Error: {str(e)}"

    def update_record(self, db_name: str, table_name: str, record_id: Any, updates: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        schema = self.get_schema(db_name, table_name, config)
        pk = schema.get('primary_keys', ['ID'])[0] if schema.get('primary_keys') else 'ID'

        set_clause = ", ".join([f"\"{k}\" = :{i+1}" for i, k in enumerate(updates.keys())])
        vals = list(updates.values()) + [record_id]
        sql = f"UPDATE \"{db_name}\".\"{table_name}\" SET {set_clause} WHERE \"{pk}\" = :{len(vals)}"

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute(sql, vals)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record `{pk}`={record_id} updated in Oracle table `{table_name}`."
        except Exception as e:
            logger.error(f"Oracle update record error: {e}")
            return False, f"Oracle Update Error: {str(e)}"

    def delete_record(self, db_name: str, table_name: str, record_id: Any, config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 1521)
        service = config.get('service', 'XE')
        user = config.get('username', 'system')
        pwd = config.get('password', '')

        schema = self.get_schema(db_name, table_name, config)
        pk = schema.get('primary_keys', ['ID'])[0] if schema.get('primary_keys') else 'ID'
        sql = f"DELETE FROM \"{db_name}\".\"{table_name}\" WHERE \"{pk}\" = :1"

        try:
            conn = self.get_connection(host=host, port=port, service=service, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute(sql, [record_id])
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record `{pk}`={record_id} deleted from Oracle table `{table_name}`."
        except Exception as e:
            logger.error(f"Oracle delete record error: {e}")
            return False, f"Oracle Delete Error: {str(e)}"
