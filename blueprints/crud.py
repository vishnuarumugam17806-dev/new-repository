"""
SMART DB — SQL Server Dynamic CRUD Interface Blueprint
Allows browsing, inserting, updating, and deleting records in SQL Server databases.
Works by dynamically introspecting table and column definitions on the SQL Server instance.
"""
import os
import re
import logging
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, abort
)
from flask_login import current_user
import config as cfg
from models import db, SharedDatabase
from services.sqlserver_service import SqlServerService

logger = logging.getLogger(__name__)

crud_bp = Blueprint('crud', __name__)

def _get_connection(db_name: str):
    """Obtain a pyodbc connection to the specific SQL Server database."""
    return SqlServerService.get_connection(db_name)

def _get_tables(conn) -> list[str]:
    """Fetch all user tables from the SQL Server database."""
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
    return tables

def _get_columns(conn, table: str) -> list[dict]:
    """Introspect column details for a given table in SQL Server."""
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
    cursor.execute(query, table)
    cols = []
    for idx, row in enumerate(cursor.fetchall()):
        cols.append({
            'cid':       idx,
            'name':      row[0],
            'type':      row[1].upper(),
            'notnull':   row[2],
            'dflt_value': row[3],
            'pk':        row[4],
        })
    cursor.close()
    return cols

def _get_pk_col(columns: list[dict]) -> str | None:
    """Return the name of the primary key column, if any."""
    for col in columns:
        if col['pk'] == 1:
            return col['name']
    return None

def _fetch_rows_as_dicts(cursor) -> list[dict]:
    """Utility to convert cursor output into list of dictionaries."""
    col_names = [col[0] for col in cursor.description]
    return [dict(zip(col_names, row)) for row in cursor.fetchall()]

# ── Routes ────────────────────────────────────────────────────────────────────

