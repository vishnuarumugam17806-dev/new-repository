"""
DB VITHRA — Universal Connection & Database Adapter Manager
Dispatches database lifecycle, querying, connection testing, and CRUD operations to SQLServerAdapter, MySQLAdapter, OracleAdapter, MongoDBAdapter, or ExcelAdapter.
"""
import logging
from typing import Dict, List, Tuple, Any, Optional
from services.base_adapter import BaseDatabaseAdapter
from services.sqlserver_service import SqlServerService
from services.mysql_service import MySQLAdapter
from services.oracle_service import OracleAdapter
from services.mongodb_service import MongoDBAdapter
from services.excel_service import ExcelAdapter

logger = logging.getLogger(__name__)

# Adapter registry map
_adapters: Dict[str, BaseDatabaseAdapter] = {
    'mysql': MySQLAdapter(),
    'oracle': OracleAdapter(),
    'mongodb': MongoDBAdapter(),
    'excel': ExcelAdapter()
}

class SQLServerAdapterWrapper(BaseDatabaseAdapter):
    """Adapter wrapper around SqlServerService to enforce BaseDatabaseAdapter interface."""
    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        instance = config.get('instance_name') or config.get('server') or SqlServerService.get_server()
        return SqlServerService.test_connection(instance)

    def create_database(self, db_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        valid, msg = SqlServerService.validate_database_name(db_name)
        if not valid:
            return False, msg
        instance = config.get('instance_name') or SqlServerService.get_server()
        try:
            conn = SqlServerService.get_connection('master', autocommit=True, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute(f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{db_name}') CREATE DATABASE [{db_name}]")
            cursor.close()
            conn.close()
            return True, f"SQL Server Database `[{db_name}]` created successfully on instance `{instance}`."
        except Exception as e:
            return False, f"SQL Server Database Creation Error: {str(e)}"

    def list_databases(self, config: Dict[str, Any]) -> List[str]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        try:
            conn = SqlServerService.get_connection('master', instance_name=instance)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb') ORDER BY name")
            rows = cursor.fetchall()
            dbs = [r[0] for r in rows]
            cursor.close()
            conn.close()
            return dbs
        except Exception:
            return [SqlServerService.get_system_db_name()]

    def list_tables(self, db_name: str, config: Dict[str, Any]) -> List[str]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
            rows = cursor.fetchall()
            tables = [r[0] for r in rows]
            cursor.close()
            conn.close()
            return tables
        except Exception:
            return []

    def get_schema(self, db_name: str, table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """, (table_name,))
            rows = cursor.fetchall()

            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            count = cursor.fetchone()[0]

            columns = []
            for r in rows:
                cname, dtype, nullable, default = r[0], r[1], r[2] == 'YES', r[3]
                columns.append({
                    'name': cname,
                    'type': dtype,
                    'nullable': nullable,
                    'primary_key': cname.lower().endswith('id') or cname.lower() == 'id'
                })

            cursor.close()
            conn.close()
            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': [c['name'] for c in columns if c['primary_key']],
                'row_count': count,
                'db_type': 'sqlserver'
            }
        except Exception as e:
            return {'table_name': table_name, 'columns': [], 'primary_keys': [], 'row_count': 0, 'error': str(e)}

    def create_table(self, db_name: str, table_name: str, columns: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        col_defs = []
        pks = []
        for c in columns:
            cname = c.get('name')
            ctype = c.get('type', 'VARCHAR(255)')
            if ctype.upper() == 'TEXT':
                ctype = 'VARCHAR(MAX)'
            elif ctype.upper() == 'BOOLEAN':
                ctype = 'BIT'

            nullable = 'NULL' if c.get('nullable', True) else 'NOT NULL'
            identity = 'IDENTITY(1,1)' if c.get('auto_increment') or (c.get('primary_key') and 'INT' in ctype.upper()) else ''
            if c.get('primary_key'):
                pks.append(f"[{cname}]")
            col_defs.append(f"[{cname}] {ctype} {identity} {nullable}".strip())

        if pks:
            col_defs.append(f"PRIMARY KEY ({', '.join(pks)})")

        create_sql = f"CREATE TABLE [{table_name}] (\n  " + ",\n  ".join(col_defs) + "\n);"

        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute(create_sql)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"SQL Server Table `[{table_name}]` created successfully in database `[{db_name}]`."
        except Exception as e:
            return False, f"SQL Server Create Table Error: {str(e)}"

    def query(self, db_name: str, table_name: str, query_filter: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = config or {}
        instance = config.get('instance_name') or SqlServerService.get_server()
        offset = (page - 1) * per_page
        search_term = (query_filter or {}).get('search', '').strip()

        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()

            schema = self.get_schema(db_name, table_name, config)
            col_names = [c['name'] for c in schema.get('columns', [])]
            pk = schema.get('primary_keys', [col_names[0] if col_names else 'id'])[0]

            where_clause = ""
            params = []
            if search_term and col_names:
                conditions = [f"[{c}] LIKE ?" for c in col_names]
                where_clause = " WHERE " + " OR ".join(conditions)
                params = [f"%{search_term}%"] * len(col_names)

            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]{where_clause}", params)
            total_count = cursor.fetchone()[0]

            data_sql = f"SELECT * FROM [{table_name}]{where_clause} ORDER BY [{pk}] OFFSET {offset} ROWS FETCH NEXT {per_page} ROWS ONLY"
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
            return {'data': [], 'columns': [], 'total_count': 0, 'page': page, 'per_page': per_page, 'error': str(e)}

    def insert_record(self, db_name: str, table_name: str, record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        keys = list(record.keys())
        cols = ", ".join([f"[{k}]" for k in keys])
        placeholders = ", ".join(["?"] * len(keys))
        vals = [record[k] for k in keys]
        sql = f"INSERT INTO [{table_name}] ({cols}) VALUES ({placeholders})"

        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute(sql, vals)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record inserted into SQL Server table `[{table_name}]`."
        except Exception as e:
            return False, f"SQL Server Insert Error: {str(e)}"

    def update_record(self, db_name: str, table_name: str, record_id: Any, updates: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        schema = self.get_schema(db_name, table_name, config)
        pk = schema.get('primary_keys', ['id'])[0] if schema.get('primary_keys') else 'id'

        set_clause = ", ".join([f"[{k}] = ?" for k in updates.keys()])
        vals = list(updates.values()) + [record_id]
        sql = f"UPDATE [{table_name}] SET {set_clause} WHERE [{pk}] = ?"

        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute(sql, vals)
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record `{pk}`={record_id} updated in SQL Server table `[{table_name}]`."
        except Exception as e:
            return False, f"SQL Server Update Error: {str(e)}"

    def delete_record(self, db_name: str, table_name: str, record_id: Any, config: Dict[str, Any]) -> Tuple[bool, str]:
        instance = config.get('instance_name') or SqlServerService.get_server()
        schema = self.get_schema(db_name, table_name, config)
        pk = schema.get('primary_keys', ['id'])[0] if schema.get('primary_keys') else 'id'
        sql = f"DELETE FROM [{table_name}] WHERE [{pk}] = ?"

        try:
            conn = SqlServerService.get_connection(db_name, instance_name=instance)
            cursor = conn.cursor()
            cursor.execute(sql, [record_id])
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"Record `{pk}`={record_id} deleted from SQL Server table `[{table_name}]`."
        except Exception as e:
            return False, f"SQL Server Delete Error: {str(e)}"

# Register SQL Server wrapper
_adapters['sqlserver'] = SQLServerAdapterWrapper()

class ConnectionManager:
    @staticmethod
    def get_adapter(db_type: str) -> BaseDatabaseAdapter:
        norm_type = (db_type or 'sqlserver').lower().strip()
        if norm_type == 'mssql':
            norm_type = 'sqlserver'
        adapter = _adapters.get(norm_type)
        if not adapter:
            raise ValueError(f"Unsupported database specification type: {db_type}")
        return adapter

    @classmethod
    def test_connection(cls, db_type: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        adapter = cls.get_adapter(db_type)
        return adapter.test_connection(config)

    @classmethod
    def create_database(cls, db_type: str, db_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        adapter = cls.get_adapter(db_type)
        return adapter.create_database(db_name, config)

    @classmethod
    def list_databases(cls, db_type: str, config: Dict[str, Any]) -> List[str]:
        adapter = cls.get_adapter(db_type)
        return adapter.list_databases(config)

    @classmethod
    def list_tables(cls, db_type: str, db_name: str, config: Dict[str, Any]) -> List[str]:
        adapter = cls.get_adapter(db_type)
        return adapter.list_tables(db_name, config)

    @classmethod
    def get_schema(cls, db_type: str, db_name: str, table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        adapter = cls.get_adapter(db_type)
        return adapter.get_schema(db_name, table_name, config)

    @classmethod
    def create_table(cls, db_type: str, db_name: str, table_name: str, columns: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        adapter = cls.get_adapter(db_type)
        return adapter.create_table(db_name, table_name, columns, config)

    @classmethod
    def query(cls, db_type: str, db_name: str, table_name: str, query_filter: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        adapter = cls.get_adapter(db_type)
        return adapter.query(db_name, table_name, query_filter, page, per_page, config)

    @classmethod
    def insert_record(cls, db_type: str, db_name: str, table_name: str, record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        adapter = cls.get_adapter(db_type)
        return adapter.insert_record(db_name, table_name, record, config)

    @classmethod
    def update_record(cls, db_type: str, db_name: str, table_name: str, record_id: Any, updates: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        adapter = cls.get_adapter(db_type)
        return adapter.update_record(db_name, table_name, record_id, updates, config)

    @classmethod
    def delete_record(cls, db_type: str, db_name: str, table_name: str, record_id: Any, config: Dict[str, Any]) -> Tuple[bool, str]:
        adapter = cls.get_adapter(db_type)
        return adapter.delete_record(db_name, table_name, record_id, config)
