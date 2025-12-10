"""
Search API Router
Search endpoints for distributed document search in DistriSearch
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional
from datetime import datetime
import logging
import uuid
import time

from .schemas import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SearchType,
    SearchHistoryItem,
    SearchHistoryResponse,
    ErrorResponse
)
from .dependencies import (
    get_document_repository,
    get_search_engine,
    get_cluster_manager,
    get_search_history_repository,
    rate_limit_search
)
from ..storage.mongodb import DocumentRepository, SearchHistoryRepository
from ..core.search import SearchEngine
from ..distributed.coordination import ClusterManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "/",
    response_model=SearchResponse,
    summary="Search documents",
    dependencies=[Depends(rate_limit_search)],
    responses={
        200: {"description": "Search results"},
        400: {"model": ErrorResponse, "description": "Invalid search request"},
        408: {"model": ErrorResponse, "description": "Search timeout"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def search_documents(
    request: SearchRequest,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    history_repo: SearchHistoryRepository = Depends(get_search_history_repository)
):
    """
    Search for documents across the distributed cluster.
    
    The search uses a hybrid approach combining:
    - **Keyword search**: TF-IDF based term matching
    - **Semantic search**: MinHash for near-duplicate detection, LDA for topic similarity
    - **Hybrid search** (default): Combines both approaches with weighted scoring
    
    The search is distributed across all nodes in the cluster using the VP-Tree
    to identify relevant partitions, minimizing search latency.
    """
    query_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Vectorize the query
        query_vectors = await search_engine.vectorize_query(request.query)
        
        # Determine which partitions/nodes to search based on VP-Tree
        target_partitions = await cluster_manager.get_partitions_for_query(
            query_vectors,
            top_k=request.top_k
        )
        
        # Execute distributed search
        search_results = await search_engine.distributed_search(
            query=request.query,
            query_vectors=query_vectors,
            search_type=request.search_type.value,
            top_k=request.top_k,
            filters=request.filters,
            target_partitions=target_partitions,
            timeout_ms=request.timeout_ms,
            cluster_manager=cluster_manager
        )
        
        search_time_ms = (time.time() - start_time) * 1000
        
        # Format results
        results = []
        for result in search_results.get("results", []):
            # Generate content preview with highlighted matches
            content_preview = _generate_preview(
                result.get("content", ""),
                request.query,
                max_length=300
            )
            
            result_item = SearchResultItem(
                document_id=result["document_id"],
                title=result.get("title", "Untitled"),
                content_preview=content_preview,
                score=result.get("score", 0.0),
                node_id=result.get("node_id", ""),
                metadata=result.get("metadata", {}),
                matched_terms=result.get("matched_terms", [])
            )
            
            if request.include_vectors and result.get("vectors"):
                from .schemas import DocumentVectors
                result_item.vectors = DocumentVectors(**result["vectors"])
            
            results.append(result_item)
        
        # Save to search history
        await history_repo.create({
            "_id": query_id,
            "query": request.query,
            "search_type": request.search_type.value,
            "results_count": len(results),
            "total_results": search_results.get("total", len(results)),
            "search_time_ms": search_time_ms,
            "searched_nodes": search_results.get("searched_nodes", 0),
            "filters": request.filters,
            "timestamp": datetime.utcnow()
        })
        
        logger.info(
            f"Search completed: query='{request.query[:50]}...', "
            f"results={len(results)}, time={search_time_ms:.2f}ms"
        )
        
        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            results=results,
            total_results=search_results.get("total", len(results)),
            searched_nodes=search_results.get("searched_nodes", 0),
            search_time_ms=search_time_ms,
            query_id=query_id
        )
        
    except TimeoutError:
        logger.warning(f"Search timeout: query='{request.query[:50]}...'")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Search operation timed out"
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get(
    "/quick",
    response_model=SearchResponse,
    summary="Quick search (GET)",
    dependencies=[Depends(rate_limit_search)],
    responses={
        200: {"description": "Search results"},
        400: {"model": ErrorResponse, "description": "Invalid query"}
    }
)
async def quick_search(
    q: str = Query(..., min_length=1, max_length=1000, description="Search query"),
    type: SearchType = Query(default=SearchType.HYBRID, description="Search type"),
    limit: int = Query(default=10, ge=1, le=100, description="Max results"),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    history_repo: SearchHistoryRepository = Depends(get_search_history_repository)
):
    """
    Quick search endpoint using GET parameters.
    Simplified version of the main search endpoint.
    """
    request = SearchRequest(
        query=q,
        search_type=type,
        top_k=limit,
        include_vectors=False
    )
    
    return await search_documents(
        request=request,
        doc_repo=doc_repo,
        search_engine=search_engine,
        cluster_manager=cluster_manager,
        history_repo=history_repo
    )


@router.get(
    "/suggest",
    response_model=List[str],
    summary="Get search suggestions",
    responses={
        200: {"description": "List of suggestions"}
    }
)
async def get_suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="Partial query"),
    limit: int = Query(default=5, ge=1, le=20, description="Max suggestions"),
    history_repo: SearchHistoryRepository = Depends(get_search_history_repository)
):
    """
    Get search suggestions based on query history and document titles.
    """
    try:
        # Get suggestions from search history
        suggestions = await history_repo.get_suggestions(
            prefix=q,
            limit=limit
        )
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return []


@router.get(
    "/similar/{document_id}",
    response_model=SearchResponse,
    summary="Find similar documents",
    responses={
        200: {"description": "Similar documents"},
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def find_similar_documents(
    document_id: str,
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    Find documents similar to the given document using its vector representation.
    """
    query_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Get the source document
        doc = await doc_repo.find_by_id(document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        vectors = doc.get("vectors", {})
        if not vectors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no vectors for similarity search"
            )
        
        # Find similar documents using VP-Tree
        similar_results = await search_engine.find_similar(
            vectors=vectors,
            exclude_id=document_id,
            top_k=limit,
            cluster_manager=cluster_manager
        )
        
        search_time_ms = (time.time() - start_time) * 1000
        
        # Format results
        results = []
        for result in similar_results.get("results", []):
            results.append(SearchResultItem(
                document_id=result["document_id"],
                title=result.get("title", "Untitled"),
                content_preview=result.get("content", "")[:300],
                score=result.get("score", 0.0),
                node_id=result.get("node_id", ""),
                metadata=result.get("metadata", {}),
                matched_terms=[]
            ))
        
        return SearchResponse(
            query=f"similar:{document_id}",
            search_type=SearchType.SEMANTIC,
            results=results,
            total_results=len(results),
            searched_nodes=similar_results.get("searched_nodes", 0),
            search_time_ms=search_time_ms,
            query_id=query_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar documents: {str(e)}"
        )