@crud_bp.route('/crud/<int:db_id>')
def crud_home(db_id):
    """Show all tables in the SQL Server database."""
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        abort(404)

    db_name = database.project_name
    
    # Verify database still exists in SQL Server
    if not SqlServerService.check_db_exists(db_name):
        flash(f"SQL Server database '{db_name}' could not be reached. It may have been modified or dropped.", "danger")
        return redirect(url_for('auth.dashboard'))

    try:
        conn   = _get_connection(db_name)
        tables = _get_tables(conn)
        table_info = []
        for tbl in tables:
            cols  = _get_columns(conn, tbl)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM [{tbl}]")
            count = cursor.fetchone()[0]
            cursor.close()
            table_info.append({'name': tbl, 'columns': cols, 'row_count': count})
        conn.close()
    except Exception as e:
        logger.error(f"Failed to introspect SQL Server database {db_name}: {e}")
        flash(f"Failed to connect to database: {e}", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('crud.html',
        database=database,
        table_info=table_info,
        active_table=None,
        rows=None,
        columns=None,
        mode='home',
    )


@crud_bp.route('/crud/<int:db_id>/<table_name>')
def crud_table(db_id, table_name):
    """List all records in the given table with SQL Server paging."""
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        abort(404)

    db_name = database.project_name
    
    if not SqlServerService.check_db_exists(db_name):
        flash(f"SQL Server database '{db_name}' not found.", "danger")
        return redirect(url_for('auth.dashboard'))

    try:
        conn    = _get_connection(db_name)
        tables  = _get_tables(conn)
        if table_name not in tables:
            conn.close()
            abort(404)

        columns = _get_columns(conn, table_name)
        pk_col  = _get_pk_col(columns)
        
        # Paging configuration
        page    = request.args.get('page', 1, type=int)
        per_page = 25
        offset  = (page - 1) * per_page
        
        # Get count
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        total = cursor.fetchone()[0]
        
        # Query with offset (SQL Server 2012+ offset fetch syntax)
        order_by = f"[{pk_col}]" if pk_col else "(SELECT NULL)"
        paging_query = f"SELECT * FROM [{table_name}] ORDER BY {order_by} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        cursor.execute(paging_query, (offset, per_page))
        rows = _fetch_rows_as_dicts(cursor)
        cursor.close()

        # Build table sidebar summary
        table_info = []
        for tbl in tables:
            cols  = _get_columns(conn, tbl)
            c_cur = conn.cursor()
            c_cur.execute(f"SELECT COUNT(*) FROM [{tbl}]")
            count = c_cur.fetchone()[0]
            c_cur.close()
            table_info.append({'name': tbl, 'columns': cols, 'row_count': count})
            
        conn.close()
    except Exception as e:
        logger.error(f"CRUD browse failed for {db_name}.{table_name}: {e}")
        flash(f"Database query failed: {e}", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('crud.html',
        database=database,
        table_info=table_info,
        active_table=table_name,
        columns=columns,
        rows=rows,
        mode='list',
        page=page,
        per_page=per_page,
        total=total,
        pk_col=pk_col,
    )


@crud_bp.route('/crud/<int:db_id>/<table_name>/insert', methods=['GET', 'POST'])
def crud_insert(db_id, table_name):
    """Insert a new record into the SQL Server table."""
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        abort(404)

    db_name = database.project_name
    
    try:
        conn    = _get_connection(db_name)
        columns = _get_columns(conn, table_name)
        pk_col  = _get_pk_col(columns)
        
        # In SQL Server, exclude columns with identity or defaults if empty
        insert_cols = [c for c in columns if not (c['pk'] == 1 and ('INT' in c['type'].upper()))]

        if request.method == 'POST':
            col_names  = [c['name'] for c in insert_cols]
            col_values = []
            
            # Map form values, handling bit conversion and nulls
            for c in insert_cols:
                val = request.form.get(c['name'], '').strip()
                if val == '' or val.upper() == 'NONE':
                    col_values.append(None)
                elif c['type'] == 'BIT':
                    col_values.append(1 if val in ('1', 'True', 'true', 'on') else 0)
                else:
                    col_values.append(val)
                    
            placeholders = ', '.join(['?' for _ in col_names])
            names_str    = ', '.join([f"[{n}]" for n in col_names])
            insert_query = f"INSERT INTO [{table_name}] ({names_str}) VALUES ({placeholders})"
            
            cursor = conn.cursor()
            try:
                cursor.execute(insert_query, col_values)
                conn.commit()
                flash(f"Record successfully inserted into '{table_name}'! ✅", "success")
            except Exception as insert_err:
                conn.rollback()
                flash(f"Insert failed: {insert_err}", "danger")
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('crud.crud_table', db_id=db_id, table_name=table_name))

        conn.close()
    except Exception as e:
        logger.error(f"CRUD insert failed: {e}")
        flash(f"Failed to access table metadata: {e}", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('crud.html',
        database=database,
        table_info=[],
        active_table=table_name,
        columns=columns,
        insert_cols=insert_cols,
        rows=None,
        mode='insert',
        pk_col=pk_col,
    )


@crud_bp.route('/crud/<int:db_id>/<table_name>/edit/<row_id>', methods=['GET', 'POST'])
def crud_edit(db_id, table_name, row_id):
    """Edit an existing record in SQL Server table."""
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        abort(404)

    db_name = database.project_name
    
    try:
        conn    = _get_connection(db_name)
        columns = _get_columns(conn, table_name)
        pk_col  = _get_pk_col(columns)
        if not pk_col:
            flash("Cannot edit record: no primary key column found.", "danger")
            conn.close()
            return redirect(url_for('crud.crud_table', db_id=db_id, table_name=table_name))

        edit_cols = [c for c in columns if not (c['pk'] == 1 and ('INT' in c['type'].upper()))]
        
        # Retrieve row by PK
        cursor = conn.cursor()
        select_query = f"SELECT * FROM [{table_name}] WHERE [{pk_col}] = ?"
        cursor.execute(select_query, row_id)
        row_data = cursor.fetchone()
        
        if not row_data:
            cursor.close()
            conn.close()
            abort(404)
            
        row_dict = dict(zip([col[0] for col in cursor.description], row_data))
        cursor.close()

        if request.method == 'POST':
            set_parts  = [f"[{c['name']}] = ?" for c in edit_cols]
            set_values = []
            
            for c in edit_cols:
                val = request.form.get(c['name'], '').strip()
                if val == '' or val.upper() == 'NONE':
                    set_values.append(None)
                elif c['type'] == 'BIT':
                    set_values.append(1 if val in ('1', 'True', 'true', 'on') else 0)
                else:
                    set_values.append(val)
                    
            update_query = f"UPDATE [{table_name}] SET {', '.join(set_parts)} WHERE [{pk_col}] = ?"
            cursor = conn.cursor()
            try:
                cursor.execute(update_query, set_values + [row_id])
                conn.commit()
                flash(f"Record #{row_id} updated successfully! ✅", "success")
            except Exception as update_err:
                conn.rollback()
                flash(f"Update failed: {update_err}", "danger")
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('crud.crud_table', db_id=db_id, table_name=table_name))

        conn.close()
    except Exception as e:
        logger.error(f"CRUD edit failed: {e}")
        flash(f"Database edit operation failed: {e}", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('crud.html',
        database=database,
        table_info=[],
        active_table=table_name,
        columns=columns,
        edit_cols=edit_cols,
        row=row_dict,
        rows=None,
        mode='edit',
        pk_col=pk_col,
        row_id=row_id,
    )


@crud_bp.route('/crud/<int:db_id>/<table_name>/delete/<row_id>', methods=['POST'])
def crud_delete(db_id, table_name, row_id):
    """Delete a record from SQL Server table."""
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        abort(404)

    db_name = database.project_name
    
    try:
        conn    = _get_connection(db_name)
        columns = _get_columns(conn, table_name)
        pk_col  = _get_pk_col(columns)
        if not pk_col:
            flash("Cannot delete record: no primary key column found.", "danger")
            conn.close()
            return redirect(url_for('crud.crud_table', db_id=db_id, table_name=table_name))

        cursor = conn.cursor()
        delete_query = f"DELETE FROM [{table_name}] WHERE [{pk_col}] = ?"
        try:
            cursor.execute(delete_query, row_id)
            conn.commit()
            flash(f"Record #{row_id} deleted successfully from '{table_name}'. 🗑️", "info")
        except Exception as delete_err:
            conn.rollback()
            flash(f"Delete failed: {delete_err}", "danger")
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"CRUD delete failed: {e}")
        flash(f"Database delete operation failed: {e}", "danger")
        
    return redirect(url_for('crud.crud_table', db_id=db_id, table_name=table_name))


@crud_bp.route('/crud/<int:db_id>/<table_name>/api-rows')
def crud_api_rows(db_id, table_name):
    """JSON API for AJAX dynamic table refresh (limited to 100 rows)."""
    database = db.session.get(SharedDatabase, db_id)
    if database is None:
        return jsonify({'error': 'Not found'}), 404
        
    db_name = database.project_name
    try:
        conn = _get_connection(db_name)
        cursor = conn.cursor()
        cursor.execute(f"SELECT TOP 100 * FROM [{table_name}]")
        rows = _fetch_rows_as_dicts(cursor)
        cursor.close()
        conn.close()
        return jsonify({'rows': rows})
    except Exception as e:
        logger.error(f"API rows fetch failed: {e}")
        return jsonify({'error': str(e)}), 500

