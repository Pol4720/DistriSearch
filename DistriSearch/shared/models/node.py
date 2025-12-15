"""
Node Data Models

Defines models for cluster nodes (master and slave).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class NodeRole(str, Enum):
    """Role of a node in the cluster."""
    MASTER = "master"
    SLAVE = "slave"


class NodeStatus(str, Enum):
    """Current status of a node."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAINING = "draining"  # Node is being removed, no new documents
    FAILED = "failed"
    STARTING = "starting"
    SYNCING = "syncing"  # Syncing state after recovery


class NodeCapacity(BaseModel):
    """Resource capacity and usage of a node."""
    max_documents: int = Field(
        default=100000,
        description="Maximum documents this node can store"
    )
    current_documents: int = Field(
        default=0,
        description="Current document count"
    )
    storage_total_gb: float = Field(
        default=100.0,
        description="Total storage in GB"
    )
    storage_used_gb: float = Field(
        default=0.0,
        description="Used storage in GB"
    )
    memory_total_mb: int = Field(
        default=2048,
        description="Total memory in MB"
    )
    memory_used_mb: int = Field(
        default=0,
        description="Used memory in MB"
    )
    cpu_cores: int = Field(default=2)
    cpu_usage_percent: float = Field(default=0.0)
    
    @property
    def document_utilization(self) -> float:
        """Document capacity utilization (0-1)."""
        if self.max_documents == 0:
            return 0.0
        return self.current_documents / self.max_documents
    
    @property
    def storage_utilization(self) -> float:
        """Storage utilization (0-1)."""
        if self.storage_total_gb == 0:
            return 0.0
        return self.storage_used_gb / self.storage_total_gb
    
    @property
    def is_overloaded(self) -> bool:
        """Check if node is overloaded (>80% on any metric)."""
        return (
            self.document_utilization > 0.8 or
            self.storage_utilization > 0.8 or
            self.cpu_usage_percent > 80.0
        )


class Node(BaseModel):
    """
    Represents a node in the DistriSearch cluster.
    """
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: NodeRole = NodeRole.SLAVE
    status: NodeStatus = NodeStatus.STARTING
    
    # Network information
    host: str = Field(..., description="Hostname or IP address")
    port: int = Field(default=8000, description="API port")
    grpc_port: int = Field(default=50051, description="gRPC port")
    
    # Cluster membership
    cluster_id: Optional[str] = None
    joined_at: Optional[datetime] = None
    
    # Health monitoring
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_failures: int = Field(
        default=0,
        description="Consecutive heartbeat failures"
    )
    
    # Capacity
    capacity: NodeCapacity = Field(default_factory=NodeCapacity)
    
    # VP-Tree information (for slaves)
    vantage_point: Optional[Dict] = Field(
        None,
        description="VP-Tree vantage point for this node's partition"
    )
    partition_radius: Optional[float] = Field(
        None,
        description="Coverage radius in VP-Tree"
    )
    
    # Raft information (for masters)
    raft_state: Optional[str] = Field(
        None,
        description="Raft state: leader, follower, candidate"
    )
    raft_term: int = Field(default=0)
    
    # Metadata
    version: str = Field(default="1.0.0", description="Software version")
    metadata: Dict = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def address(self) -> str:
        """Full address for HTTP API."""
        return f"http://{self.host}:{self.port}"
    
    @property
    def grpc_address(self) -> str:
        """Full address for gRPC."""
        return f"{self.host}:{self.grpc_port}"
    
    @property
    def is_healthy(self) -> bool:
        """Check if node is healthy."""
        if self.status != NodeStatus.ACTIVE:
            return False
        # Consider unhealthy if no heartbeat in last 30 seconds
        seconds_since_heartbeat = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return seconds_since_heartbeat < 30
    
    def record_heartbeat(self):
        """Record a successful heartbeat."""
        self.last_heartbeat = datetime.utcnow()
        self.heartbeat_failures = 0
    
    def record_heartbeat_failure(self):
        """Record a heartbeat failure."""
        self.heartbeat_failures += 1


class NodeRegistration(BaseModel):
    """Schema for node registration with the master."""
    node_id: str
    role: NodeRole = NodeRole.SLAVE
    host: str
    port: int = 8000
    grpc_port: int = 50051
    capacity: NodeCapacity = Field(default_factory=NodeCapacity)
    version: str = "1.0.0"
    metadata: Dict = Field(default_factory=dict)


class NodeHeartbeat(BaseModel):
    """Heartbeat message from a node."""
    node_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: NodeStatus = NodeStatus.ACTIVE
    capacity: NodeCapacity
    document_count: int = 0
    active_requests: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NodeList(BaseModel):
    """List of nodes response."""
    nodes: List[Node]
    total: int
    active_count: int
    master_node_id: Optional[str] = None
