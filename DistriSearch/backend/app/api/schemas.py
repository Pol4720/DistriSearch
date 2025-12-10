"""
API Schemas
Pydantic models for request/response validation in DistriSearch API
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


# =======================
# Document Schemas
# =======================

class DocumentBase(BaseModel):
    """Base document schema"""
    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    content: str = Field(..., min_length=1, description="Document content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    tags: Optional[List[str]] = Field(default_factory=list, description="Document tags")


class DocumentCreate(DocumentBase):
    """Schema for creating a document"""
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class DocumentVectors(BaseModel):
    """Document vector representations"""
    tfidf: List[float] = Field(default_factory=list, description="TF-IDF vector")
    minhash: List[int] = Field(default_factory=list, description="MinHash signature")
    lda: List[float] = Field(default_factory=list, description="LDA topic distribution")
    textrank: Optional[List[str]] = Field(default_factory=list, description="TextRank keywords")


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: str = Field(..., description="Document ID")
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    node_id: Optional[str] = Field(None, description="Node where document is stored")
    partition_id: Optional[str] = Field(None, description="Partition ID")
    vectors: Optional[DocumentVectors] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for listing documents"""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response"""
    id: str
    filename: str
    title: str
    content_preview: str = Field(..., description="First 500 characters of content")
    file_size: int
    content_type: str
    node_id: str
    partition_id: str
    created_at: datetime


# =======================
# Search Schemas
# =======================

class SearchType(str, Enum):
    """Types of search queries"""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchRequest(BaseModel):
    """Schema for search request"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    search_type: SearchType = Field(default=SearchType.HYBRID, description="Type of search")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Filter criteria")
    include_vectors: bool = Field(default=False, description="Include vectors in response")
    timeout_ms: int = Field(default=5000, ge=100, le=30000, description="Search timeout in milliseconds")
    
    @validator('query')
    def query_not_empty(cls, v):
        if v.strip() == "":
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class SearchResultItem(BaseModel):
    """Individual search result"""
    document_id: str
    title: str
    content_preview: str = Field(..., description="Snippet with highlighted matches")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    node_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    matched_terms: List[str] = Field(default_factory=list, description="Matched search terms")
    vectors: Optional[DocumentVectors] = None


class SearchResponse(BaseModel):
    """Schema for search response"""
    query: str
    search_type: SearchType
    results: List[SearchResultItem]
    total_results: int
    searched_nodes: int
    search_time_ms: float
    query_id: str
    

class SearchHistoryItem(BaseModel):
    """Search history entry"""
    query_id: str
    query: str
    search_type: SearchType
    results_count: int
    search_time_ms: float
    timestamp: datetime


class SearchHistoryResponse(BaseModel):
    """Search history response"""
    history: List[SearchHistoryItem]
    total: int


# =======================
# Cluster Schemas
# =======================

class NodeStatus(str, Enum):
    """Node status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class NodeRole(str, Enum):
    """Node role values"""
    MASTER = "master"
    SLAVE = "slave"
    CANDIDATE = "candidate"


class NodeInfo(BaseModel):
    """Information about a cluster node"""
    node_id: str
    address: str
    port: int
    role: NodeRole
    status: NodeStatus
    document_count: int = 0
    partition_count: int = 0
    cpu_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    disk_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    last_heartbeat: Optional[datetime] = None
    joined_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClusterStatus(BaseModel):
    """Overall cluster status"""
    cluster_id: str
    master_node_id: Optional[str]
    master_address: Optional[str]
    total_nodes: int
    healthy_nodes: int
    unhealthy_nodes: int
    total_documents: int
    total_partitions: int
    replication_factor: int
    status: NodeStatus
    nodes: List[NodeInfo]
    last_rebalance: Optional[datetime]
    created_at: datetime


class PartitionInfo(BaseModel):
    """Information about a partition"""
    partition_id: str
    primary_node_id: str
    replica_node_ids: List[str]
    document_count: int
    size_bytes: int
    status: str
    created_at: datetime
    last_modified: datetime


class ClusterPartitions(BaseModel):
    """Cluster partitions information"""
    total_partitions: int
    partitions: List[PartitionInfo]
    replication_factor: int


class NodeJoinRequest(BaseModel):
    """Request to join the cluster"""
    node_id: str
    address: str
    port: int
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class NodeJoinResponse(BaseModel):
    """Response for node join request"""
    success: bool
    message: str
    cluster_id: str
    master_node_id: str
    assigned_partitions: List[str]


class RebalanceRequest(BaseModel):
    """Request to trigger cluster rebalance"""
    force: bool = Field(default=False, description="Force rebalance even if balanced")
    target_node_id: Optional[str] = Field(None, description="Target specific node for rebalance")


class RebalanceResponse(BaseModel):
    """Response for rebalance request"""
    success: bool
    message: str
    migrations_planned: int
    estimated_time_seconds: float


# =======================
# Health Check Schemas
# =======================

class HealthStatus(str, Enum):
    """Health status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health of a system component"""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: HealthStatus
    node_id: str
    role: NodeRole
    version: str
    uptime_seconds: float
    components: List[ComponentHealth]
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness check response"""
    ready: bool
    message: str
    checks: Dict[str, bool]


class LivenessResponse(BaseModel):
    """Liveness check response"""
    alive: bool
    timestamp: datetime


# =======================
# Error Schemas
# =======================

class ErrorDetail(BaseModel):
    """Error detail"""
    field: Optional[str] = None
    message: str
    code: str


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    message: str
    details: List[ErrorDetail] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


# =======================
# Pagination Schemas
# =======================

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


# =======================
# WebSocket Schemas
# =======================

class WSMessageType(str, Enum):
    """WebSocket message types"""
    CLUSTER_UPDATE = "cluster_update"
    NODE_STATUS = "node_status"
    SEARCH_PROGRESS = "search_progress"
    REBALANCE_PROGRESS = "rebalance_progress"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class WSMessage(BaseModel):
    """WebSocket message"""
    type: WSMessageType
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSClusterUpdate(BaseModel):
    """WebSocket cluster update message"""
    type: WSMessageType = WSMessageType.CLUSTER_UPDATE
    cluster_status: ClusterStatus


class WSNodeStatus(BaseModel):
    """WebSocket node status message"""
    type: WSMessageType = WSMessageType.NODE_STATUS
    node_id: str
    status: NodeStatus
    metrics: Dict[str, float]
