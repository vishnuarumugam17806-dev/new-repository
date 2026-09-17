"""
SMART DB — Comprehensive Multi-Platform AI Query Assistant & Training Verification Tests
Tests SQL Server, MySQL, Oracle, MongoDB, and Excel generation across DML, DDL, queries, and conceptual doubts.
"""
import pytest
from ai_engine.fallback_engine import FallbackEngine

def test_multi_platform_query_dialects():
    engine = FallbackEngine()

    # 1. MongoDB Query & Count
    res_mongo_find = engine.nl_to_sql("Show all patients older than 50", "", db_type="mongodb")
    assert "db.patients.find(" in res_mongo_find["sql"]
    assert '"age": {"$gt": 50}' in res_mongo_find["sql"]
    assert res_mongo_find["tables_used"] == ["patients"]

    res_mongo_count = engine.nl_to_sql("Count the number of patients", "", db_type="mongodb")
    assert "db.patients.countDocuments(" in res_mongo_count["sql"]

    # 2. Excel (Python Pandas)
    res_excel = engine.nl_to_sql("Show top 5 products by price", "", db_type="excel")
    assert "filtered_df" in res_excel["sql"] or "df" in res_excel["sql"]
    assert "head(5)" in res_excel["sql"]
    assert "to_excel" in res_excel["sql"]

    res_excel_count = engine.nl_to_sql("Count total patients", "", db_type="excel")
    assert "len(df)" in res_excel_count["sql"]

    # 3. MySQL Dialect
    res_mysql = engine.nl_to_sql("Show top 10 customers", "", db_type="mysql")
    assert "LIMIT 10" in res_mysql["sql"]
    assert "`customers`" in res_mysql["sql"]

    # 4. Oracle Dialect
    res_oracle = engine.nl_to_sql("Show top 10 customers", "", db_type="oracle")
    assert "FETCH FIRST 10 ROWS ONLY" in res_oracle["sql"]
    assert '"CUSTOMERS"' in res_oracle["sql"]

    # 5. SQL Server Dialect
    res_mssql = engine.nl_to_sql("Show top 5 patients", "", db_type="mssql")
    assert "TOP 5" in res_mssql["sql"]
    assert "[patients]" in res_mssql["sql"]


def test_dml_command_generation():
    engine = FallbackEngine()

    # INSERT
    res_insert_sql = engine.nl_to_sql("Add a new customer named Arun", "", db_type="sqlserver")
    assert "INSERT INTO" in res_insert_sql["sql"]
    assert "Arun" in res_insert_sql["sql"]
    assert "GETDATE()" in res_insert_sql["sql"]

    res_insert_mongo = engine.nl_to_sql("Add a new customer named Arun", "", db_type="mongodb")
    assert "db.customers.insertOne(" in res_insert_mongo["sql"]
    assert '"name": "Arun"' in res_insert_mongo["sql"]

    # UPDATE
    res_update_sql = engine.nl_to_sql("Change Arun phone number to 9876543210", "", db_type="sqlserver")
    assert "UPDATE" in res_update_sql["sql"]
    assert "9876543210" in res_update_sql["sql"]
    assert "Arun" in res_update_sql["sql"]

    res_update_mongo = engine.nl_to_sql("Change Arun phone number to 9876543210", "", db_type="mongodb")
    assert "db.customers.updateOne(" in res_update_mongo["sql"]
    assert "9876543210" in res_update_mongo["sql"]

    # DELETE
    res_delete = engine.nl_to_sql("Delete customer Arun", "", db_type="sqlserver")
    assert "DELETE FROM" in res_delete["sql"]
    assert "Arun" in res_delete["sql"]


def test_conceptual_doubt_resolution():
    engine = FallbackEngine()

    # Indexing
    res_idx = engine.nl_to_sql("Explain difference between clustered and non-clustered index", "", db_type="sqlserver")
    assert "Clustered Index" in res_idx["explanation"]
    assert "CREATE CLUSTERED INDEX" in res_idx["sql"]
    assert "CREATE NONCLUSTERED INDEX" in res_idx["sql"]

    # Normalization
    res_norm = engine.nl_to_sql("Explain 1NF 2NF 3NF and BCNF normalization", "", db_type="sqlserver")
    assert "Normalization" in res_norm["explanation"]
    assert "1NF" in res_norm["sql"]

    # ACID Properties
    res_acid = engine.nl_to_sql("What are ACID properties in database transactions?", "", db_type="sqlserver")
    assert "Atomicity" in res_acid["explanation"]
    assert "BEGIN TRANSACTION" in res_acid["sql"]

    # Deadlocks
    res_deadlock = engine.nl_to_sql("What is a deadlock and how to prevent it?", "", db_type="sqlserver")
    assert "deadlock" in res_deadlock["explanation"].lower()
    assert len(res_deadlock["optimization_tips"]) > 0
