"""
Database Models for DistriSearch.

Defines Pydantic models for MongoDB documents.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, EmailStr
import uuid
import hashlib
import secrets


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


class UserRole(str, Enum):
    """User roles."""
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class UserStatus(str, Enum):
    """User status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserModel(BaseModel):
    """
    User model for authentication.
    
    Represents a user in the system.
    """
    id: str = Field(default_factory=generate_id)
    username: str
    email: str
    password_hash: str
    salt: str = Field(default_factory=lambda: secrets.token_hex(32))
    
    # Profile
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Permissions
    role: UserRole = UserRole.USER
    permissions: List[str] = Field(default_factory=list)
    
    # Status
    status: UserStatus = UserStatus.ACTIVE
    email_verified: bool = False
    
    # Security
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    
    # Tokens
    refresh_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
    
    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Hash a password with salt using SHA-256."""
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return self.password_hash == self.hash_password(password, self.salt)
    
    @classmethod
    def create_user(cls, username: str, email: str, password: str, **kwargs) -> "UserModel":
        """Create a new user with hashed password."""
        salt = secrets.token_hex(32)
        password_hash = cls.hash_password(password, salt)
        return cls(
            username=username,
            email=email,
            password_hash=password_hash,
            salt=salt,
            **kwargs
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB."""
        return {
            "_id": self.id,
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "salt": self.salt,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "permissions": self.permissions,
            "status": self.status,
            "email_verified": self.email_verified,
            "failed_login_attempts": self.failed_login_attempts,
            "locked_until": self.locked_until,
            "last_login": self.last_login,
            "last_password_change": self.last_password_change,
            "refresh_token": self.refresh_token,
            "password_reset_token": self.password_reset_token,
            "password_reset_expires": self.password_reset_expires,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    def to_public_dict(self) -> Dict[str, Any]:
        """Convert to public dictionary (no sensitive data)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserModel":
        """Create from MongoDB document."""
        data = data.copy()
        data["id"] = data.pop("_id", data.get("id"))
        return cls(**data)


class DocumentStatus(str, Enum):
    """Document status."""
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class NodeStatus(str, Enum):
    """Node status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    DRAINING = "draining"


class NodeRole(str, Enum):
    """Node role."""
    MASTER = "master"
    SLAVE = "slave"


class DocumentModel(BaseModel):
    """
    Document model for storage.
    
    Represents a document stored in the distributed system.
    """
    id: str = Field(default_factory=generate_id)
    title: Optional[str] = None
    content: str
    content_hash: Optional[str] = None
    
    # Source information
    filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    
    # Location
    primary_node_id: Optional[str] = None
    partition_id: Optional[str] = None
    replica_node_ids: List[str] = Field(default_factory=list)
    
    # Vector representation
    vector_tfidf: Optional[List[float]] = None
    vector_minhash: Optional[List[int]] = None
    vector_lda: Optional[List[float]] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Status
    status: DocumentStatus = DocumentStatus.PENDING
    error_message: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    indexed_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB."""
        return {
            "_id": self.id,
            "title": self.title,
            "content": self.content,
            "content_hash": self.content_hash,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "primary_node_id": self.primary_node_id,
            "partition_id": self.partition_id,
            "replica_node_ids": self.replica_node_ids,
            "vector_tfidf": self.vector_tfidf,
            "vector_minhash": self.vector_minhash,
            "vector_lda": self.vector_lda,
            "metadata": self.metadata,
            "tags": self.tags,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "indexed_at": self.indexed_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentModel":
        """Create from MongoDB document."""
        data["id"] = data.pop("_id", data.get("id"))
        return cls(**data)


class NodeModel(BaseModel):
    """
    Node model for storage.
    
    Represents a node in the cluster.
    """
    id: str = Field(default_factory=generate_id)
    name: Optional[str] = None
    address: str
    port: int = 8000
    role: NodeRole = NodeRole.SLAVE
    status: NodeStatus = NodeStatus.ACTIVE
    
    # Resources
    cpu_cores: Optional[int] = None
    memory_mb: Optional[int] = None
    disk_gb: Optional[int] = None
    
    # Current state
    documents_count: int = 0
    partition_ids: List[str] = Field(default_factory=list)
    load: float = 0.0
    
    # Health
    last_heartbeat: Optional[datetime] = None
    health_score: float = 1.0
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
    
    @property
    def full_address(self) -> str:
        """Get full address with port."""
        return f"{self.address}:{self.port}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB."""
        return {
            "_id": self.id,
            "name": self.name,
            "address": self.address,
            "port": self.port,
            "role": self.role,
            "status": self.status,
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_gb": self.disk_gb,
            "documents_count": self.documents_count,
            "partition_ids": self.partition_ids,
            "load": self.load,
            "last_heartbeat": self.last_heartbeat,
            "health_score": self.health_score,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeModel":
        """Create from MongoDB document."""
        data["id"] = data.pop("_id", data.get("id"))
        return cls(**data)


class PartitionModel(BaseModel):
    """
    Partition model for storage.
    
    Represents a partition of documents.
    """
    id: str = Field(default_factory=generate_id)
    name: Optional[str] = None
    
    # Assignment
    primary_node_id: Optional[str] = None
    replica_node_ids: List[str] = Field(default_factory=list)
    
    # Contents
    document_ids: List[str] = Field(default_factory=list)
    documents_count: int = 0
    
    # VP-Tree representation
    centroid_vector: Optional[List[float]] = None
    radius: float = 0.0
    
    # Status
    is_active: bool = True
    is_rebalancing: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB."""
        return {
            "_id": self.id,
            "name": self.name,
            "primary_node_id": self.primary_node_id,
            "replica_node_ids": self.replica_node_ids,
            "document_ids": self.document_ids,
            "documents_count": self.documents_count,
            "centroid_vector": self.centroid_vector,
            "radius": self.radius,
            "is_active": self.is_active,
            "is_rebalancing": self.is_rebalancing,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PartitionModel":
        """Create from MongoDB document."""
        data["id"] = data.pop("_id", data.get("id"))
        return cls(**data)


class SearchQueryModel(BaseModel):
    """
    Search query model for logging/analytics.
    
    Records search queries for analysis.
    """
    id: str = Field(default_factory=generate_id)
    
    # Query
    query_text: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 10
    
    # Results
    total_results: int = 0
    results_returned: int = 0
    
    # Performance
    query_time_ms: float = 0.0
    nodes_queried: List[str] = Field(default_factory=list)
    
    # User info
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB."""
        return {
            "_id": self.id,
            "query_text": self.query_text,
            "filters": self.filters,
            "limit": self.limit,
            "total_results": self.total_results,
            "results_returned": self.results_returned,
            "query_time_ms": self.query_time_ms,
            "nodes_queried": self.nodes_queried,
            "user_id": self.user_id,
            "client_ip": self.client_ip,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchQueryModel":
        """Create from MongoDB document."""
        data["id"] = data.pop("_id", data.get("id"))
        return cls(**data)


class MetricsModel(BaseModel):
    """
    Metrics model for time-series data.
    """
    id: str = Field(default_factory=generate_id)
    
    # Source
    node_id: str
    metric_type: str
    
    # Values
    value: float
    values: Dict[str, float] = Field(default_factory=dict)
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB."""
        return {
            "_id": self.id,
            "node_id": self.node_id,
            "metric_type": self.metric_type,
            "value": self.value,
            "values": self.values,
            "timestamp": self.timestamp,
        }
