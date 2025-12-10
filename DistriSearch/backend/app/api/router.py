"""
API Router
Main router combining all API endpoints for DistriSearch
"""

from fastapi import APIRouter

from .documents import router as documents_router
from .search import router as search_router
from .cluster import router as cluster_router
from .health import router as health_router
from .websocket import router as websocket_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include all routers
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(cluster_router)
api_router.include_router(health_router)
api_router.include_router(websocket_router)


# Root endpoint
@api_router.get("/", tags=["root"])
async def root():
    """
    API root endpoint.
    Returns API information and available endpoints.
    """
    return {
        "name": "DistriSearch API",
        "version": "1.0.0",
        "description": "Distributed document search system API",
        "endpoints": {
            "documents": "/api/v1/documents",
            "search": "/api/v1/search",
            "cluster": "/api/v1/cluster",
            "health": "/api/v1/health",
            "websocket": "/ws"
        },
        "documentation": "/docs"
    }
