# DistriSearch API Module
# FastAPI routers and endpoints for the distributed search system

from .router import api_router
from .dependencies import (
    get_db,
    get_document_repository,
    get_search_engine,
    get_cluster_manager,
    get_current_node
)

__all__ = [
    "api_router",
    "get_db",
    "get_document_repository",
    "get_search_engine",
    "get_cluster_manager",
    "get_current_node"
]
