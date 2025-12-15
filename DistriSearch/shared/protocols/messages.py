"""
Message Protocol Definitions

Defines message formats for request-reply communication between nodes.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class MessageType(str, Enum):
    """Types of messages in the system."""
    # Search operations
    SEARCH_REQUEST = "search_request"
    SEARCH_RESPONSE = "search_response"
    
    # Document operations
    UPLOAD_REQUEST = "upload_request"
    UPLOAD_RESPONSE = "upload_response"
    DELETE_REQUEST = "delete_request"
    DELETE_RESPONSE = "delete_response"
    
    # Replication operations
    REPLICATION_REQUEST = "replication_request"
    REPLICATION_RESPONSE = "replication_response"
    
    # Migration operations
    MIGRATION_REQUEST = "migration_request"
    MIGRATION_RESPONSE = "migration_response"
    MIGRATION_PREPARE = "migration_prepare"
    MIGRATION_COMMIT = "migration_commit"
    MIGRATION_ABORT = "migration_abort"
    
    # Cluster operations
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    REGISTER_NODE = "register_node"
    REGISTER_ACK = "register_ack"
    PARTITION_UPDATE = "partition_update"
    
    # Raft consensus
    RAFT_REQUEST_VOTE = "raft_request_vote"
    RAFT_VOTE_RESPONSE = "raft_vote_response"
    RAFT_APPEND_ENTRIES = "raft_append_entries"
    RAFT_APPEND_RESPONSE = "raft_append_response"


class Message(BaseModel):
    """Base message class for all inter-node communication."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType
    source_node_id: str
    target_node_id: Optional[str] = None  # None for broadcast
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None  # For request-response matching
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SearchRequest(BaseModel):
    """Request for distributed search."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    query_vector: Optional[Dict] = None  # Pre-computed query vector
    filters: Dict[str, Any] = Field(default_factory=dict)
    max_results: int = 10
    offset: int = 0
    include_snippets: bool = True
    timeout_seconds: int = 30
    
    # Search parameters
    name_weight: float = 0.4
    content_weight: float = 0.4
    topic_weight: float = 0.2
    min_score: float = 0.0
    
    # Target nodes (if specified by master)
    target_nodes: List[str] = Field(
        default_factory=list,
        description="Specific nodes to search (empty = all)"
    )


class SearchResult(BaseModel):
    """Individual search result from a node."""
    doc_id: str
    filename: str
    score: float
    node_id: str
    snippet: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    name_similarity: Optional[float] = None
    content_similarity: Optional[float] = None
    topic_similarity: Optional[float] = None


class SearchResponse(BaseModel):
    """Response containing search results."""
    request_id: str
    node_id: str
    results: List[SearchResult] = Field(default_factory=list)
    total_hits: int = 0
    search_time_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None


class UploadRequest(BaseModel):
    """Request to upload a document."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content_hash: str
    file_size: int
    mime_type: str = "application/octet-stream"
    target_node_id: Optional[str] = None  # Assigned by master
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # For chunked uploads
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    is_final_chunk: bool = True


class UploadResponse(BaseModel):
    """Response to upload request."""
    request_id: str
    doc_id: Optional[str] = None
    node_id: str
    success: bool = True
    error_message: Optional[str] = None
    
    # For chunked uploads
    bytes_received: int = 0
    upload_complete: bool = False


class ReplicationRequest(BaseModel):
    """Request to replicate a document to another node."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    source_node_id: str
    target_node_id: str
    document_data: Optional[Dict] = None  # Document metadata
    include_content: bool = True
    priority: int = Field(
        default=0,
        description="Higher priority = process sooner"
    )


class ReplicationResponse(BaseModel):
    """Response to replication request."""
    request_id: str
    doc_id: str
    target_node_id: str
    success: bool = True
    error_message: Optional[str] = None
    bytes_transferred: int = 0
    replication_time_ms: float = 0.0


class MigrationRequest(BaseModel):
    """Request for two-phase document migration."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str  # Migration task ID
    doc_ids: List[str]
    source_node_id: str
    target_node_id: str
    phase: str = "prepare"  # prepare, commit, abort
    batch_index: int = 0
    total_batches: int = 1


class MigrationResponse(BaseModel):
    """Response to migration request."""
    request_id: str
    task_id: str
    phase: str
    success: bool = True
    error_message: Optional[str] = None
    docs_processed: int = 0
    docs_failed: int = 0
    ready_for_commit: bool = False  # For prepare phase


class RaftRequestVote(BaseModel):
    """Raft RequestVote RPC."""
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


class RaftVoteResponse(BaseModel):
    """Response to Raft RequestVote."""
    term: int
    vote_granted: bool
    voter_id: str


class RaftAppendEntries(BaseModel):
    """Raft AppendEntries RPC."""
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[Dict] = Field(default_factory=list)
    leader_commit: int


class RaftAppendResponse(BaseModel):
    """Response to Raft AppendEntries."""
    term: int
    success: bool
    follower_id: str
    match_index: int = 0
