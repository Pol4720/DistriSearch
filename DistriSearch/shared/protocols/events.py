"""
Event Protocol Definitions

Defines event types for publish-subscribe communication in the cluster.
Events are used for asynchronous notifications about cluster state changes.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    """Types of events in the system."""
    # Node lifecycle events
    NODE_JOINED = "node_joined"
    NODE_LEFT = "node_left"
    NODE_FAILED = "node_failed"
    NODE_RECOVERED = "node_recovered"
    NODE_STATUS_CHANGED = "node_status_changed"
    
    # Document events
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_REPLICATED = "document_replicated"
    DOCUMENT_MIGRATION_STARTED = "document_migration_started"
    DOCUMENT_MIGRATION_COMPLETED = "document_migration_completed"
    
    # Cluster events
    CLUSTER_INITIALIZED = "cluster_initialized"
    CLUSTER_STATUS_CHANGED = "cluster_status_changed"
    
    # Rebalancing events
    REBALANCE_STARTED = "rebalance_started"
    REBALANCE_PROGRESS = "rebalance_progress"
    REBALANCE_COMPLETED = "rebalance_completed"
    REBALANCE_FAILED = "rebalance_failed"
    
    # Leader election events
    LEADER_ELECTION_STARTED = "leader_election_started"
    LEADER_ELECTED = "leader_elected"
    LEADER_LOST = "leader_lost"
    
    # Partition events
    PARTITION_CREATED = "partition_created"
    PARTITION_UPDATED = "partition_updated"
    PARTITION_DELETED = "partition_deleted"
    VP_TREE_RECOMPUTED = "vp_tree_recomputed"
    
    # Replication events
    UNDER_REPLICATION_DETECTED = "under_replication_detected"
    REPLICATION_RESTORED = "replication_restored"


class Event(BaseModel):
    """Base event class for pub-sub communication."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    source_node_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Event metadata
    cluster_id: Optional[str] = None
    sequence_number: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NodeJoinedEvent(BaseModel):
    """Event emitted when a new node joins the cluster."""
    event_type: EventType = EventType.NODE_JOINED
    node_id: str
    node_role: str
    host: str
    port: int
    capacity: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NodeLeftEvent(BaseModel):
    """Event emitted when a node gracefully leaves the cluster."""
    event_type: EventType = EventType.NODE_LEFT
    node_id: str
    reason: str = "graceful_shutdown"
    documents_to_migrate: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NodeFailedEvent(BaseModel):
    """Event emitted when a node fails (heartbeat timeout)."""
    event_type: EventType = EventType.NODE_FAILED
    node_id: str
    last_heartbeat: datetime
    failure_reason: str = "heartbeat_timeout"
    consecutive_failures: int = 0
    documents_affected: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DocumentIndexedEvent(BaseModel):
    """Event emitted when a document is successfully indexed."""
    event_type: EventType = EventType.DOCUMENT_INDEXED
    doc_id: str
    filename: str
    node_id: str
    file_size: int
    partition_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RebalanceStartedEvent(BaseModel):
    """Event emitted when cluster rebalancing starts."""
    event_type: EventType = EventType.REBALANCE_STARTED
    reason: str  # node_joined, node_left, manual, threshold_exceeded
    trigger_node_id: Optional[str] = None  # Node that triggered rebalance
    documents_to_migrate: int = 0
    affected_nodes: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RebalanceProgressEvent(BaseModel):
    """Event emitted periodically during rebalancing."""
    event_type: EventType = EventType.REBALANCE_PROGRESS
    documents_migrated: int = 0
    documents_remaining: int = 0
    current_source_node: Optional[str] = None
    current_target_node: Optional[str] = None
    progress_percent: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RebalanceCompletedEvent(BaseModel):
    """Event emitted when cluster rebalancing completes."""
    event_type: EventType = EventType.REBALANCE_COMPLETED
    documents_migrated: int = 0
    duration_seconds: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LeaderElectedEvent(BaseModel):
    """Event emitted when a new Raft leader is elected."""
    event_type: EventType = EventType.LEADER_ELECTED
    leader_id: str
    term: int
    previous_leader_id: Optional[str] = None
    election_reason: str = "initial"  # initial, timeout, leader_failed
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UnderReplicationEvent(BaseModel):
    """Event emitted when documents become under-replicated."""
    event_type: EventType = EventType.UNDER_REPLICATION_DETECTED
    doc_ids: List[str]
    current_replicas: int
    required_replicas: int
    affected_node_id: Optional[str] = None  # Node that failed
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PartitionUpdatedEvent(BaseModel):
    """Event emitted when VP-Tree partitions are updated."""
    event_type: EventType = EventType.PARTITION_UPDATED
    partition_id: str
    node_id: str
    document_count: int
    radius: float
    action: str = "updated"  # created, updated, deleted
    timestamp: datetime = Field(default_factory=datetime.utcnow)
