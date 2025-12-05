from typing import List, Dict, Optional
from models import FileMeta, SearchQuery, SearchResult, NodeInfo
import database
from services import node_service
from pymongo import MongoClient
import os

def register_files(files: List[FileMeta]) -> int:
    """
    Registra una lista de archivos en el índice
    """
    count = 0
    for file in files:
        database.register_file(file)
        count += 1
    
    # Actualizar contador de archivos compartidos del nodo
    if files:
        node_id = files[0].node_id
        node = database.get_node(node_id)
        if node:
            # Recalcular desde la tabla de files para consistencia
            total = database.get_node_file_count(node_id)
            database.update_node_shared_files_count(node_id, total)
    
    return count

def search_files(query: SearchQuery) -> SearchResult:
    """
    Busca archivos que coincidan con la consulta
    """
    # Buscar archivos en la base de datos
    file_type_str = query.file_type.value if query.file_type else None
    files_data = database.search_files(
        query=query.query, 
        file_type=file_type_str, 
        limit=query.max_results
    )
    
    # Convertir los resultados de la base de datos a modelos FileMeta
    files = []
    node_ids = set()
    for file_data in files_data:
        node_ids.add(file_data["node_id"])
        files.append(FileMeta(
            file_id=file_data["file_id"],
            name=file_data["name"],
            path=file_data["path"],
            size=file_data["size"],
            mime_type=file_data["mime_type"],
            type=file_data["type"],
            node_id=file_data["node_id"],
            last_updated=file_data["last_updated"],
            content=None,
            content_hash=file_data.get("content_hash") if isinstance(file_data, dict) else None
        ))
    
    # Obtener información de los nodos que tienen estos archivos
    nodes_available = []
    for node_id in node_ids:
        node_data = database.get_node(node_id)
        if node_data:
            nodes_available.append(NodeInfo(
                node_id=node_data["node_id"],
                name=node_data["name"],
                ip_address=node_data["ip_address"],
                port=node_data["port"],
                status=node_data["status"],
                last_seen=node_data["last_seen"],
                shared_files_count=node_data["shared_files_count"]
            ))
    
    return SearchResult(
        files=files,
        total_count=len(files),
        nodes_available=nodes_available
    )

def get_file_by_id(file_id: str) -> Optional[Dict]:
    """
    Obtiene un archivo por su ID usando MongoDB
    """
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    file_doc = db.files.find_one({"file_id": file_id})
    
    if file_doc:
        # Convertir ObjectId a string
        file_doc["_id"] = str(file_doc["_id"])
    
    return file_doc

def get_nodes_with_file(file_id: str) -> List[Dict]:
    """
    Obtiene todos los nodos que tienen un archivo específico
    """
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    # Buscar archivos con ese file_id
    files = list(db.files.find({"file_id": file_id}))
    
    # Obtener nodos únicos
    node_ids = list(set(f["node_id"] for f in files))
    
    # Buscar información de nodos
    nodes = []
    for node_id in node_ids:
        node = database.get_node(node_id)
        if node:
            nodes.append(node)
    
    return nodes

def get_index_stats() -> Dict:
    """
    ✅ CORREGIDO: Obtiene estadísticas usando MongoDB
    """
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    # Total de archivos
    total_files = db.files.count_documents({})
    
    # Total de nodos
    total_nodes = db.nodes.count_documents({})
    
    # Nodos activos
    active_nodes = db.nodes.count_documents({"status": "online"})
    
    # Archivos por tipo usando aggregation
    pipeline = [
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1}
        }}
    ]
    
    files_by_type_cursor = db.files.aggregate(pipeline)
    files_by_type = {doc["_id"]: doc["count"] for doc in files_by_type_cursor}
    
    # Tamaño total de archivos
    size_pipeline = [
        {"$group": {
            "_id": None,
            "total_size": {"$sum": "$size"}
        }}
    ]
    
    size_result = list(db.files.aggregate(size_pipeline))
    total_size = size_result[0]["total_size"] if size_result else 0
    
    # Duplicados (archivos con mismo file_id en diferentes nodos)
    duplicates_pipeline = [
        {"$group": {
            "_id": "$file_id",
            "count": {"$sum": 1}
        }},
        {"$match": {
            "count": {"$gt": 1}
        }},
        {"$count": "duplicates"}
    ]
    
    duplicates_result = list(db.files.aggregate(duplicates_pipeline))
    duplicates_count = duplicates_result[0]["duplicates"] if duplicates_result else 0
    
    return {
        "total_files": total_files,
        "total_nodes": total_nodes,
        "active_nodes": active_nodes,
        "files_by_type": files_by_type,
        "total_size_bytes": total_size,
        "duplicates_count": duplicates_count
    }
