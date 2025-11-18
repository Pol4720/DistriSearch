import pytest
from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

# Token will be set by auth tests
test_token = None

@pytest.fixture(scope="module", autouse=True)
def get_token():
    """Get authentication token from auth tests."""
    # This assumes test_auth.py runs first and sets test_token
    # In a real scenario, you'd want to register and login here
    global test_token
    if test_token is None:
        # Usar la misma DB que los tests de auth
        import os
        import tempfile
        import user_database
        import importlib

        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            test_db_path = f.name

        os.environ["USER_DATABASE_PATH"] = test_db_path
        os.environ["SECRET_KEY"] = "test-secret-key"

        importlib.reload(user_database)
        user_database.init_user_db()

        # Register and login
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)

        user_data = {
            "username": "taskuser",
            "email": "task@example.com",
            "password": "taskpass123"
        }
        client.post("/auth/register", json=user_data)

        login_data = {
            "username": "taskuser",
            "password": "taskpass123"
        }
        response = client.post("/auth/login", data=login_data)
        test_token = response.json()["access_token"]

        # Cleanup will be handled by auth test fixture

def get_auth_headers():
    """Get authorization headers."""
    return {"Authorization": f"Bearer {test_token}"}

def test_create_task():
    """Test creating a new task."""
    task_data = {
        "title": "Test Task",
        "description": "This is a test task"
    }
    response = client.post("/tasks/", json=task_data, headers=get_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["description"] == "This is a test task"
    assert data["status"] == "pending"
    assert "id" in data

    # Guardar ID de tarea para otros tests
    global test_task_id
    test_task_id = data["id"]

def test_get_user_tasks():
    """Test getting user's tasks."""
    response = client.get("/tasks/", headers=get_auth_headers())
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) >= 1
    assert any(task["title"] == "Test Task" for task in tasks)

def test_update_task_status():
    """Test updating task status."""
    update_data = {"status": "completed"}
    response = client.put(f"/tasks/{test_task_id}", json=update_data, headers=get_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"

def test_update_nonexistent_task():
    """Test updating a nonexistent task."""
    update_data = {"status": "completed"}
    response = client.put("/tasks/99999", json=update_data, headers=get_auth_headers())
    assert response.status_code == 404

def test_delete_task():
    """Test deleting a task."""
    response = client.delete(f"/tasks/{test_task_id}", headers=get_auth_headers())
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted successfully"

def test_delete_nonexistent_task():
    """Test deleting a nonexistent task."""
    response = client.delete("/tasks/99999", headers=get_auth_headers())
    assert response.status_code == 404

def test_create_task_no_auth():
    """Test creating task without authentication."""
    task_data = {
        "title": "Unauthorized Task",
        "description": "Should fail"
    }
    response = client.post("/tasks/", json=task_data)
    assert response.status_code == 401

def test_get_tasks_no_auth():
    """Test getting tasks without authentication."""
    response = client.get("/tasks/")
    assert response.status_code == 401