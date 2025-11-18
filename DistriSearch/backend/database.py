# dataset.py
import os
from datetime import datetime
from typing import List, Optional, Dict

from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.errors import DuplicateKeyError
import gridfs

from models import FileMeta, NodeInfo

# Config via env
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "distrisearch")
USE_GRIDFS_THRESHOLD = int(os.getenv("GRIDFS_THRESHOLD_BYTES", "200000"))  # 200 KB

# Client / DB / GridFS singletons
_client = MongoClient(MONGO_URI)
_db = _client[MONGO_DBNAME]
_fs = gridfs.GridFS(_db)

def init_db():
    """Crea índices y colecciones necesarias (idempotente)."""
    # files: un documento por (file_id, node_id)
    _db.files.create_index([("file_id", ASCENDING), ("node_id", ASCENDING)], unique=True, name="u_file_node")
    _db.files.create_index([("node_id", ASCENDING), ("path", ASCENDING)], unique=True, name="u_node_path")
    _db.files.create_index([("name", ASCENDING)], name="idx_files_name")
    _db.files.create_index([("content_hash", ASCENDING)], name="idx_files_content_hash")

    # nodes: index por node_id
    _db.nodes.create_index([("node_id", ASCENDING)], unique=True, name="u_node_id")

    # node_mounts: único por node_id
    _db.node_mounts.create_index([("node_id", ASCENDING)], unique=True, name="u_node_mount")

    # file_contents: doc por file_id con texto indexado
    # name con mayor peso para simular boost del FTS en SQLite
    try:
        _db.file_contents.create_index([("name", TEXT), ("content", TEXT)],
                                       name="text_name_content",
                                       default_language="spanish",
                                       weights={"name": 10, "content": 1})
    except Exception:
        # si ya existe u otro problema, ignorarlo (idempotente)
        pass

# Inicializar índices al importar
init_db()

# --------------------- Helpers GridFS ---------------------
def _store_content_gridfs(file_id: str, content_bytes: bytes) -> str:
    """Guarda contenido en GridFS (filename=file_id) y devuelve gridfs id (str)."""
    # remover versiones previas con filename=file_id
    prev = _db.fs.files.find_one({"filename": file_id})
    if prev:
        _db.fs.files.delete_one({"_id": prev["_id"]})
        _db.fs.chunks.delete_many({"files_id": prev["_id"]})
    gfid = _fs.put(content_bytes, filename=file_id)
    return str(gfid)

def get_file_content_from_gridfs(file_id: str) -> Optional[bytes]:
    """Recuperar contenido completo desde GridFS por file_id (filename)."""
    meta = _db.fs.files.find_one({"filename": file_id})
    if not meta:
        return None
    return _fs.get(meta["_id"]).read()

# --------------------- API pública (mismas firmas que database.py) ---------------------
def register_file(file_meta: FileMeta):
    """
    Inserta/actualiza metadatos en la colección 'files' y sincroniza 'file_contents' y GridFS.
    Mantiene compatibilidad con el schema esperado por el resto del backend.
    """
    doc = {
        "file_id": file_meta.file_id,
        "name": file_meta.name,
        "path": file_meta.path,
        "size": int(file_meta.size),
        "mime_type": file_meta.mime_type,
        "type": file_meta.type.value if hasattr(file_meta.type, "value") else file_meta.type,
        "node_id": file_meta.node_id,
        "last_updated": getattr(file_meta, "last_updated", datetime.utcnow()),
        "content_hash": getattr(file_meta, "content_hash", None),
    }

    # Upsert en files
    _db.files.update_one(
        {"file_id": file_meta.file_id, "node_id": file_meta.node_id},
        {"$set": doc},
        upsert=True
    )

    # Indexar contenido (si se proporciona)
    content = getattr(file_meta, "content", None)
    if content:
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        if len(content_bytes) > USE_GRIDFS_THRESHOLD:
            gfid = _store_content_gridfs(file_meta.file_id, content_bytes)
            snippet = content_bytes[:200000].decode("utf-8", errors="ignore")
            _db.file_contents.update_one(
                {"file_id": file_meta.file_id},
                {"$set": {"file_id": file_meta.file_id, "name": file_meta.name, "content": snippet, "gridfs_id": gfid}},
                upsert=True
            )
        else:
            snippet = content_bytes.decode("utf-8", errors="ignore")
            _db.file_contents.update_one(
                {"file_id": file_meta.file_id},
                {"$set": {"file_id": file_meta.file_id, "name": file_meta.name, "content": snippet}},
                upsert=True
            )
    else:
        # asegurar al menos el documento en file_contents (con content vacío)
        _db.file_contents.update_one(
            {"file_id": file_meta.file_id},
            {"$setOnInsert": {"file_id": file_meta.file_id, "name": file_meta.name, "content": ""}},
            upsert=True
        )

