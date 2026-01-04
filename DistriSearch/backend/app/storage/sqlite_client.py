"""
SQLite Client for DistriSearch.

Provides async SQLite connectivity for storing:
- Users (replicated via Raft)
- Nodes (cluster membership)
- Partitions (VP-Tree assignments)
- User-Document Registry (for AP mode)

This replaces MongoDB for metadata, keeping MongoDB only for
document content on each slave node locally.
"""

import asyncio
import aiosqlite
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


# SQL Schema for all tables
SCHEMA_SQL = """
-- Users table (replicated via Raft to all nodes)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'user',
    permissions TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    email_verified INTEGER DEFAULT 0,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TEXT,
    last_login TEXT,
    last_password_change TEXT,
    refresh_token TEXT,
    password_reset_token TEXT,
    password_reset_expires TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Nodes table (cluster membership)
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT,
    address TEXT UNIQUE NOT NULL,
    port INTEGER DEFAULT 8000,
    role TEXT DEFAULT 'slave',
    status TEXT DEFAULT 'active',
    cpu_cores INTEGER,
    memory_mb INTEGER,
    disk_gb INTEGER,
    documents_count INTEGER DEFAULT 0,
    partition_ids TEXT DEFAULT '[]',
    load REAL DEFAULT 0.0,
    last_heartbeat TEXT,
    health_score REAL DEFAULT 1.0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Partitions table (VP-Tree assignments)
CREATE TABLE IF NOT EXISTS partitions (
    id TEXT PRIMARY KEY,
    name TEXT,
    primary_node_id TEXT,
    replica_node_ids TEXT DEFAULT '[]',
    document_ids TEXT DEFAULT '[]',
    documents_count INTEGER DEFAULT 0,
    centroid_vector TEXT,
    radius REAL DEFAULT 0.0,
    is_active INTEGER DEFAULT 1,
    is_rebalancing INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (primary_node_id) REFERENCES nodes(id)
);

-- User-Document Registry (maps users to their documents across nodes)
-- This enables AP: any node can answer "what documents does user X have?"
CREATE TABLE IF NOT EXISTS user_document_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    title TEXT,
    filename TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    vector_clock TEXT DEFAULT '{}',
    UNIQUE(user_id, document_id)
);

-- Search history (for analytics)
CREATE TABLE IF NOT EXISTS search_history (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    query_text TEXT NOT NULL,
    search_type TEXT DEFAULT 'HYBRID',
    results_count INTEGER DEFAULT 0,
    query_time_ms REAL DEFAULT 0.0,
    nodes_queried TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Metrics (with cleanup for old data)
CREATE TABLE IF NOT EXISTS metrics (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL,
    values_json TEXT DEFAULT '{}',
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Configuration (key-value pairs, replicated via Raft)
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Applied requests (for Raft command deduplication)
CREATE TABLE IF NOT EXISTS applied_requests (
    request_id TEXT PRIMARY KEY,
    result TEXT,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_nodes_address ON nodes(address);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
CREATE INDEX IF NOT EXISTS idx_nodes_role ON nodes(role);
CREATE INDEX IF NOT EXISTS idx_partitions_primary ON partitions(primary_node_id);
CREATE INDEX IF NOT EXISTS idx_partitions_active ON partitions(is_active);
CREATE INDEX IF NOT EXISTS idx_user_docs_user ON user_document_registry(user_id);
CREATE INDEX IF NOT EXISTS idx_user_docs_node ON user_document_registry(node_id);
CREATE INDEX IF NOT EXISTS idx_user_docs_deleted ON user_document_registry(is_deleted);
CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history(created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_node ON metrics(node_id);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_applied_requests_applied ON applied_requests(applied_at);
"""


