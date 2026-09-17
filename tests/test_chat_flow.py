"""
SMART DB — Database Creation Chat Flow Tests
Tests multi-database session state machine step-by-step.
"""
from unittest.mock import patch
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret_key'
    with app.test_client() as client:
        with app.app_context():
            yield client


def test_chat_flow_initial_state(client):
    res = client.get('/api/db-create-chat/state')
    assert res.status_code == 200
    data = res.get_json()
    assert 'state' in data
    assert data['state']['step'] == 'select_spec'


def test_chat_flow_select_spec(client):
    client.post('/api/db-create-chat/state', json={})
    res = client.post('/api/db-create-chat/message', json={
        'action': 'select_spec',
        'db_type': 'sqlserver'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['step'] == 'ask_dbname'
    assert data['database_type'] == 'sqlserver'


def test_chat_flow_dbname_and_action(client):
    client.post('/api/db-create-chat/state', json={})
    client.post('/api/db-create-chat/message', json={'action': 'select_spec', 'db_type': 'sqlserver'})

    # DB Name input
    res_db = client.post('/api/db-create-chat/message', json={'message': 'TestMultiTableDB'})
    assert res_db.get_json()['step'] == 'choose_creation_mode'

    # Mode Selection (Create New Scratch Mode)
    res_act = client.post('/api/db-create-chat/message', json={'action': 'create_scratch_mode'})
    assert res_act.get_json()['step'] == 'ask_table_name'


def test_chat_flow_table_creation(client):
    client.post('/api/db-create-chat/state', json={})
    client.post('/api/db-create-chat/message', json={'action': 'select_spec', 'db_type': 'sqlserver'})
    client.post('/api/db-create-chat/message', json={'message': 'TestMultiTableDB'})
    client.post('/api/db-create-chat/message', json={'action': 'create_scratch_mode'})
    
    # Table 1: Patients
    res1 = client.post('/api/db-create-chat/message', json={'message': 'Patients'})
    assert res1.get_json()['step'] == 'ask_add_another_table'
    
    # Stop adding tables -> NO
    res2 = client.post('/api/db-create-chat/message', json={'message': 'no_continue', 'action': 'no_continue'})
    data2 = res2.get_json()
    assert data2['step'] == 'ask_table_structure'
    assert 'Patients' in data2['current_table']

    # Table structure & complete
    res3 = client.post('/api/db-create-chat/message', json={
        'message': "patient_id INT PRIMARY KEY, patient_name VARCHAR(100), age INT"
    })
    data3 = res3.get_json()
    assert data3['step'] == 'finished'
