"""
API Dependencies
FastAPI dependency injection for DistriSearch API
"""

from typing import Optional, AsyncGenerator
from fastapi import Depends, HTTPException, status, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os
import logging

from ..storage.mongodb import (
    MongoDBClient,
    DocumentRepository,
    NodeRepository,
    SearchHistoryRepository,
    ClusterRepository
)
from ..core.search import SearchEngine
from ..distributed.coordination import ClusterManager
from ..config import Settings

logger = logging.getLogger(__name__)


# Global instances (initialized at startup)
_mongodb_client: Optional[MongoDBClient] = None
_document_repository: Optional[DocumentRepository] = None
_node_repository: Optional[NodeRepository] = None
_search_history_repository: Optional[SearchHistoryRepository] = None
_cluster_repository: Optional[ClusterRepository] = None
_search_engine: Optional[SearchEngine] = None
_cluster_manager: Optional[ClusterManager] = None
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


async def init_dependencies(settings: Settings):
    """Initialize all dependencies at application startup"""
    global _mongodb_client, _document_repository, _node_repository
    global _search_history_repository, _cluster_repository
    global _search_engine, _cluster_manager, _settings
    
    _settings = settings
    
    # Initialize MongoDB client
    _mongodb_client = MongoDBClient(
        uri=settings.mongodb_uri,
        database_name=settings.mongodb_database
    )
    await _mongodb_client.connect()
    
    # Initialize repositories
    db = _mongodb_client.database
    _document_repository = DocumentRepository(db)
    _node_repository = NodeRepository(db)
    _search_history_repository = SearchHistoryRepository(db)
    _cluster_repository = ClusterRepository(db)
    
    # Ensure indexes are created
    await _document_repository.ensure_indexes()
    await _node_repository.ensure_indexes()
    await _search_history_repository.ensure_indexes()
    await _cluster_repository.ensure_indexes()
    
    # Initialize search engine
    _search_engine = SearchEngine()
    
    # Initialize cluster manager
    _cluster_manager = ClusterManager(
        node_id=settings.node_id,
        node_address=settings.node_address,
        node_port=settings.node_port
    )
    
    logger.info("Dependencies initialized successfully")


async def shutdown_dependencies():
    """Cleanup dependencies at application shutdown"""
    global _mongodb_client, _cluster_manager
    
    if _mongodb_client:
        await _mongodb_client.disconnect()
        _mongodb_client = None
    
    if _cluster_manager:
        await _cluster_manager.shutdown()
        _cluster_manager = None
    
    logger.info("Dependencies cleaned up")


async def get_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    if _mongodb_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized"
        )
    return _mongodb_client.database


async def get_document_repository() -> DocumentRepository:
    """Get document repository instance"""
    if _document_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document repository not initialized"
        )
    return _document_repository


async def get_node_repository() -> NodeRepository:
    """Get node repository instance"""
    if _node_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node repository not initialized"
        )
    return _node_repository


async def get_search_history_repository() -> SearchHistoryRepository:
    """Get search history repository instance"""
    if _search_history_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search history repository not initialized"
        )
    return _search_history_repository


async def get_cluster_repository() -> ClusterRepository:
    """Get cluster repository instance"""
    if _cluster_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cluster repository not initialized"
        )
    return _cluster_repository


async def get_search_engine() -> SearchEngine:
    """Get search engine instance"""
    if _search_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search engine not initialized"
        )
    return _search_engine


async def get_cluster_manager() -> ClusterManager:
    """Get cluster manager instance"""
    if _cluster_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cluster manager not initialized"
        )
    return _cluster_manager


def get_current_node() -> dict:
    """Get current node information"""
    settings = get_settings()
    return {
        "node_id": settings.node_id,
        "address": settings.node_address,
        "port": settings.node_port,
        "role": os.getenv("NODE_ROLE", "slave")
    }


async def verify_master_node(
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """Verify that the current node is the master"""
    if not cluster_manager.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation can only be performed by the master node"
        )


async def verify_cluster_ready(
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """Verify that the cluster is ready"""
    if not cluster_manager.is_initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cluster is not ready"
        )


def get_request_id(request: Request) -> Optional[str]:
    """Get request ID from headers"""
    return request.headers.get("X-Request-ID")


class RateLimiter:
    """Simple rate limiter for API endpoints"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict = {}  # Track requests per IP
    
    async def check_rate_limit(self, request: Request):
        """Check if request is within rate limit"""
        from datetime import datetime, timedelta
        import time
        
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Clean old entries
        if client_ip in self._requests:
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if t > minute_ago
            ]
        else:
            self._requests[client_ip] = []
        
        # Check rate limit
        if len(self._requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Add current request
        self._requests[client_ip].append(current_time)


# Global rate limiter instances
search_rate_limiter = RateLimiter(requests_per_minute=60)
upload_rate_limiter = RateLimiter(requests_per_minute=10)


async def rate_limit_search(request: Request):
    """Rate limit for search endpoints"""
    await search_rate_limiter.check_rate_limit(request)


async def rate_limit_upload(request: Request):
    """Rate limit for upload endpoints"""
    await upload_rate_limiter.check_rate_limit(request)