class SQLiteClient:
    """
    Async SQLite client with connection pooling.
    
    Features:
    - Async operations via aiosqlite
    - Connection pooling for concurrency
    - Automatic schema creation
    - WAL mode for better concurrent access
    - Read replicas support (for slaves)
    """
    
    def __init__(
        self,
        db_path: str = "/app/data/distrisearch.db",
        pool_size: int = 5,
        read_only: bool = False,
    ):
        """
        Initialize SQLite client.
        
        Args:
            db_path: Path to SQLite database file
            pool_size: Number of connections in pool
            read_only: If True, only allow read operations (for slave replicas)
        """
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self.read_only = read_only
        
        self._pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._connected = False
        
        logger.info(f"SQLiteClient initialized: {db_path} (read_only={read_only})")
    
    async def connect(self) -> None:
        """Connect to SQLite and initialize schema."""
        if self._connected:
            return
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create initial connection for schema setup
            conn = await aiosqlite.connect(
                str(self.db_path),
                isolation_level=None,  # Autocommit for setup
            )
            
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=10000")
            await conn.execute("PRAGMA temp_store=MEMORY")
            
            # Create schema if not read-only
            if not self.read_only:
                await conn.executescript(SCHEMA_SQL)
                await conn.commit()
            
            await conn.close()
            
            # Initialize connection pool
            for _ in range(self.pool_size):
                conn = await self._create_connection()
                self._pool.append(conn)
            
            self._connected = True
            logger.info(f"SQLite connected: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection."""
        conn = await aiosqlite.connect(
            str(self.db_path),
            isolation_level=None,
        )
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        return conn
    
    async def disconnect(self) -> None:
        """Close all connections."""
        async with self._pool_lock:
            for conn in self._pool:
                await conn.close()
            self._pool.clear()
            self._connected = False
        logger.info("SQLite disconnected")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        conn = None
        async with self._pool_lock:
            if self._pool:
                conn = self._pool.pop()
        
        if conn is None:
            conn = await self._create_connection()
        
        try:
            yield conn
        finally:
            async with self._pool_lock:
                if len(self._pool) < self.pool_size:
                    self._pool.append(conn)
                else:
                    await conn.close()
    
    async def execute(
        self,
        sql: str,
        params: tuple = (),
    ) -> aiosqlite.Cursor:
        """Execute a SQL statement."""
        if self.read_only and not sql.strip().upper().startswith("SELECT"):
            raise RuntimeError("Database is read-only")
        
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor
    
    async def execute_many(
        self,
        sql: str,
        params_list: List[tuple],
    ) -> None:
        """Execute a SQL statement with multiple parameter sets."""
        if self.read_only:
            raise RuntimeError("Database is read-only")
        
        async with self.acquire() as conn:
            await conn.executemany(sql, params_list)
            await conn.commit()
    
    async def fetch_one(
        self,
        sql: str,
        params: tuple = (),
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row as dictionary."""
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, params)
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def fetch_all(
        self,
        sql: str,
        params: tuple = (),
    ) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def fetch_count(
        self,
        table: str,
        where: str = "",
        params: tuple = (),
    ) -> int:
        """Count rows in a table."""
        sql = f"SELECT COUNT(*) as count FROM {table}"
        if where:
            sql += f" WHERE {where}"
        
        result = await self.fetch_one(sql, params)
        return result["count"] if result else 0
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any],
    ) -> str:
        """Insert a row and return the ID."""
        if self.read_only:
            raise RuntimeError("Database is read-only")
        
        columns = list(data.keys())
        placeholders = ["?" for _ in columns]
        values = [self._serialize_value(v) for v in data.values()]
        
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, tuple(values))
            await conn.commit()
            return data.get("id", str(cursor.lastrowid))
    
    async def update(
        self,
        table: str,
        id: str,
        data: Dict[str, Any],
    ) -> bool:
        """Update a row by ID."""
        if self.read_only:
            raise RuntimeError("Database is read-only")
        
        data["updated_at"] = datetime.now().isoformat()
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = [self._serialize_value(v) for v in data.values()]
        values.append(id)
        
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"
        
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, tuple(values))
            await conn.commit()
            return cursor.rowcount > 0
    
    async def delete(
        self,
        table: str,
        id: str,
    ) -> bool:
        """Delete a row by ID."""
        if self.read_only:
            raise RuntimeError("Database is read-only")
        
        sql = f"DELETE FROM {table} WHERE id = ?"
        
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, (id,))
            await conn.commit()
            return cursor.rowcount > 0
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            result = await self.fetch_one("SELECT 1 as ok")
            return result is not None and result.get("ok") == 1
        except Exception:
            return False
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for SQLite storage."""
        if isinstance(value, (list, dict)):
            return json.dumps(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, bool):
            return 1 if value else 0
        return value
    
    @staticmethod
    def deserialize_json(value: Optional[str]) -> Any:
        """Deserialize a JSON string from SQLite."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


# Singleton instance management
_sqlite_client: Optional[SQLiteClient] = None


async def get_sqlite_client(
    db_path: str = "/app/data/distrisearch.db",
    read_only: bool = False,
) -> SQLiteClient:
    """Get or create the SQLite client singleton."""
    global _sqlite_client
    
    if _sqlite_client is None:
        _sqlite_client = SQLiteClient(db_path=db_path, read_only=read_only)
        await _sqlite_client.connect()
    
    return _sqlite_client


async def close_sqlite_client() -> None:
    """Close the SQLite client."""
    global _sqlite_client
    
    if _sqlite_client is not None:
        await _sqlite_client.disconnect()
        _sqlite_client = None
