# dataset.py
import os
import gridfs
import hashlib
from datetime import datetime
from typing import List, Optional, Dict
from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.errors import DuplicateKeyError
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
    try:
        _db.file_contents.create_index([("name", TEXT), ("content", TEXT)],
                                       name="text_name_content",
                                       default_language="spanish",
                                       weights={"name": 10, "content": 1})
    except Exception:
        pass
    
    # **NUEVO: Índices para usuarios y actividades**
    _db.users.create_index([("username", ASCENDING)], unique=True, name="u_username")
    _db.users.create_index([("email", ASCENDING)], unique=True, name="u_email")
    _db.activities.create_index([("user_id", ASCENDING)], name="idx_activities_user")
    _db.activities.create_index([("timestamp", ASCENDING)], name="idx_activities_timestamp")

# Inicializar índices al importar
init_db()

# --------------------- Helpers GridFS ---------------------
def _store_content_gridfs(file_id: str, content_bytes: bytes) -> str:
    """Guarda contenido en GridFS (filename=file_id) y devuelve gridfs id (str)."""
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

# --------------------- API pública ---------------------
def register_file(file_meta: FileMeta):
    """Inserta/actualiza metadatos en la colección 'files'."""
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

    _db.files.update_one(
        {"file_id": file_meta.file_id, "node_id": file_meta.node_id},
        {"$set": doc},
        upsert=True
    )

    # Indexar contenido
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
        _db.file_contents.update_one(
            {"file_id": file_meta.file_id},
            {"$setOnInsert": {"file_id": file_meta.file_id, "name": file_meta.name, "content": ""}},
            upsert=True
        )

def search_files(query: str, file_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Búsqueda híbrida con MongoDB text search y fallback a regex."""
    q = (query or "").strip()
    if not q:
        return []

    # Búsqueda textual
    text_filter = {"$text": {"$search": q}}
    if file_type:
        text_filter = {"$and": [text_filter, {"type": file_type}]}
    projection = {"score": {"$meta": "textScore"}, "file_id": 1}
    cursor = _db.file_contents.find(text_filter, projection).sort([("score", {"$meta": "textScore"})]).limit(limit)
    file_ids = [doc["file_id"] for doc in cursor]

    # Fallback: regex
    if not file_ids:
        regex = {"name": {"$regex": q, "$options": "i"}}
        if file_type:
            matches = _db.files.find({"name": {"$regex": q, "$options": "i"}, "type": file_type}).limit(limit)
        else:
            matches = _db.files.find(regex).limit(limit)
        file_ids = [f["file_id"] for f in matches]

    # Recuperar documentos completos
    files_cursor = _db.files.find({"file_id": {"$in": file_ids}})
    files_by_id = {}
    for f in files_cursor:
        files_by_id.setdefault(f["file_id"], []).append(f)

    results = []
    for fid in file_ids:
        docs = files_by_id.get(fid, [])
        for d in docs:
            results.append({
                "file_id": d["file_id"],
                "name": d["name"],
                "path": d["path"],
                "size": d["size"],
                "mime_type": d["mime_type"],
                "type": d["type"],
                "node_id": d["node_id"],
                "last_updated": d["last_updated"],
                "content_hash": d.get("content_hash")
            })
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

# --------------------- Node mounts ---------------------
def set_node_mount(node_id: str, folder: str):
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    _db.node_mounts.update_one({"node_id": node_id}, {"$set": {"node_id": node_id, "folder": folder}}, upsert=True)

def get_node_mount(node_id: str) -> Optional[str]:
    doc = _db.node_mounts.find_one({"node_id": node_id})
    return doc["folder"] if doc else None

def delete_node_mount(node_id: str):
    _db.node_mounts.delete_one({"node_id": node_id})

# ==================== AUTENTICACIÓN (Migrado desde SQLite) ====================

def create_user(email: str, username: str, hashed_password: str) -> Dict:
    """Crea un nuevo usuario en MongoDB."""
    user_doc = {
        "email": email,
        "username": username,
        "hashed_password": hashed_password,
        "is_active": True,
        "is_superuser": False,
        "created_at": datetime.utcnow()
    }
    
    try:
        result = _db.users.insert_one(user_doc)
        user_doc["_id"] = str(result.inserted_id)
        return user_doc
    except DuplicateKeyError:
        raise ValueError("Usuario o email ya registrado")

def get_user_by_username(username: str) -> Optional[Dict]:
    """Obtiene un usuario por su username."""
    user = _db.users.find_one({"username": username})
    if user:
        user["_id"] = str(user["_id"])
    return user

def get_user_by_email(email: str) -> Optional[Dict]:
    """Obtiene un usuario por su email."""
    user = _db.users.find_one({"email": email})
    if user:
        user["_id"] = str(user["_id"])
    return user

def log_activity(user_id: str, action: str, details: str):
    """Registra actividad de usuario."""
    activity_doc = {
        "user_id": user_id,
        "action": action,
        "details": details,
        "timestamp": datetime.utcnow()
    }
    _db.activities.insert_one(activity_doc)

def get_user_activities(user_id: str, limit: int = 50) -> List[Dict]:
    """Obtiene actividades de un usuario."""
    activities = _db.activities.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    return list(activities)
