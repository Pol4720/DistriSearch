import sqlite3
from contextlib import contextmanager
import os
from typing import Dict, List, Optional
from models import FileMeta, NodeInfo

# Por simplicidad inicial, usamos SQLite
# En la segunda fase migraremos a Elasticsearch
# Permitimos configurar la ruta vía variable de entorno para persistencia en contenedor
DATABASE_PATH = os.getenv("DATABASE_PATH", "distrisearch.db")

# Asegurar que la carpeta de la base de datos exista (si incluye directorio)
_db_dir = os.path.dirname(DATABASE_PATH)
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)

def init_db():
    """Inicializa la base de datos si no existe."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Migración: si la tabla 'files' existe con PK en file_id únicamente, migrar a (file_id,node_id) y añadir content_hash
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(files)")
                info = cursor.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
                cols = [r[1] for r in info]
                pk_cols = [r[1] for r in info if r[5] != 0]
                needs_migration = (('content_hash' not in cols) or (pk_cols == ['file_id']))
                if needs_migration:
                    cursor.execute('ALTER TABLE files RENAME TO files_old')
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS files (
                        file_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        mime_type TEXT NOT NULL,
                        type TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        content_hash TEXT,
                        PRIMARY KEY (file_id, node_id),
                        FOREIGN KEY (node_id) REFERENCES nodes(node_id)
                    )
                    ''')
                    cursor.execute('''
                        INSERT OR IGNORE INTO files (file_id, name, path, size, mime_type, type, node_id, last_updated)
                        SELECT file_id, name, path, size, mime_type, type, node_id, last_updated FROM files_old
                    ''')
                    cursor.execute('DROP TABLE files_old')
        except Exception:
            # Si hay algún problema, continuamos con creación idempotente más abajo
            pass

        # Tabla principal de archivos
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT NOT NULL,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            size INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            type TEXT NOT NULL,
            node_id TEXT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_hash TEXT,
            PRIMARY KEY (file_id, node_id),
            FOREIGN KEY (node_id) REFERENCES nodes(node_id)
        )
        ''')

        # Asegurar índices/constraints útiles en esquemas actualizados
        # Unicidad por nodo+path (un mismo archivo físico por ruta en un nodo)
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_files_node_path ON files(node_id, path)')

        # Tabla de nodos
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

        # Índices útiles
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_files_node_path ON files(node_id, path)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_content_hash ON files(content_hash)')

        # Tabla virtual FTS5 para contenido textual y nombre (para boosting básico)
        # Usamos content="" para modo external content table; manualmente mantenemos sincronización.
        cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS file_contents USING fts5(
            file_id UNINDEXED,
            name,
            content,
            tokenize = 'porter'
        )
        ''')

        # Tabla para nodos locales simulados (mapeo node_id -> carpeta base)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_mounts (
            node_id TEXT PRIMARY KEY,
            folder TEXT NOT NULL,
            FOREIGN KEY (node_id) REFERENCES nodes(node_id)
        )
        ''')

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
        INSERT INTO files 
        (file_id, name, path, size, mime_type, type, node_id, last_updated, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(file_id, node_id) DO UPDATE SET
            name=excluded.name,
            path=excluded.path,
            size=excluded.size,
            mime_type=excluded.mime_type,
            type=excluded.type,
            last_updated=excluded.last_updated,
            content_hash=COALESCE(excluded.content_hash, files.content_hash)
        ''', (
            file_meta.file_id, 
            file_meta.name, 
            file_meta.path, 
            file_meta.size, 
            file_meta.mime_type, 
            file_meta.type, 
            file_meta.node_id, 
            file_meta.last_updated,
            getattr(file_meta, 'content_hash', None)
        ))

        # Indexar contenido si viene incluido
        if getattr(file_meta, 'content', None):
            # Eliminar entrada previa
            cursor.execute('DELETE FROM file_contents WHERE file_id = ?', (file_meta.file_id,))
            cursor.execute('INSERT INTO file_contents (file_id, name, content) VALUES (?, ?, ?)', (
                file_meta.file_id,
                file_meta.name,
                file_meta.content[:200000]  # límite de seguridad ~200KB
            ))
        else:
            # Asegurar al menos indexación por nombre (si no hay contenido aún)
            existing = cursor.execute('SELECT 1 FROM file_contents WHERE file_id = ?', (file_meta.file_id,)).fetchone()
            if not existing:
                cursor.execute('INSERT INTO file_contents (file_id, name, content) VALUES (?, ?, ?)', (
                    file_meta.file_id,
                    file_meta.name,
                    ''
                ))
        conn.commit()

def search_files(query: str, file_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Búsqueda híbrida: combina coincidencia en nombre y contenido.

    Estrategia simple: usamos FTS5 sobre (name, content). Recuperamos file_ids
    ordenados por rank y luego traemos filas de la tabla principal.
    Si query está vacío devolvemos nada.
    """
    if not query.strip():
        return []
    with get_connection() as conn:
        cursor = conn.cursor()

        # Normalizar tokens para FTS (eliminando caracteres peligrosos). Prefijos para coincidencias parciales simples.
        raw_tokens = [t for t in query.strip().split() if t]
        # Si el usuario escribe una frase larga, no añadimos comodines para evitar explosión de resultados.
        processed_tokens: List[str] = []
        for tok in raw_tokens[:10]:  # limitar a 10 términos
            safe = ''.join(ch for ch in tok if ch.isalnum())
            if not safe:
                continue
            processed_tokens.append(safe)
        # Unir tokens con espacio (equivale a AND implícito en FTS5)
        fts_query = ' '.join(processed_tokens) if processed_tokens else query.strip()

        # Usar nombre de la tabla FTS directamente para evitar problemas con algunos builds de SQLite al usar alias.
        fts_where = "file_contents MATCH ?"
        fts_param = fts_query

        # bm25: la tabla tiene 3 columnas (file_id UNINDEXED, name, content). Proveemos 3 pesos.
        # Peso 0 para file_id (no indexado), mayor peso a coincidencias en nombre.
        sql = f"""
        SELECT f.*, bm25(file_contents, 0.0, 1.0, 0.5) AS score
        FROM file_contents
        JOIN files f ON f.file_id = file_contents.file_id
        WHERE {fts_where}
        { 'AND f.type = ?' if file_type else '' }
        ORDER BY score ASC
        LIMIT ?
        """
        params: List = [fts_param]
        if file_type:
            params.append(file_type)
        params.append(limit)
        try:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            # Fallback a LIKE simple si hay error con FTS (por ejemplo sintaxis inválida)
            # Nota: este fallback solo busca en el nombre, no en el contenido.
            like_sql = "SELECT * FROM files WHERE name LIKE ?"
            params = [f"%{query}%"]
            if file_type:
                like_sql += " AND type = ?"
                params.append(file_type)
            like_sql += " LIMIT ?"
            params.append(limit)
            cursor.execute(like_sql, params)
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

def get_node_file_count(node_id: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM files WHERE node_id = ?', (node_id,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

def update_node_shared_files_count(node_id: str, count: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE nodes SET shared_files_count = ? WHERE node_id = ?', (count, node_id))
        conn.commit()

# ---- Node mounts (local-simulated nodes) ----
def set_node_mount(node_id: str, folder: str):
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO node_mounts (node_id, folder) VALUES (?, ?)', (node_id, folder))
        conn.commit()

def get_node_mount(node_id: str) -> Optional[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT folder FROM node_mounts WHERE node_id = ?', (node_id,))
        row = cur.fetchone()
        return row[0] if row else None

def delete_node_mount(node_id: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM node_mounts WHERE node_id = ?', (node_id,))
        conn.commit()

# Inicializar la base de datos al importar este módulo
init_db()
