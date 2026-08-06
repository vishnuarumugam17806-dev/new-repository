"""
SMART DB — API and Integration Tests
Tests Flask routing, auth endpoints and session validation.
"""
from models import User

def test_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"SMART" in response.data


def test_auth_routes_load(client):
    login_resp = client.get("/login")
    assert login_resp.status_code == 200
    assert b"Sign In" in login_resp.data

    register_resp = client.get("/register")
    assert register_resp.status_code == 200
    assert b"Create Account" in register_resp.data


def test_user_registration_flow(client, db):
    # Register a new user
    resp = client.post("/register", data={
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword123"
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    
    # Verify user exists in database
    user = User.query.filter_by(username="testuser").first()
    assert user is not None
    assert user.email == "test@example.com"
    
    # Try logging in
    login_resp = client.post("/login", data={
        "username": "testuser",
        "password": "securepassword123"
    }, follow_redirects=True)
    
    assert login_resp.status_code == 200
    assert b"testuser" in login_resp.data


def test_nl_to_sql_api(client):
    response = client.post("/api/nl-to-sql", json={
        "query": "Show all active users registered this month",
        "db_type": "sqlite"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert "sql" in data
    assert "explanation" in data
    assert "users" in data["tables_used"]
