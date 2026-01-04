"""
Storage module for DistriSearch.

This module contains the data storage components:
- mongodb: MongoDB client and DocumentRepository (local documents per node)
- sqlite_client: SQLite client for replicated data (users, nodes, partitions)
- sqlite_user_repository: User management with SQLite
- sqlite_cluster_repository: Node and partition management with SQLite
- user_document_registry: Distributed registry for user->document mapping
- models: Database models
- file_handler: File upload and processing
- content_extractor: Extract text from various file formats

Architecture:
- SQLite (Raft-replicated): users, nodes, partitions
- MongoDB (LOCAL per node): documents
- UserDocumentRegistry (Gossip-based): user->documents mapping
"""

from .mongodb import (
    MongoDBClient,
    DocumentRepository,
    MetricsRepository,
)
from .sqlite_client import SQLiteClient
from .sqlite_user_repository import SQLiteUserRepository
from .sqlite_cluster_repository import (
    SQLiteNodeRepository,
    SQLitePartitionRepository,
)
from .user_document_registry import UserDocumentRegistry
from .models import (
    DocumentModel,
    NodeModel,
    PartitionModel,
    SearchQueryModel,
)
from .file_handler import (
    FileHandler,
    UploadedFile,
)
from .content_extractor import (
    ContentExtractor,
    ExtractedContent,
)

__all__ = [
    # MongoDB (local documents per node)
    "MongoDBClient",
    "DocumentRepository",
    "MetricsRepository",
    # SQLite (replicated via Raft)
    "SQLiteClient",
    "SQLiteUserRepository",
    "SQLiteNodeRepository",
    "SQLitePartitionRepository",
    # Distributed Registry (Gossip-based)
    "UserDocumentRegistry",
    # Models
    "DocumentModel",
    "NodeModel",
    "PartitionModel",
    "SearchQueryModel",
    # File handling
    "FileHandler",
    "UploadedFile",
    # Content extraction
    "ContentExtractor",
    "ExtractedContent",
]
