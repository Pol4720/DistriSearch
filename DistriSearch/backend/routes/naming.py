"""
Endpoints para sistema de nombrado jerárquico
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from services.naming.hierarchical_naming import get_namespace
from services.naming.ip_cache import get_ip_cache
from services.naming.multicast_discovery import get_multicast_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/naming",
    tags=["naming"],
    responses={404: {"description": "Not found"}},
)


class PathRegistration(BaseModel):
    path: str
    file_id: str
    metadata: dict


class AliasCreation(BaseModel):
    alias_path: str
    real_path: str


@router.post("/register_path")
async def register_hierarchical_path(registration: PathRegistration):
    """Registra archivo en namespace jerárquico"""
    namespace = get_namespace()
    
    success = namespace.register_path(
        registration.path,
        registration.file_id,
        registration.metadata
    )
    
    if success:
        return {"status": "success", "path": registration.path}
    else:
        raise HTTPException(status_code=500, detail="Error registrando path")


@router.get("/resolve")
async def resolve_path(path: str = Query(..., description="Path a resolver")):
    """Resuelve un path a información de archivo"""
    namespace = get_namespace()
    
    result = namespace.resolve(path)
    
    if result:
        return result
    else:
        raise HTTPException(status_code=404, detail=f"Path no encontrado: {path}")


@router.get("/list")
async def list_directory(path: str = Query("/", description="Directorio a listar")):
    """Lista contenidos de un directorio"""
    namespace = get_namespace()
    
    contents = namespace.list_directory(path)
    
    return {
        "path": path,
        "contents": contents,
        "count": len(contents)
    }


@router.post("/alias")
async def create_alias(alias: AliasCreation):
    """Crea un alias (symbolic link)"""
    namespace = get_namespace()
    
    success = namespace.create_alias(alias.alias_path, alias.real_path)
    
    if success:
        return {"status": "success", "alias": alias.alias_path, "target": alias.real_path}
    else:
        raise HTTPException(status_code=400, detail="Error creando alias")


@router.get("/search")
async def search_by_pattern(pattern: str = Query(..., description="Patrón de búsqueda (wildcards)")):
    """Busca archivos por patrón"""
    namespace = get_namespace()
    
    results = namespace.search_by_pattern(pattern)
    
    return {
        "pattern": pattern,
        "results": results,
        "count": len(results)
    }


@router.get("/tree")
async def get_tree_structure(
    path: str = Query("/", description="Raíz del árbol"),
    max_depth: int = Query(3, description="Profundidad máxima")
):
    """Obtiene estructura de árbol"""
    namespace = get_namespace()
    
    tree = namespace.get_tree_structure(path, max_depth)
    
    return tree


@router.delete("/path")
async def delete_path(
    path: str = Query(..., description="Path a eliminar"),
    recursive: bool = Query(False, description="Eliminar recursivamente")
):
    """Elimina un path"""
    namespace = get_namespace()
    
    success = namespace.delete_path(path, recursive)
    
    if success:
        return {"status": "success", "path": path}
    else:
        raise HTTPException(status_code=404, detail=f"Path no encontrado: {path}")


@router.get("/multicast/discovered")
async def get_discovered_nodes():
    """Obtiene nodos descubiertos vía multicast"""
    try:
        multicast = await get_multicast_service("", 0, "")  # Obtener instancia existente
        nodes = multicast.get_discovered_nodes()
        
        return {
            "discovered_nodes": list(nodes.values()),
            "count": len(nodes)
        }
    except:
        return {"discovered_nodes": [], "count": 0}


@router.get("/cache/stats")
async def get_cache_stats():
    """Obtiene estadísticas del IP cache"""
    cache = get_ip_cache()
    return cache.get_stats()


@router.post("/cache/clear")
async def clear_cache():
    """Limpia el IP cache"""
    cache = get_ip_cache()
    cache.clear()
    return {"status": "success", "message": "Cache limpiado"}