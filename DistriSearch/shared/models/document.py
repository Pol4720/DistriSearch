"""
Document Data Models

Defines the core document model and related types used throughout the system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import uuid


class DocumentStatus(str, Enum):
    """Document lifecycle status."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class NameVector(BaseModel):
    """
    Vector representation of document filename.
    Level 1 of the Adaptive Document Vector.
    """
    tokens_tfidf: Dict[str, float] = Field(
        default_factory=dict,
        description="TF-IDF weights for filename tokens"
    )
    char_ngrams_signature: List[int] = Field(
        default_factory=list,
        description="MinHash signature from character n-grams (128 values)"
    )
    category: Dict[str, str] = Field(
        default_factory=dict,
        description="Inferred categories (domain, type, temporal)"
    )


class ContentVector(BaseModel):
    """
    Vector representation of document content.
    Level 2 of the Adaptive Document Vector.
    """
    minhash_signatures: List[List[int]] = Field(
        default_factory=list,
        description="MinHash signatures for content segments"
    )
    keywords_textrank: List[str] = Field(
        default_factory=list,
        description="Keywords extracted via TextRank"
    )
    topic_distribution: List[float] = Field(
        default_factory=list,
        description="LDA topic probabilities"
    )


class StructuralFeatures(BaseModel):
    """
    Structural metadata features.
    Level 3 of the Adaptive Document Vector.
    """
    extension: str = ""
    name_length: int = 0
    file_size: int = 0
    has_date_pattern: bool = False
    has_version: bool = False
    section_count: int = 0
    has_tables: bool = False


class DocumentVector(BaseModel):
    """
    Adaptive Document Vector with three levels:
    1. Name vector (high priority)
    2. Content vector (segmented)
    3. Structural features
    """
    name_vector: NameVector = Field(default_factory=NameVector)
    content_vector: ContentVector = Field(default_factory=ContentVector)
    structural_features: StructuralFeatures = Field(default_factory=StructuralFeatures)
    
    # Computed similarity weights
    name_weight: float = Field(default=0.4, description="Weight for name similarity")
    content_weight: float = Field(default=0.4, description="Weight for content similarity")
    topic_weight: float = Field(default=0.2, description="Weight for topic similarity")


class DocumentMetadata(BaseModel):
    """Additional document metadata."""
    author: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """
    Core Document model representing a document in the distributed system.
    """
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content_hash: Optional[str] = Field(
        None,
        description="SHA-256 hash of content for deduplication"
    )
    file_path: Optional[str] = Field(
        None,
        description="Path to document on filesystem"
    )
    file_size: int = 0
    mime_type: str = "application/octet-stream"
    
    # Location information
    node_id: str = Field(..., description="Primary node storing this document")
    replica_nodes: List[str] = Field(
        default_factory=list,
        description="Nodes with replicas"
    )
    
    # Vector representation
    vector: Optional[DocumentVector] = None
    
    # VP-Tree distance from vantage point
    vp_distance: Optional[float] = None
    
    # Status and timestamps
    status: DocumentStatus = DocumentStatus.PENDING
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    indexed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('updated_at', pre=True, always=True)
    def set_updated_at(cls, v):
        return v or datetime.utcnow()


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    filename: str
    content: Optional[bytes] = None
    metadata: Optional[DocumentMetadata] = None
    tags: List[str] = Field(default_factory=list)
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v) > 255:
            raise ValueError("Filename must be 1-255 characters")
        # Basic sanitization
        forbidden = ['/', '\\', '..', '\x00']
        for char in forbidden:
            if char in v:
                raise ValueError(f"Filename cannot contain '{char}'")
        return v


class DocumentUpdate(BaseModel):
    """Schema for updating document metadata."""
    filename: Optional[str] = None
    metadata: Optional[DocumentMetadata] = None
    tags: Optional[List[str]] = None
    
    @validator('filename')
    def validate_filename(cls, v):
        if v is not None:
            if len(v) > 255:
                raise ValueError("Filename must be <= 255 characters")
        return v


class DocumentSearchResult(BaseModel):
    """Search result for a document."""
    doc_id: str
    filename: str
    score: float = Field(..., description="Relevance score (0-1)")
    node_id: str
    snippet: Optional[str] = Field(
        None,
        description="Content snippet with highlighted matches"
    )
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    file_size: int = 0
    mime_type: str = "application/octet-stream"
    created_at: datetime
    
    # Similarity breakdown
    name_similarity: Optional[float] = None
    content_similarity: Optional[float] = None
    topic_similarity: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
