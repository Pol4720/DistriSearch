from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from models import SearchQuery, SearchResult, FileType
from services import index_service, node_service
from auth import get_current_active_user
from models import User
from database_sql import get_db, log_activity
from sqlalchemy.orm import Session
import database as database_viejo

router = APIRouter(
    prefix="/search",
    tags=["search"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=SearchResult)
async def search_files(
    q: str = Query(..., description="Texto a buscar"),
    file_type: Optional[FileType] = Query(None, description="Tipo de archivo"),
    max_results: int = Query(50, description="Número máximo de resultados"),
    include_score: bool = Query(False, description="Si es true, incluye el score por resultado"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Busca archivos en el sistema distribuido
    """
    # Log activity
    log_activity(db, current_user.id, "search", f"Query: {q}, Type: {file_type}, Max: {max_results}")

    if include_score:
        # Devolver JSON crudo con 'score' por entrada; evitamos response_model para no filtrar el campo.
        file_type_str = file_type.value if file_type else None
        rows = database_viejo.search_files(query=q, file_type=file_type_str, limit=max_results)
        node_ids = {r["node_id"] for r in rows}
        nodes = []
        for nid in node_ids:
            nd = database_viejo.get_node(nid)
            if nd:
                nodes.append(nd)
        # Normalizar score a float
        files = []
        for r in rows:
            d = dict(r)
            if "score" in d and d["score"] is not None:
                try:
                    d["score"] = float(d["score"])  # bm25: menor es mejor
                except Exception:
                    pass
            files.append(d)
        return JSONResponse(content={
            "files": files,
            "total_count": len(files),
            "nodes_available": nodes,
        })
    else:
        query = SearchQuery(
            query=q,
            file_type=file_type,
            max_results=max_results
        )
        return index_service.search_files(query)

@router.get("/stats")
async def search_stats():
    """
    Retorna estadísticas del índice de búsqueda
    """
    return index_service.get_index_stats()

@router.get("/nodes")
async def get_nodes():
    """
    Retorna la lista de todos los nodos registrados
    """
    return node_service.get_all_nodes()