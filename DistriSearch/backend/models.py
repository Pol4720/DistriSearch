"""
DistriSearch Backend - Modelos para API

Este módulo re-exporta los modelos desde core/models.py para mantener
compatibilidad con el código existente del backend.

IMPORTANTE: No definir modelos aquí, usar core/models.py
"""

from core.models import (
    # Enums
    NodeRole,
    NodeStatus,
    MessageType,
    FileType,
    
    # Dataclasses
    NodeInfo,
    ClusterMessage,
    SlaveProfile,
    QueryResult,
    
    # Pydantic Models
    FileMetaModel,
    NodeInfoModel,
    SearchQueryModel,
    SearchResultModel,
    UserCreate,
    UserLogin,
    Token,
    TokenData,
    DownloadRequest,
    NodeRegistration,
    
    # Aliases
    FileMeta,
    SearchQuery,
    SearchResult,
)

# Re-exportar con nombres originales para compatibilidad total
__all__ = [
    # Enums
    'NodeRole',
    'NodeStatus', 
    'MessageType',
    'FileType',
    
    # Dataclasses
    'NodeInfo',
    'ClusterMessage',
    'SlaveProfile',
    'QueryResult',
    
    # Pydantic Models
    'FileMetaModel',
    'NodeInfoModel',
    'SearchQueryModel', 
    'SearchResultModel',
    'UserCreate',
    'UserLogin',
    'Token',
    'TokenData',
    'DownloadRequest',
    'NodeRegistration',
    
    # Aliases para compatibilidad
    'FileMeta',
    'SearchQuery',
    'SearchResult',
]

