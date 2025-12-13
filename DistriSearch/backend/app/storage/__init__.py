"""
Storage module for DistriSearch.

This module contains the data storage components:
- mongodb: MongoDB client and repositories
- models: Database models
- file_handler: File upload and processing
- content_extractor: Extract text from various file formats
- cache: Caching layer
"""

from .mongodb import (
    MongoDBClient,
    DocumentRepository,
    ClusterRepository,
    MetricsRepository,
)
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
