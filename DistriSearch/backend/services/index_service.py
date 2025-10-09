from typing import List, Dict, Optional
from models import FileMeta, SearchQuery, SearchResult, NodeInfo
import database
from services import node_service

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
            # No devolvemos el contenido completo por seguridad/eficiencia.
            content=None
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
    Obtiene un archivo por su ID
    """
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE file_id = ?", (file_id,))
        file = cursor.fetchone()
        return dict(file) if file else None

def get_nodes_with_file(file_id: str) -> List[Dict]:
    """
    Obtiene todos los nodos que tienen un archivo específico
    """
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.* FROM nodes n
            JOIN files f ON n.node_id = f.node_id
            WHERE f.file_id = ?
        """, (file_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_index_stats() -> Dict:
    """
    Obtiene estadísticas del índice
    """
    with database.get_connection() as conn:
        cursor = conn.cursor()
        
        # Total de archivos
        cursor.execute("SELECT COUNT(*) as total FROM files")
        total_files = cursor.fetchone()["total"]
        
        # Total de nodos
        cursor.execute("SELECT COUNT(*) as total FROM nodes")
        total_nodes = cursor.fetchone()["total"]
        
        # Nodos activos
        cursor.execute("SELECT COUNT(*) as total FROM nodes WHERE status = 'online'")
        active_nodes = cursor.fetchone()["total"]
        
        # Archivos por tipo
        cursor.execute("""
            SELECT type, COUNT(*) as count 
            FROM files 
            GROUP BY type
        """)
        files_by_type = {row["type"]: row["count"] for row in cursor.fetchall()}
        
        # Tamaño total de archivos
        cursor.execute("SELECT SUM(size) as total_size FROM files")
        total_size = cursor.fetchone()["total_size"] or 0
        
        # Duplicados (archivos con mismo file_id en diferentes nodos)
        cursor.execute("""
            SELECT file_id, COUNT(*) as copies
            FROM files
            GROUP BY file_id
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        duplicates_count = len(duplicates)
        
        return {
            "total_files": total_files,
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "files_by_type": files_by_type,
            "total_size_bytes": total_size,
            "duplicates_count": duplicates_count
        }
