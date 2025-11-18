import sqlite3
from contextlib import contextmanager
import os
from typing import Dict, List, Optional
from datetime import datetime

# Base de datos separada para usuarios y tareas
USER_DATABASE_PATH = os.getenv("USER_DATABASE_PATH", "users.db")

# Asegurar que la carpeta exista
_db_dir = os.path.dirname(USER_DATABASE_PATH)
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)

@contextmanager
def get_user_connection():
    """Context manager para conexiones a la base de datos de usuarios."""
    conn = sqlite3.connect(USER_DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_user_db():
    """Inicializa la base de datos de usuarios si no existe."""
    with get_user_connection() as conn:
        cursor = conn.cursor()

        # Tabla de usuarios
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        # Tabla de tareas
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        conn.commit()

# Funciones para usuarios
def create_user(username: str, email: str, hashed_password: str) -> int:
    """Crea un nuevo usuario y retorna el ID."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            (username, email, hashed_password)
        )
        conn.commit()
        return cursor.lastrowid

def get_user_by_username(username: str) -> Optional[Dict]:
    """Obtiene un usuario por nombre de usuario."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_email(email: str) -> Optional[Dict]:
    """Obtiene un usuario por email."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Obtiene un usuario por ID."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# Funciones para tareas
def create_task(user_id: int, title: str, description: str = None) -> int:
    """Crea una nueva tarea y retorna el ID."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (user_id, title, description) VALUES (?, ?, ?)",
            (user_id, title, description)
        )
        conn.commit()
        return cursor.lastrowid

def get_tasks_by_user(user_id: int) -> List[Dict]:
    """Obtiene todas las tareas de un usuario."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def update_task_status(task_id: int, status: str):
    """Actualiza el estado de una tarea."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id)
        )
        conn.commit()

def delete_task(task_id: int):
    """Elimina una tarea."""
    with get_user_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()