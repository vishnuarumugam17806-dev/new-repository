"""
DB VITHRA — AI Query Assistant Tests
Tests 20+ distinct natural language questions to verify unique, schema-aware SQL Server query generation.
"""
import pytest
from ai_engine.fallback_engine import FallbackEngine
from ai_engine.schema_agent import SchemaAgent

TEST_HOSPITAL_SCHEMA = {
    'database_name': 'HospitalManagement',
    'tables': {
        'Patients': {
            'columns': [
                {'name': 'patient_id', 'type': 'INT', 'pk': 1},
                {'name': 'patient_name', 'type': 'NVARCHAR(100)', 'pk': 0},
                {'name': 'age', 'type': 'INT', 'pk': 0},
                {'name': 'gender', 'type': 'NVARCHAR(20)', 'pk': 0},
                {'name': 'phone', 'type': 'NVARCHAR(20)', 'pk': 0},
                {'name': 'registered_date', 'type': 'DATE', 'pk': 0}
            ],
            'foreign_keys': []
        },
        'Doctors': {
            'columns': [
                {'name': 'doctor_id', 'type': 'INT', 'pk': 1},
                {'name': 'doctor_name', 'type': 'NVARCHAR(100)', 'pk': 0},
                {'name': 'specialization', 'type': 'NVARCHAR(100)', 'pk': 0},
                {'name': 'department_id', 'type': 'INT', 'pk': 0}
            ],
            'foreign_keys': []
        },
        'Appointments': {
            'columns': [
                {'name': 'appointment_id', 'type': 'INT', 'pk': 1},
                {'name': 'patient_id', 'type': 'INT', 'pk': 0},
                {'name': 'doctor_id', 'type': 'INT', 'pk': 0},
                {'name': 'appointment_date', 'type': 'DATETIME', 'pk': 0},
                {'name': 'status', 'type': 'NVARCHAR(50)', 'pk': 0}
            ],
            'foreign_keys': [
                {'column': 'patient_id', 'ref_table': 'Patients', 'ref_column': 'patient_id'},
                {'column': 'doctor_id', 'ref_table': 'Doctors', 'ref_column': 'doctor_id'}
            ]
        },
        'Billing': {
            'columns': [
                {'name': 'bill_id', 'type': 'INT', 'pk': 1},
                {'name': 'patient_id', 'type': 'INT', 'pk': 0},
                {'name': 'total_amount', 'type': 'DECIMAL(12,2)', 'pk': 0},
                {'name': 'paid_amount', 'type': 'DECIMAL(12,2)', 'pk': 0},
                {'name': 'status', 'type': 'NVARCHAR(50)', 'pk': 0}
            ],
            'foreign_keys': [
                {'column': 'patient_id', 'ref_table': 'Patients', 'ref_column': 'patient_id'}
            ]
        }
    }
}

QUESTIONS_AND_EXPECTATIONS = [
    ("Show all patients.", "Patients", "SELECT"),
    ("Show patients older than 50.", "Patients", "WHERE [age] > 50"),
    ("Show patients younger than 30.", "Patients", "WHERE [age] < 30"),
    ("Show the names of all doctors.", "Doctors", "doctor_name"),
    ("How many patients are there?", "Patients", "COUNT(*)"),
    ("Show appointments with patient and doctor names.", "Appointments", "JOIN"),
    ("Find the oldest patient.", "Patients", "MAX([age])"),
    ("Find the youngest patient.", "Patients", "MIN([age])"),
    ("Show total billing amount.", "Billing", "SUM("),
    ("Show average patient age.", "Patients", "AVG("),
    ("Show patients registered today.", "Patients", "GETDATE()"),
    ("Show active doctors.", "Doctors", "Doctors"),
    ("Show top 5 patients.", "Patients", "TOP 5"),
    ("Show top 10 doctors.", "Doctors", "TOP 10"),
    ("Sort patients by age.", "Patients", "ORDER BY"),
    ("Show completed appointments.", "Appointments", "status"),
    ("Show pending bills.", "Billing", "status"),
    ("Count total doctors.", "Doctors", "COUNT(*)"),
    ("Show patient phone numbers.", "Patients", "phone"),
    ("Show doctor specializations.", "Doctors", "specialization")
]


def test_20_distinct_questions_generate_different_sql():
    engine = FallbackEngine()
    generated_sqls = set()

    for q, expected_table, expected_keyword in QUESTIONS_AND_EXPECTATIONS:
        res = engine.nl_to_sql(q, TEST_HOSPITAL_SCHEMA, db_type='mssql')
        sql = res.get('sql', '')
        
        assert sql != "", f"Failed to generate SQL for query: {q}"
        assert expected_table.lower() in [t.lower() for t in res.get('tables_used', [])], f"Expected table {expected_table} in query: {q}"
        assert expected_keyword.lower() in sql.lower(), f"Expected keyword '{expected_keyword}' in generated SQL: {sql} for prompt: {q}"
        
        generated_sqls.add(sql)

    # Verify that different questions produced distinct SQL queries
    assert len(generated_sqls) >= 15, f"Expected at least 15 unique SQL queries out of 20, got {len(generated_sqls)}"


def test_read_only_query_security_checker():
    from services.sqlserver_service import SqlServerService
    
    # Destructive queries should be blocked
    success1, _, _, err1 = SqlServerService.execute_read_only_query("HospitalManagement", "DROP TABLE Patients")
    assert not success1
    assert "blocked" in err1.lower()

    success2, _, _, err2 = SqlServerService.execute_read_only_query("HospitalManagement", "DELETE FROM Patients WHERE age > 50")
    assert not success2
    assert "blocked" in err2.lower()

    success3, _, _, err3 = SqlServerService.execute_read_only_query("HospitalManagement", "ALTER TABLE Patients DROP COLUMN age")
    assert not success3
    assert "blocked" in err3.lower()


def test_nl_to_sql_endpoint_always_returns_json():
    from app import app
    with app.test_client() as client:
        # Invalid schema_id string
        res1 = client.post('/api/nl-to-sql', json={'query': 'Show all patients', 'schema_id': 'invalid_id_string'})
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert 'sql' in data1 or 'error' in data1

        # Non-existent DB name
        res2 = client.post('/api/nl-to-sql', json={'query': 'Show all patients', 'db_name': 'NonExistentDB12345'})
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert 'sql' in data2 or 'error' in data2

        # Empty query
        res3 = client.post('/api/nl-to-sql', json={'query': ''})
        assert res3.status_code == 400
        assert 'error' in res3.get_json()


def test_custom_requirements_and_general_sql_doubts():
    engine = FallbackEngine()

    # 1. Custom user requirement without schema
    res1 = engine.nl_to_sql("Find top 10 employees by salary", "", db_type='mssql')
    assert "Employees" in res1['tables_used'] or "employees" in res1['sql'].lower()
    assert "salary" in res1['sql'].lower()

    # 2. General SQL doubt query
    res2 = engine.nl_to_sql("What is an index in SQL?", "", db_type='mssql')
    assert "index" in res2['explanation'].lower()
    assert "CREATE" in res2['sql'] or "INDEX" in res2['sql']


