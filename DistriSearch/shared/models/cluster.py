"""
Cluster Data Models

Defines models for cluster state, configuration, and partition information.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from shared.models.node import Node, NodeStatus


class ClusterStatus(str, Enum):
    """Overall cluster status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    INITIALIZING = "initializing"
    MAINTENANCE = "maintenance"


class ReplicationStatus(str, Enum):
    """Replication status for a document."""
    FULLY_REPLICATED = "fully_replicated"
    UNDER_REPLICATED = "under_replicated"
    REPLICATING = "replicating"
    FAILED = "failed"


class PartitionInfo(BaseModel):
    """Information about a VP-Tree partition."""
    partition_id: str
    node_id: str
    vantage_point: Dict = Field(
        default_factory=dict,
        description="VP-Tree vantage point vector"
    )
    radius: float = Field(
        default=0.0,
        description="Coverage radius"
    )
    document_count: int = 0
    left_child: Optional[str] = None
    right_child: Optional[str] = None
    parent: Optional[str] = None
    depth: int = 0
    
    # Statistics
    avg_distance: float = 0.0
    max_distance: float = 0.0
    min_distance: float = 0.0


class ClusterConfig(BaseModel):
    """Cluster configuration."""
    cluster_id: str
    cluster_name: str = "distrisearch"
    
    # Replication settings
    replication_factor: int = Field(
        default=2,
        description="Number of replicas for each document"
    )
    min_replicas_for_write: int = Field(
        default=1,
        description="Minimum replicas needed for write to succeed"
    )
    
    # Raft settings
    raft_election_timeout_min_ms: int = 150
    raft_election_timeout_max_ms: int = 300
    raft_heartbeat_interval_ms: int = 50
    
    # Heartbeat settings
    heartbeat_interval_seconds: int = 5
    heartbeat_timeout_seconds: int = 15
    max_heartbeat_failures: int = 3
    
    # Rebalancing settings
    rebalance_threshold: float = Field(
        default=0.8,
        description="Node utilization threshold to trigger rebalancing"
    )
    rebalance_batch_size: int = Field(
        default=50,
        description="Documents per migration batch"
    )
    rebalance_delay_seconds: float = Field(
        default=1.0,
        description="Delay between migration batches"
    )
    
    # Search settings
    search_timeout_seconds: int = 30
    max_results_per_node: int = 100
    
    # VP-Tree settings
    vp_tree_leaf_size: int = Field(
        default=10,
        description="Minimum documents per VP-Tree leaf"
    )
    
    # DNS settings
    dns_fallback_enabled: bool = True
    dns_cache_ttl_seconds: int = 30


class ClusterState(BaseModel):
    """
    Current state of the cluster.
    Maintained by the master and replicated via Raft.
    """
    cluster_id: str
    status: ClusterStatus = ClusterStatus.INITIALIZING
    config: ClusterConfig
    
    # Nodes
    nodes: Dict[str, Node] = Field(default_factory=dict)
    master_node_id: Optional[str] = None
    
    # Partitions (VP-Tree)
    partitions: Dict[str, PartitionInfo] = Field(default_factory=dict)
    root_partition_id: Optional[str] = None
    
    # Statistics
    total_documents: int = 0
    total_storage_used_gb: float = 0.0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_rebalance_at: Optional[datetime] = None
    
    # Raft state
    raft_term: int = 0
    raft_leader_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def active_nodes(self) -> List[Node]:
        """Get list of active nodes."""
        return [n for n in self.nodes.values() if n.status == NodeStatus.ACTIVE]
    
    @property
    def slave_nodes(self) -> List[Node]:
        """Get list of slave nodes."""
        from shared.models.node import NodeRole
        return [n for n in self.nodes.values() if n.role == NodeRole.SLAVE]
    
    @property
    def master_nodes(self) -> List[Node]:
        """Get list of master nodes."""
        from shared.models.node import NodeRole
        return [n for n in self.nodes.values() if n.role == NodeRole.MASTER]
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def add_node(self, node: Node):
        """Add a node to the cluster."""
        self.nodes[node.node_id] = node
        self.updated_at = datetime.utcnow()
    
    def remove_node(self, node_id: str) -> Optional[Node]:
        """Remove a node from the cluster."""
        node = self.nodes.pop(node_id, None)
        if node:
            self.updated_at = datetime.utcnow()
        return node
    
    def calculate_status(self) -> ClusterStatus:
        """Calculate overall cluster status based on node health."""
        if not self.nodes:
            return ClusterStatus.INITIALIZING
        
        active_count = len(self.active_nodes)
        total_count = len(self.nodes)
        
        if active_count == 0:
            return ClusterStatus.CRITICAL
        
        ratio = active_count / total_count
        if ratio >= 0.9:
            return ClusterStatus.HEALTHY
        elif ratio >= 0.5:
            return ClusterStatus.DEGRADED
        else:
            return ClusterStatus.CRITICAL


class DocumentLocation(BaseModel):
    """Location information for a document."""
    doc_id: str
    primary_node_id: str
    replica_node_ids: List[str] = Field(default_factory=list)
    partition_id: str
    vp_distance: float = Field(
        default=0.0,
        description="Distance from partition vantage point"
    )
    replication_status: ReplicationStatus = ReplicationStatus.UNDER_REPLICATED
    
    @property
    def all_node_ids(self) -> List[str]:
        """Get all nodes (primary + replicas)."""
        return [self.primary_node_id] + self.replica_node_ids


class MigrationTask(BaseModel):
    """Task for migrating documents during rebalancing."""
    task_id: str
    doc_ids: List[str]
    source_node_id: str
    target_node_id: str
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ClusterMetrics(BaseModel):
    """Cluster-wide metrics."""
    total_nodes: int = 0
    active_nodes: int = 0
    total_documents: int = 0
    total_storage_gb: float = 0.0
    used_storage_gb: float = 0.0
    avg_node_utilization: float = 0.0
    queries_per_second: float = 0.0
    avg_query_latency_ms: float = 0.0
    replication_health: float = Field(
        default=1.0,
        description="Ratio of fully replicated documents"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
