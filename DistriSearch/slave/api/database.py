"""
DistriSearch Slave - Database Module
=====================================
Acceso a MongoDB para el nodo Slave.
Re-exporta desde backend/database.py para compatibilidad.
"""

# Importar todo desde el módulo backend existente para evitar duplicación
# En el futuro se puede migrar completamente aquí
import sys
import os

# Asegurar que backend esté en el path
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from backend.database import (
    # MongoDB connection
    _client,
    _db,
    _fs,
    MONGO_URI,
    MONGO_DBNAME,
    USE_GRIDFS_THRESHOLD,
    
    # Initialization
    init_db,
    
    # GridFS helpers
    get_file_content_from_gridfs,
    
    # File operations
    register_file,
    search_files,
    
    # Node operations
    register_node,
    get_node,
    get_all_nodes,
    update_node_status,
    get_node_file_count,
    update_node_shared_files_count,
    
    # Mount operations
    set_node_mount,
    get_node_mount,
    delete_node_mount,
    
    # User/Auth operations
    create_user,
    get_user_by_username,
    get_user_by_email,
    log_activity,
    get_user_activities,
)

__all__ = [
    # Connection
    "_client",
    "_db", 
    "_fs",
    "MONGO_URI",
    "MONGO_DBNAME",
    "USE_GRIDFS_THRESHOLD",
    
    # Init
    "init_db",
    
    # GridFS
    "get_file_content_from_gridfs",
    
    # Files
    "register_file",
    "search_files",
    
    # Nodes
    "register_node",
    "get_node",
    "get_all_nodes",
    "update_node_status",
    "get_node_file_count",
    "update_node_shared_files_count",
    
    # Mounts
    "set_node_mount",
    "get_node_mount",
    "delete_node_mount",
    
    # Auth
    "create_user",
    "get_user_by_username",
    "get_user_by_email",
    "log_activity",
    "get_user_activities",
]
