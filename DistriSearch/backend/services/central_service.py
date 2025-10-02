"""Centralized mode service.

Allows scanning a single local folder (central repository) and indexing
its files under a synthetic node 'central'. This co-exists with the
distributed mode without changing existing endpoints. Frontend can call
`/central/scan` to (re)index the folder contents.
"""

from __future__ import annotations

import os
import logging
import hashlib
import mimetypes
from datetime import datetime
from typing import Dict, List, Optional

from models import FileMeta, NodeInfo, NodeStatus
import database
from services import index_service, node_service

CENTRAL_NODE_ID = "central"
logger = logging.getLogger("central_service")

def _ensure_central_node(name: str = "Repositorio Central", port: int = 8000):
    """Register the synthetic central node if not present."""
    existing = database.get_node(CENTRAL_NODE_ID)
    if existing:
        return existing
    node = NodeInfo(
        node_id=CENTRAL_NODE_ID,
        name=name,
        ip_address="localhost",  # Local access; downloads served by same backend later if needed
        port=port,
        status=NodeStatus.ONLINE,
        shared_files_count=0,
    )
    database.register_node(node)
    return database.get_node(CENTRAL_NODE_ID)

def _hash_file(path: str) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def _categorize(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith((
        "text/",
        "application/pdf",
        "application/msword",
        "application/vnd.ms-",
        "application/vnd.openxmlformats-",
    )):
        return "document"
    return "other"

def scan_folder(folder_path: str) -> List[Dict]:
    """Return metadata dicts for all files in folder (recursive)."""
    folder_path = os.path.abspath(folder_path)
    results: List[Dict] = []
    mimetypes.init()
    for root, _, files in os.walk(folder_path):
        for fname in files:
            full_path = os.path.join(root, fname)
            try:
                mime_type, _ = mimetypes.guess_type(full_path)
                if not mime_type:
                    mime_type = "application/octet-stream"
                rel_path = os.path.relpath(full_path, folder_path)
                results.append({
                    "file_id": _hash_file(full_path),
                    "name": fname,
                    "path": rel_path,
                    "size": os.path.getsize(full_path),
                    "mime_type": mime_type,
                    "type": _categorize(mime_type),
                    "last_updated": datetime.fromtimestamp(os.path.getmtime(full_path)),
                })
            except Exception as e:
                logger.warning(f"No se pudo procesar archivo '{full_path}': {e}")
                continue
    return results

def index_central_folder(folder_path: Optional[str] = None) -> Dict:
    """Scan and index the central folder.

    Args:
        folder_path: Optional explicit path; if None uses env CENTRAL_SHARED_FOLDER or './central_shared'

    Returns summary dict with counts.
    """
    folder = folder_path or os.getenv("CENTRAL_SHARED_FOLDER", "./central_shared")
    os.makedirs(folder, exist_ok=True)
    _ensure_central_node()

    files_meta = scan_folder(folder)
    # Convert and register
    count = 0
    for meta in files_meta:
        fm = FileMeta(
            file_id=meta["file_id"],
            name=meta["name"],
            path=meta["path"],
            size=meta["size"],
            mime_type=meta["mime_type"],
            type=meta["type"],
            node_id=CENTRAL_NODE_ID,
            last_updated=meta["last_updated"],
        )
        database.register_file(fm)
        count += 1

    # Update node shared_files_count
    node_data = database.get_node(CENTRAL_NODE_ID)
    if node_data:
        node_info = NodeInfo(
            node_id=node_data["node_id"],
            name=node_data["name"],
            ip_address=node_data["ip_address"],
            port=node_data["port"],
            status=NodeStatus.ONLINE,
            shared_files_count=count
        )
        database.register_node(node_info)

    logger.info(f"Indexación centralizada completada: {count} archivos en {folder}")
    return {
        "mode": "centralized",
        "indexed_files": count,
        "folder": os.path.abspath(folder),
    }

def get_mode() -> Dict:
    """Return current operating mode metadata.

    Currently always returns centralized available; distributed can still operate.
    In future could inspect config to disable.
    """
    # If there is only the central node registered, treat as centralized-only for UI convenience.
    nodes = database.get_all_nodes()
    node_ids = {n["node_id"] for n in nodes}
    centralized_active = CENTRAL_NODE_ID in node_ids
    return {
        "centralized": centralized_active,
        "distributed": len(node_ids - {CENTRAL_NODE_ID}) > 0,
        "central_node_id": CENTRAL_NODE_ID if centralized_active else None,
    }

def resolve_central_file_path(file_id: str, base_folder: Optional[str] = None) -> Optional[str]:
    """Given a file_id returns the absolute path if it belongs to central node.

    This queries DB for matching file row with node_id=central. Returns None if not found.
    """
    folder = base_folder or os.getenv("CENTRAL_SHARED_FOLDER", "./central_shared")
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT path FROM files WHERE file_id = ? AND node_id = ?",
            (file_id, CENTRAL_NODE_ID),
        )
        row = cursor.fetchone()
        if not row:
            return None
        abs_path = os.path.abspath(os.path.join(folder, row["path"]))
        if not os.path.isfile(abs_path):
            logger.warning(f"Archivo central no encontrado físicamente: {abs_path}")
            return None
        return abs_path