@router.get(
    "/history",
    response_model=SearchHistoryResponse,
    summary="Get search history",
    responses={
        200: {"description": "Search history"}
    }
)
async def get_search_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    history_repo: SearchHistoryRepository = Depends(get_search_history_repository)
):
    """
    Get recent search history.
    """
    try:
        skip = (page - 1) * page_size
        
        history = await history_repo.find(
            filters={},
            skip=skip,
            limit=page_size,
            sort=[("timestamp", -1)]
        )
        total = await history_repo.count({})
        
        items = []
        for h in history:
            items.append(SearchHistoryItem(
                query_id=str(h["_id"]),
                query=h["query"],
                search_type=SearchType(h["search_type"]),
                results_count=h.get("results_count", 0),
                search_time_ms=h.get("search_time_ms", 0),
                timestamp=h["timestamp"]
            ))
        
        return SearchHistoryResponse(
            history=items,
            total=total
        )
        
    except Exception as e:
        logger.error(f"Error getting search history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get search history: {str(e)}"
        )


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear search history",
    responses={
        204: {"description": "History cleared"}
    }
)
async def clear_search_history(
    history_repo: SearchHistoryRepository = Depends(get_search_history_repository)
):
    """
    Clear all search history.
    """
    try:
        await history_repo.delete_all()
        logger.info("Search history cleared")
    except Exception as e:
        logger.error(f"Error clearing search history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear search history: {str(e)}"
        )


def _generate_preview(content: str, query: str, max_length: int = 300) -> str:
    """
    Generate a content preview with highlighted query matches.
    
    Args:
        content: Full document content
        query: Search query
        max_length: Maximum preview length
    
    Returns:
        Content preview with matched terms highlighted
    """
    if not content:
        return ""
    
    # Find query terms in content
    query_terms = query.lower().split()
    content_lower = content.lower()
    
    # Find the best position to start the preview
    best_pos = 0
    best_score = 0
    
    for i in range(0, len(content) - max_length, 50):
        chunk = content_lower[i:i + max_length]
        score = sum(1 for term in query_terms if term in chunk)
        if score > best_score:
            best_score = score
            best_pos = i
    
    # Extract preview
    if len(content) <= max_length:
        preview = content
    else:
        start = max(0, best_pos - 20)
        end = min(len(content), start + max_length)
        preview = content[start:end]
        
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."
    
    # Highlight matched terms (wrap in **)
    for term in query_terms:
        if len(term) > 2:  # Only highlight terms with 3+ characters
            import re
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            preview = pattern.sub(f"**{term}**", preview)
    
    return preview


@router.post(
    "/batch",
    response_model=List[SearchResponse],
    summary="Batch search",
    responses={
        200: {"description": "Batch search results"},
        400: {"model": ErrorResponse, "description": "Too many queries"}
    }
)
async def batch_search(
    queries: List[SearchRequest],
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    history_repo: SearchHistoryRepository = Depends(get_search_history_repository)
):
    """
    Execute multiple search queries in a single request.
    Maximum 10 queries per batch.
    """
    if len(queries) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 queries per batch request"
        )
    
    results = []
    for query in queries:
        try:
            result = await search_documents(
                request=query,
                doc_repo=doc_repo,
                search_engine=search_engine,
                cluster_manager=cluster_manager,
                history_repo=history_repo
            )
            results.append(result)
        except HTTPException as e:
            # Include error information in the result
            results.append(SearchResponse(
                query=query.query,
                search_type=query.search_type,
                results=[],
                total_results=0,
                searched_nodes=0,
                search_time_ms=0,
                query_id=str(uuid.uuid4())
            ))
    
    return results
