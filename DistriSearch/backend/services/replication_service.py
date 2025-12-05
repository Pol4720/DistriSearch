"""Servicio de replicación para tolerancia a fallos."""

from __future__ import annotations
import logging
from typing import List, Dict
import database

logger = logging.getLogger("replication")

def find_offline_files(limit: int = 100) -> List[Dict]:
    """Devuelve archivos pertenecientes a nodos OFFLINE."""
    # Usar MongoDB en lugar de SQLite
    from pymongo import MongoClient
    import os
    
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    # Buscar nodos offline
    offline_nodes = db.nodes.find({"status": "offline"})
    offline_node_ids = [n["node_id"] for n in offline_nodes]
    
    # Buscar archivos de esos nodos
    files = list(db.files.find(
        {"node_id": {"$in": offline_node_ids}}
    ).limit(limit))
    
    return files

def get_online_nodes_with_file(file_id: str) -> List[Dict]:
    """Obtiene nodos online que tienen el archivo."""
    import os
    from pymongo import MongoClient
    
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    # Buscar todos los nodos que tienen el archivo
    files = list(db.files.find({"file_id": file_id}))
    node_ids = [f["node_id"] for f in files]
    
    # Filtrar solo los online
    online_nodes = list(db.nodes.find({
        "node_id": {"$in": node_ids},
        "status": "online"
    }))
    
    return online_nodes

def replicate_missing_files(batch: int = 25) -> Dict:
    """Replica archivos de nodos OFFLINE a otros nodos online."""
    offline_files = find_offline_files(limit=batch)
    if not offline_files:
        return {"checked": 0, "replicated": 0}

    replicated = 0
    for f in offline_files:
        fid = f["file_id"]
        candidates = get_online_nodes_with_file(fid)
        if not candidates:
            continue
        replicated += 1

    return {"checked": len(offline_files), "replicated": replicated}
