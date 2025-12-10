"""
Custom Exceptions
Exception classes for DistriSearch error handling
"""

from fastapi import HTTPException, status
from typing import Optional, Dict, Any, List


class DistriSearchException(Exception):
    """
    Base exception for all DistriSearch errors.
    """
    
    def __init__(
        self,
        message: str,
        code: str = "DISTRISEARCH_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[List[Dict[str, Any]]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response"""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }
    
    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException"""
        return HTTPException(
            status_code=self.status_code,
            detail=self.to_dict()
        )


# Document Exceptions

class DocumentNotFoundError(DistriSearchException):
    """Raised when a document is not found"""
    
    def __init__(self, document_id: str, message: Optional[str] = None):
        super().__init__(
            message=message or f"Document not found: {document_id}",
            code="DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=[{"field": "document_id", "value": document_id}]
        )


class DocumentAlreadyExistsError(DistriSearchException):
    """Raised when trying to create a document that already exists"""
    
    def __init__(self, document_id: str):
        super().__init__(
            message=f"Document already exists: {document_id}",
            code="DOCUMENT_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            details=[{"field": "document_id", "value": document_id}]
        )


class DocumentValidationError(DistriSearchException):
    """Raised when document validation fails"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = []
        if field:
            details.append({"field": field, "message": message})
        
        super().__init__(
            message=message,
            code="DOCUMENT_VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class DocumentTooLargeError(DistriSearchException):
    """Raised when document exceeds size limit"""
    
    def __init__(self, size: int, max_size: int):
        super().__init__(
            message=f"Document size {size} exceeds maximum {max_size}",
            code="DOCUMENT_TOO_LARGE",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details=[{"size": size, "max_size": max_size}]
        )


# Node Exceptions

class NodeNotFoundError(DistriSearchException):
    """Raised when a node is not found"""
    
    def __init__(self, node_id: str, message: Optional[str] = None):
        super().__init__(
            message=message or f"Node not found: {node_id}",
            code="NODE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=[{"field": "node_id", "value": node_id}]
        )


class NodeUnavailableError(DistriSearchException):
    """Raised when a node is unavailable"""
    
    def __init__(self, node_id: str, reason: Optional[str] = None):
        super().__init__(
            message=f"Node unavailable: {node_id}" + (f" - {reason}" if reason else ""),
            code="NODE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=[{"field": "node_id", "value": node_id, "reason": reason}]
        )


class NodeAlreadyExistsError(DistriSearchException):
    """Raised when trying to register a node that already exists"""
    
    def __init__(self, node_id: str):
        super().__init__(
            message=f"Node already registered: {node_id}",
            code="NODE_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            details=[{"field": "node_id", "value": node_id}]
        )


# Cluster Exceptions

class ClusterError(DistriSearchException):
    """Base exception for cluster-related errors"""
    
    def __init__(self, message: str, code: str = "CLUSTER_ERROR"):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ClusterNotInitializedError(ClusterError):
    """Raised when cluster is not initialized"""
    
    def __init__(self):
        super().__init__(
            message="Cluster is not initialized",
            code="CLUSTER_NOT_INITIALIZED"
        )


class NoMasterError(ClusterError):
    """Raised when no master node is available"""
    
    def __init__(self):
        super().__init__(
            message="No master node available",
            code="NO_MASTER"
        )


class RebalanceInProgressError(ClusterError):
    """Raised when rebalance is already in progress"""
    
    def __init__(self):
        super().__init__(
            message="Rebalance operation already in progress",
            code="REBALANCE_IN_PROGRESS"
        )
        self.status_code = status.HTTP_409_CONFLICT


class InsufficientNodesError(ClusterError):
    """Raised when there aren't enough nodes for an operation"""
    
    def __init__(self, required: int, available: int):
        super().__init__(
            message=f"Insufficient nodes: {available} available, {required} required",
            code="INSUFFICIENT_NODES"
        )
        self.details = [{"required": required, "available": available}]


# Search Exceptions

class SearchTimeoutError(DistriSearchException):
    """Raised when search operation times out"""
    
    def __init__(self, query_id: str, timeout_ms: int):
        super().__init__(
            message=f"Search timed out after {timeout_ms}ms",
            code="SEARCH_TIMEOUT",
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            details=[{"query_id": query_id, "timeout_ms": timeout_ms}]
        )


class SearchError(DistriSearchException):
    """Raised when search operation fails"""
    
    def __init__(self, message: str, query_id: Optional[str] = None):
        super().__init__(
            message=message,
            code="SEARCH_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=[{"query_id": query_id}] if query_id else []
        )


class InvalidQueryError(DistriSearchException):
    """Raised when search query is invalid"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="INVALID_QUERY",
            status_code=status.HTTP_400_BAD_REQUEST
        )


# Validation Exceptions

class ValidationError(DistriSearchException):
    """Raised when validation fails"""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None
    ):
        details = []
        if field:
            detail = {"field": field, "message": message}
            if value is not None:
                detail["value"] = str(value)
            details.append(detail)
        
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


# Storage Exceptions

class StorageError(DistriSearchException):
    """Raised when storage operation fails"""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(
            message=message,
            code="STORAGE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=[{"operation": operation}] if operation else []
        )


class DatabaseConnectionError(StorageError):
    """Raised when database connection fails"""
    
    def __init__(self, message: str = "Failed to connect to database"):
        super().__init__(message=message, operation="connect")
        self.code = "DATABASE_CONNECTION_ERROR"


# Replication Exceptions

class ReplicationError(DistriSearchException):
    """Raised when replication operation fails"""
    
    def __init__(self, message: str, document_id: Optional[str] = None):
        super().__init__(
            message=message,
            code="REPLICATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=[{"document_id": document_id}] if document_id else []
        )


class InsufficientReplicasError(ReplicationError):
    """Raised when required number of replicas cannot be achieved"""
    
    def __init__(self, required: int, achieved: int, document_id: Optional[str] = None):
        super().__init__(
            message=f"Could not achieve required replicas: {achieved}/{required}",
            document_id=document_id
        )
        self.code = "INSUFFICIENT_REPLICAS"
        self.details.extend([{"required": required, "achieved": achieved}])


# Authentication Exceptions

class AuthenticationError(DistriSearchException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class AuthorizationError(DistriSearchException):
    """Raised when authorization fails"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN
        )


class TokenExpiredError(AuthenticationError):
    """Raised when authentication token has expired"""
    
    def __init__(self):
        super().__init__(message="Token has expired")
        self.code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when authentication token is invalid"""
    
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message=message)
        self.code = "INVALID_TOKEN"


# Rate Limiting Exceptions

class RateLimitExceededError(DistriSearchException):
    """Raised when rate limit is exceeded"""
    
    def __init__(
        self,
        limit: int,
        window: str = "minute",
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=[{
                "limit": limit,
                "window": window,
                "retry_after": retry_after
            }]
        )
