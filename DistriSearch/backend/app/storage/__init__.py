"""
Storage module for DistriSearch.

This module contains the data storage components:
- mongodb: MongoDB client and repositories
- models: Database models
- file_handler: File upload and processing
- content_extractor: Extract text from various file formats
- cache: Caching layer
"""

from app.storage.mongodb import (
    MongoDBClient,
    DocumentRepository,
    ClusterRepository,
    MetricsRepository,
)
from app.storage.models import (
    DocumentModel,
    NodeModel,
    PartitionModel,
    SearchQueryModel,
)
from app.storage.file_handler import (
    FileHandler,
    UploadedFile,
)
from app.storage.content_extractor import (
    ContentExtractor,
    ExtractedContent,
)

__all__ = [
    # MongoDB
    "MongoDBClient",
    "DocumentRepository",
    "ClusterRepository",
    "MetricsRepository",
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
