import pytest
from fastapi.testclient import TestClient
from main import app
from user_database import init_user_db
import os
import tempfile

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    # Usar una base de datos temporal para tests
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        test_db_path = f.name

    # Configurar la base de datos de prueba
    os.environ["USER_DATABASE_PATH"] = test_db_path
    os.environ["SECRET_KEY"] = "test-secret-key"

    # Reinicializar módulos para usar la nueva DB
    import user_database
    import importlib
    importlib.reload(user_database)

    # Inicializar la base de datos
    user_database.init_user_db()

    yield

    # Limpiar
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)

def test_register_user():
    """Test user registration."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123"
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_register_duplicate_username():
    """Test registering with duplicate username."""
    user_data = {
        "username": "testuser",
        "email": "different@example.com",
        "password": "testpass123"
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]

def test_register_duplicate_email():
    """Test registering with duplicate email."""
    user_data = {
        "username": "differentuser",
        "email": "test@example.com",
        "password": "testpass123"
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]

def test_login_success():
    """Test successful login."""
    login_data = {
        "username": "testuser",
        "password": "testpass123"
    }
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Guardar token para otros tests
    global test_token
    test_token = data["access_token"]

def test_login_wrong_password():
    """Test login with wrong password."""
    login_data = {
        "username": "testuser",
        "password": "wrongpass"
    }
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401

def test_login_nonexistent_user():
    """Test login with nonexistent user."""
    login_data = {
        "username": "nonexistent",
        "password": "testpass123"
    }
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401

def test_get_current_user():
    """Test getting current user info."""
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"

def test_get_current_user_no_token():
    """Test getting current user without token."""
    response = client.get("/auth/me")
    assert response.status_code == 401

def test_get_current_user_invalid_token():
    """Test getting current user with invalid token."""
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 401