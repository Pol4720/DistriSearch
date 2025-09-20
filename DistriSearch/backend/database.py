import sqlite3
from contextlib import contextmanager
import os
from typing import Dict, List, Optional
from models import FileMeta, NodeInfo

# Por simplicidad inicial, usamos SQLite
# En la segunda fase migraremos a Elasticsearch
DATABASE_PATH = "distrisearch.db"

def init_db():
    """Inicializa la base de datos si no existe."""
    if not os.path.exists(DATABASE_PATH):
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla para almacenar metadatos de archivos
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                type TEXT NOT NULL,
                node_id TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES nodes(node_id)
            )
            ''')
            
            # Tabla para almacenar información de nodos
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                port INTEGER NOT NULL,
                status TEXT NOT NULL,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                shared_files_count INTEGER DEFAULT 0
            )
            ''')
            
            # Índice para búsquedas rápidas por nombre de archivo
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)')
            
            conn.commit()

@contextmanager
def get_connection():
    """Contexto para obtener una conexión a la base de datos."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Funciones para la gestión de archivos
def register_file(file_meta: FileMeta):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO files 
        (file_id, name, path, size, mime_type, type, node_id, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_meta.file_id, 
            file_meta.name, 
            file_meta.path, 
            file_meta.size, 
            file_meta.mime_type, 
            file_meta.type, 
            file_meta.node_id, 
            file_meta.last_updated
        ))
        conn.commit()

def search_files(query: str, file_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        sql = "SELECT * FROM files WHERE name LIKE ?"
        params = [f"%{query}%"]
        
        if file_type:
            sql += " AND type = ?"
            params.append(file_type)
        
        sql += " LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

# Funciones para la gestión de nodos
def register_node(node: NodeInfo):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO nodes 
        (node_id, name, ip_address, port, status, last_seen, shared_files_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            node.node_id,
            node.name,
            node.ip_address,
            node.port,
            node.status,
            node.last_seen,
            node.shared_files_count
        ))
        conn.commit()

def get_node(node_id: str) -> Optional[Dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_nodes() -> List[Dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nodes")
        return [dict(row) for row in cursor.fetchall()]

def update_node_status(node_id: str, status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE nodes SET status = ?, last_seen = CURRENT_TIMESTAMP
        WHERE node_id = ?
        ''', (status, node_id))
        conn.commit()

# Inicializar la base de datos al importar este módulo
init_db()
