"""
DB VITHRA — MySQL Service Module
Handles MySQL connection lifecycle, schema creation, introspection, dynamic query execution, and CRUD operations.
"""
import os
import re
import logging
from typing import Dict, List, Tuple, Any, Optional
from services.base_adapter import BaseDatabaseAdapter

logger = logging.getLogger(__name__)

class MySQLAdapter(BaseDatabaseAdapter):
    @classmethod
    def get_connection(cls, host: str = 'localhost', port: int = 3306, user: str = 'root', password: str = '', database: Optional[str] = None):
        """Get MySQL connection using mysql.connector or pymysql as fallback."""
        try:
            import mysql.connector
            conn_kwargs = {
                'host': host or 'localhost',
                'port': int(port) if port else 3306,
                'user': user or 'root',
                'password': password or '',
                'connect_timeout': 3
            }
            if database:
                conn_kwargs['database'] = database
            return mysql.connector.connect(**conn_kwargs)
        except ImportError:
            import pymysql
            conn_kwargs = {
                'host': host or 'localhost',
                'port': int(port) if port else 3306,
                'user': user or 'root',
                'password': password or '',
                'connect_timeout': 3,
                'cursorclass': pymysql.cursors.DictCursor
            }
            if database:
                conn_kwargs['database'] = database
            return pymysql.connect(**conn_kwargs)

    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            ver = cursor.fetchone()
            version_str = ver[0] if isinstance(ver, tuple) else (ver.get('VERSION()') if isinstance(ver, dict) else str(ver))
            cursor.close()
            conn.close()
            return True, f"Connection Successful! Connected to MySQL Host {host}:{port} (Version: {version_str})"
        except Exception as e:
            logger.error(f"MySQL connection failed: {e}")
            return False, f"Connection Failed: {str(e)}"

    def create_database(self, db_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        if not db_name or not re.match(r'^[A-Za-z0-9_]+$', db_name):
            return False, "Invalid MySQL database name. Use letters, numbers, and underscores only."

        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4")
            cursor.close()
            conn.close()
            return True, f"Database `{db_name}` successfully created on MySQL host {host}."
        except Exception as e:
            logger.error(f"MySQL create database error: {e}")
            return False, f"Failed to create MySQL database: {str(e)}"

    def list_databases(self, config: Dict[str, Any]) -> List[str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')
        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd)
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            rows = cursor.fetchall()
            dbs = []
            for r in rows:
                val = r[0] if isinstance(r, tuple) else list(r.values())[0]
                if val not in ['information_schema', 'mysql', 'performance_schema', 'sys']:
                    dbs.append(val)
            cursor.close()
            conn.close()
            return dbs
        except Exception as e:
            logger.error(f"MySQL list databases error: {e}")
            return []

    def list_tables(self, db_name: str, config: Dict[str, Any]) -> List[str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')
        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            rows = cursor.fetchall()
            tables = []
            for r in rows:
                val = r[0] if isinstance(r, tuple) else list(r.values())[0]
                tables.append(val)
            cursor.close()
            conn.close()
            return tables
        except Exception as e:
            logger.error(f"MySQL list tables error for {db_name}: {e}")
            return []

    def get_schema(self, db_name: str, table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')
        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE `{table_name}`")
            cols_info = cursor.fetchall()

            # Record count
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            row_count_res = cursor.fetchone()
            count = row_count_res[0] if isinstance(row_count_res, tuple) else list(row_count_res.values())[0]

            columns = []
            primary_keys = []
            for col in cols_info:
                if isinstance(col, tuple):
                    field, dtype, null, key, default, extra = col[0], col[1], col[2], col[3], col[4], col[5]
                else:
                    field = col.get('Field')
                    dtype = col.get('Type')
                    null = col.get('Null')
                    key = col.get('Key')
                    default = col.get('Default')
                    extra = col.get('Extra')

                columns.append({
                    'name': field,
                    'type': dtype,
                    'nullable': null == 'YES',
                    'primary_key': key == 'PRI',
                    'default': default,
                    'extra': extra
                })
                if key == 'PRI':
                    primary_keys.append(field)

            cursor.close()
            conn.close()
            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': primary_keys,
                'row_count': count,
                'db_type': 'mysql'
            }
        except Exception as e:
            logger.error(f"MySQL get schema error for {db_name}.{table_name}: {e}")
            return {'table_name': table_name, 'columns': [], 'primary_keys': [], 'row_count': 0, 'error': str(e)}

    def create_table(self, db_name: str, table_name: str, columns: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        if not re.match(r'^[A-Za-z0-9_]+$', table_name):
            return False, "Invalid MySQL table name."

        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        col_defs = []
        pks = []
        for c in columns:
            cname = c.get('name')
            ctype = c.get('type', 'VARCHAR(255)')
            nullable = 'NULL' if c.get('nullable', True) else 'NOT NULL'
            auto_inc = 'AUTO_INCREMENT' if c.get('auto_increment') else ''
            if c.get('primary_key'):
                pks.append(f"`{cname}`")
            col_defs.append(f"`{cname}` {ctype} {nullable} {auto_inc}".strip())

        if pks:
            col_defs.append(f"PRIMARY KEY ({', '.join(pks)})")

        create_sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n  " + ",\n  ".join(col_defs) + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()
            cursor.execute(create_sql)
            cursor.close()
            conn.close()
            return True, f"Table `{table_name}` created successfully in MySQL database `{db_name}`."
        except Exception as e:
            logger.error(f"MySQL create table error: {e}")
            return False, f"Failed to create MySQL table: {str(e)}"

    def query(self, db_name: str, table_name: str, query_filter: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = config or {}
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        offset = (page - 1) * per_page
        search_term = (query_filter or {}).get('search', '').strip()

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()

            # Get columns
            schema = self.get_schema(db_name, table_name, config)
            col_names = [c['name'] for c in schema.get('columns', [])]

            where_clause = ""
            params = []
            if search_term and col_names:
                conditions = [f"`{c}` LIKE %s" for c in col_names]
                where_clause = " WHERE " + " OR ".join(conditions)
                params = [f"%{search_term}%"] * len(col_names)

            # Count query
            count_sql = f"SELECT COUNT(*) FROM `{table_name}`{where_clause}"
            cursor.execute(count_sql, params)
            count_res = cursor.fetchone()
            total_count = count_res[0] if isinstance(count_res, tuple) else list(count_res.values())[0]

            # Data query
            data_sql = f"SELECT * FROM `{table_name}`{where_clause} LIMIT %s OFFSET %s"
            cursor.execute(data_sql, params + [per_page, offset])
            raw_rows = cursor.fetchall()

            rows = []
            for r in raw_rows:
                if isinstance(r, tuple):
                    rows.append(dict(zip(col_names, r)))
                else:
                    rows.append(r)

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
            logger.error(f"MySQL query error for {db_name}.{table_name}: {e}")
            return {'data': [], 'columns': [], 'total_count': 0, 'page': 1, 'per_page': per_page, 'error': str(e)}

    def insert_record(self, db_name: str, table_name: str, record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        if not record:
            return False, "Record cannot be empty."

        keys = list(record.keys())
        cols = ", ".join([f"`{k}`" for k in keys])
        placeholders = ", ".join(["%s"] * len(keys))
        vals = [record[k] for k in keys]
        sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})"

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()
            cursor.execute(sql, vals)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record successfully inserted into MySQL table `{table_name}`."
        except Exception as e:
            logger.error(f"MySQL insert record error: {e}")
            return False, f"MySQL Insert Error: {str(e)}"

    def update_record(self, db_name: str, table_name: str, record_id: Any, updates: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        schema = self.get_schema(db_name, table_name, config)
        pk = schema.get('primary_keys', ['id'])[0] if schema.get('primary_keys') else 'id'

        if not updates:
            return False, "No update values provided."

        set_clause = ", ".join([f"`{k}` = %s" for k in updates.keys()])
        vals = list(updates.values()) + [record_id]
        sql = f"UPDATE `{table_name}` SET {set_clause} WHERE `{pk}` = %s"

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()
            cursor.execute(sql, vals)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record `{pk}`={record_id} updated successfully in MySQL table `{table_name}`."
        except Exception as e:
            logger.error(f"MySQL update record error: {e}")
            return False, f"MySQL Update Error: {str(e)}"

    def delete_record(self, db_name: str, table_name: str, record_id: Any, config: Dict[str, Any]) -> Tuple[bool, str]:
        host = config.get('host', 'localhost')
        port = config.get('port', 3306)
        user = config.get('username', 'root')
        pwd = config.get('password', '')

        schema = self.get_schema(db_name, table_name, config)
        pk = schema.get('primary_keys', ['id'])[0] if schema.get('primary_keys') else 'id'
        sql = f"DELETE FROM `{table_name}` WHERE `{pk}` = %s"

        try:
            conn = self.get_connection(host=host, port=port, user=user, password=pwd, database=db_name)
            cursor = conn.cursor()
            cursor.execute(sql, [record_id])
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record `{pk}`={record_id} deleted successfully from MySQL table `{table_name}`."
        except Exception as e:
            logger.error(f"MySQL delete record error: {e}")
            return False, f"MySQL Delete Error: {str(e)}"