def search_files(query: str, file_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """
    Búsqueda híbrida: primero intenta $text (ordenado por score) y si no hay resultados,
    hace fallback a búsqueda por regex en el nombre.
    Devuelve documentos equivalentes a las filas de la tabla 'files' (lista de dicts).
    """
    q = (query or "").strip()
    if not q:
        return []

    # intentar búsqueda textual
    text_filter = {"$text": {"$search": q}}
    if file_type:
        text_filter = {"$and": [text_filter, {"type": file_type}]}
    projection = {"score": {"$meta": "textScore"}, "file_id": 1}
    cursor = _db.file_contents.find(text_filter, projection).sort([("score", {"$meta": "textScore"})]).limit(limit)
    file_ids = [doc["file_id"] for doc in cursor]

    # fallback: si no hay resultados, busco por nombre (regex)
    if not file_ids:
        regex = {"name": {"$regex": q, "$options": "i"}}
        if file_type:
            # filtrar por tipo usando colección files
            matches = _db.files.find({"name": {"$regex": q, "$options": "i"}, "type": file_type}).limit(limit)
            return [doc for doc in matches]
        else:
            matches = _db.files.find(regex).limit(limit)
            return [doc for doc in matches]

    # Recuperar documentos completos de files por file_id (puede haber múltiples nodos por file_id)
    files_cursor = _db.files.find({"file_id": {"$in": file_ids}})
    files_by_id = {}
    for f in files_cursor:
        files_by_id.setdefault(f["file_id"], []).append(f)

    results = []
    for fid in file_ids:
        docs = files_by_id.get(fid, [])
        for d in docs:
            results.append(d)
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    return results

# --------------------- Nodos ---------------------
def register_node(node: NodeInfo):
    doc = {
        "node_id": node.node_id,
        "name": node.name,
        "ip_address": node.ip_address,
        "port": int(node.port),
        "status": node.status.value if hasattr(node.status, "value") else node.status,
        "last_seen": getattr(node, "last_seen", datetime.utcnow()),
        "shared_files_count": int(getattr(node, "shared_files_count", 0))
    }
    _db.nodes.update_one({"node_id": node.node_id}, {"$set": doc}, upsert=True)

def get_node(node_id: str) -> Optional[Dict]:
    return _db.nodes.find_one({"node_id": node_id})

def get_all_nodes() -> List[Dict]:
    return list(_db.nodes.find())

def update_node_status(node_id: str, status: str):
    _db.nodes.update_one({"node_id": node_id}, {"$set": {"status": status, "last_seen": datetime.utcnow()}})

def get_node_file_count(node_id: str) -> int:
    return _db.files.count_documents({"node_id": node_id})

def update_node_shared_files_count(node_id: str, count: int):
    _db.nodes.update_one({"node_id": node_id}, {"$set": {"shared_files_count": int(count)}})

# --------------------- Node mounts (simulación de carpetas locales) ---------------------
def set_node_mount(node_id: str, folder: str):
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    _db.node_mounts.update_one({"node_id": node_id}, {"$set": {"node_id": node_id, "folder": folder}}, upsert=True)

def get_node_mount(node_id: str) -> Optional[str]:
    doc = _db.node_mounts.find_one({"node_id": node_id})
    return doc["folder"] if doc else None

def delete_node_mount(node_id: str):
    _db.node_mounts.delete_one({"node_id": node_id})
