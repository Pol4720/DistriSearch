from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from models import SearchQuery, SearchResult, FileType
from services import index_service

router = APIRouter(
    prefix="/search",
    tags=["search"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=SearchResult)
async def search_files(
    q: str = Query(..., description="Texto a buscar"),
    file_type: Optional[FileType] = Query(None, description="Tipo de archivo"),
    max_results: int = Query(50, description="Número máximo de resultados")
):
    """
    Busca archivos en el sistema distribuido
    """
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
