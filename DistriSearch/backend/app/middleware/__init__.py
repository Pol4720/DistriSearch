# DistriSearch Middleware Module
# Provides common middleware components for the FastAPI application

from .auth import AuthMiddleware, JWTHandler, get_current_user
from .rate_limiter import RateLimiterMiddleware, rate_limit
from .logging_middleware import LoggingMiddleware, RequestLogger
from .exceptions import (
    DistriSearchException,
    DocumentNotFoundError,
    NodeNotFoundError,
    ClusterError,
    SearchTimeoutError,
    ValidationError
)
from .validators import (
    validate_document_content,
    validate_search_query,
    validate_node_id,
    sanitize_input
)

__all__ = [
    # Auth
    "AuthMiddleware",
    "JWTHandler",
    "get_current_user",
    
    # Rate limiting
    "RateLimiterMiddleware",
    "rate_limit",
    
    # Logging
    "LoggingMiddleware",
    "RequestLogger",
    
    # Exceptions
    "DistriSearchException",
    "DocumentNotFoundError",
    "NodeNotFoundError",
    "ClusterError",
    "SearchTimeoutError",
    "ValidationError",
    
    # Validators
    "validate_document_content",
    "validate_search_query",
    "validate_node_id",
    "sanitize_input"
]
