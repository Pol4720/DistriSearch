"""
Cluster Manager for DistriSearch.

Manages cluster membership, state, and coordination
between master and slave nodes.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Set, Callable, Awaitable
from datetime import datetime

from app.distributed.consensus import RaftNode, Command, CommandType
from app.distributed.communication import (
    HeartbeatService,
    NodeHeartbeat,
    NodeStatus,
    MessageBroker,
    Message,
    MessageType,
)

logger = logging.getLogger(__name__)


class ClusterState(Enum):
    """Overall cluster state."""
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    CRITICAL = "critical"


class NodeRole(Enum):
    """Node role in the cluster."""
    MASTER = "master"
    SLAVE = "slave"


@dataclass
class NodeMembership:
    """
    Information about a node in the cluster.
    
    Attributes:
        node_id: Unique node identifier
        address: Network address (host:port)
        role: Node role (master/slave)
        status: Current health status
        joined_at: When node joined the cluster
        last_seen: Last time node was seen
        documents_count: Number of documents stored
        load: Current load (0.0 - 1.0)
        partitions: Set of partition IDs assigned
        metadata: Additional node metadata
    """
    node_id: str
    address: str
    role: NodeRole = NodeRole.SLAVE
    status: NodeStatus = NodeStatus.UNKNOWN
    joined_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    documents_count: int = 0
    load: float = 0.0
    partitions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "role": self.role.value,
            "status": self.status.value,
            "joined_at": self.joined_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "documents_count": self.documents_count,
            "load": self.load,
            "partitions": list(self.partitions),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeMembership":
        """Create from dictionary."""
        return cls(
            node_id=data["node_id"],
            address=data["address"],
            role=NodeRole(data.get("role", "slave")),
            status=NodeStatus(data.get("status", "unknown")),
            joined_at=datetime.fromisoformat(data.get("joined_at", datetime.now().isoformat())),
            last_seen=datetime.fromisoformat(data.get("last_seen", datetime.now().isoformat())),
            documents_count=data.get("documents_count", 0),
            load=data.get("load", 0.0),
            partitions=set(data.get("partitions", [])),
            metadata=data.get("metadata", {}),
        )


# Callback types
NodeJoinedCallback = Callable[[NodeMembership], Awaitable[None]]
NodeLeftCallback = Callable[[str], Awaitable[None]]
LeaderChangeCallback = Callable[[Optional[str], Optional[str]], Awaitable[None]]


class ClusterManager:
    """
    Manages cluster membership and state.
    
    Coordinates between:
    - Raft consensus for distributed state
    - Heartbeat service for health monitoring
    - Message broker for event distribution
    """
    
    def __init__(
        self,
        node_id: str,
        address: str,
        role: NodeRole,
        raft_node: RaftNode,
        heartbeat_service: HeartbeatService,
        message_broker: MessageBroker,
        min_healthy_nodes: int = 1,
    ):
        """
        Initialize cluster manager.
        
        Args:
            node_id: This node's ID
            address: This node's address
            role: This node's role
            raft_node: Raft consensus node
            heartbeat_service: Heartbeat monitoring service
            message_broker: Message broker for events
            min_healthy_nodes: Minimum healthy nodes for cluster health
        """
        self.node_id = node_id
        self.address = address
        self.role = role
        self.raft_node = raft_node
        self.heartbeat_service = heartbeat_service
        self.message_broker = message_broker
        self.min_healthy_nodes = min_healthy_nodes
        
        # Cluster state
        self._cluster_state = ClusterState.INITIALIZING
        self._nodes: Dict[str, NodeMembership] = {}
        self._leader_id: Optional[str] = None
        
        # Callbacks
        self._on_node_joined: List[NodeJoinedCallback] = []
        self._on_node_left: List[NodeLeftCallback] = []
        self._on_leader_change: List[LeaderChangeCallback] = []
        
        # Background tasks
        self._running = False
        self._state_check_task: Optional[asyncio.Task] = None
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Register self
        self._nodes[node_id] = NodeMembership(
            node_id=node_id,
            address=address,
            role=role,
            status=NodeStatus.HEALTHY,
        )
        
        # Register heartbeat callback
        self.heartbeat_service.on_status_change(self._on_node_status_change)
        self.heartbeat_service.on_heartbeat(self._on_heartbeat_received)
        
        logger.info(f"ClusterManager initialized for node {node_id}")
    
    @property
    def cluster_state(self) -> ClusterState:
        """Get current cluster state."""
        return self._cluster_state
    
    @property
    def leader_id(self) -> Optional[str]:
        """Get current leader ID."""
        return self._leader_id
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._leader_id == self.node_id
    
    def on_node_joined(self, callback: NodeJoinedCallback):
        """Register node joined callback."""
        self._on_node_joined.append(callback)
    
    def on_node_left(self, callback: NodeLeftCallback):
        """Register node left callback."""
        self._on_node_left.append(callback)
    
    def on_leader_change(self, callback: LeaderChangeCallback):
        """Register leader change callback."""
        self._on_leader_change.append(callback)
    
    async def start(self):
        """Start the cluster manager."""
        if self._running:
            return
        
        self._running = True
        
        # Start Raft node
        await self.raft_node.start()
        
        # Start state check task
        self._state_check_task = asyncio.create_task(self._state_check_loop())
        
        # Update cluster state
        await self._update_cluster_state()
        
        logger.info("ClusterManager started")
    
    async def stop(self):
        """Stop the cluster manager."""
        self._running = False
        
        if self._state_check_task and not self._state_check_task.done():
            self._state_check_task.cancel()
            try:
                await self._state_check_task
            except asyncio.CancelledError:
                pass
        
        await self.raft_node.stop()
        
        logger.info("ClusterManager stopped")
    
    async def join_cluster(
        self,
        seed_nodes: List[str],
    ) -> bool:
        """
        Join an existing cluster.
        
        Args:
            seed_nodes: Addresses of seed nodes to connect to
            
        Returns:
            True if joined successfully
        """
        for seed_address in seed_nodes:
            try:
                # Add seed node as peer
                # In real implementation, would discover node ID from seed
                seed_id = f"seed_{seed_address.replace(':', '_')}"
                await self.raft_node.add_peer(seed_id, seed_address)
                
                logger.info(f"Connected to seed node at {seed_address}")
                return True
                
            except Exception as e:
                logger.warning(f"Failed to connect to seed {seed_address}: {e}")
        
        return False
    
    async def add_node(
        self,
        node_id: str,
        address: str,
        role: NodeRole = NodeRole.SLAVE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a new node to the cluster.
        
        Args:
            node_id: Node's unique ID
            address: Node's network address
            role: Node's role
            metadata: Additional metadata
            
        Returns:
            True if node was added
        """
        if not self.is_leader:
            logger.warning("Cannot add node: not the leader")
            return False
        
        async with self._lock:
            if node_id in self._nodes:
                logger.info(f"Node {node_id} already in cluster")
                return True
            
            # Create membership
            membership = NodeMembership(
                node_id=node_id,
                address=address,
                role=role,
                status=NodeStatus.UNKNOWN,
                metadata=metadata or {},
            )
            
            # Submit to Raft
            command = Command(
                type=CommandType.ADD_NODE,
                data={
                    "node_id": node_id,
                    "node_info": {
                        "address": address,
                        "role": role.value,
                        "metadata": metadata or {},
                    },
                },
            )
            
            success = await self.raft_node.submit_command(command)
            
            if success:
                self._nodes[node_id] = membership
                await self.heartbeat_service.register_node(node_id, address)
                await self.raft_node.add_peer(node_id, address)
                
                # Notify callbacks
                for callback in self._on_node_joined:
                    try:
                        await callback(membership)
                    except Exception as e:
                        logger.error(f"Node joined callback error: {e}")
                
                # Broadcast event
                await self.message_broker.publish(Message(
                    type=MessageType.NODE_JOINED,
                    payload=membership.to_dict(),
                ))
                
                logger.info(f"Added node {node_id} to cluster")
            
            return success
    
    async def remove_node(self, node_id: str) -> bool:
        """
        Remove a node from the cluster.
        
        Args:
            node_id: Node's unique ID
            
        Returns:
            True if node was removed
        """
        if not self.is_leader:
            logger.warning("Cannot remove node: not the leader")
            return False
        
        async with self._lock:
            if node_id not in self._nodes:
                return True
            
            # Submit to Raft
            command = Command(
                type=CommandType.REMOVE_NODE,
                data={"node_id": node_id},
            )
            
            success = await self.raft_node.submit_command(command)
            
            if success:
                del self._nodes[node_id]
                await self.heartbeat_service.unregister_node(node_id)
                await self.raft_node.remove_peer(node_id)
                
                # Notify callbacks
                for callback in self._on_node_left:
                    try:
                        await callback(node_id)
                    except Exception as e:
                        logger.error(f"Node left callback error: {e}")
                
                # Broadcast event
                await self.message_broker.publish(Message(
                    type=MessageType.NODE_LEFT,
                    payload={"node_id": node_id},
                ))
                
                logger.info(f"Removed node {node_id} from cluster")
            
            return success
    
    async def update_node_stats(
        self,
        node_id: str,
        stats: Dict[str, Any],
    ):
        """
        Update node statistics.
        
        Args:
            node_id: Node's unique ID
            stats: Updated statistics
        """
        async with self._lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                node.last_seen = datetime.now()
                node.documents_count = stats.get("documents_count", node.documents_count)
                node.load = stats.get("load", node.load)
                
                if "partitions" in stats:
                    node.partitions = set(stats["partitions"])
    
    async def _on_heartbeat_received(self, heartbeat: NodeHeartbeat):
        """Handle received heartbeat."""
        await self.update_node_stats(
            heartbeat.node_id,
            {
                "documents_count": heartbeat.documents_count,
                "load": heartbeat.load,
            },
        )
    
    async def _on_node_status_change(
        self,
        node_id: str,
        old_status: NodeStatus,
        new_status: NodeStatus,
    ):
        """Handle node status change from heartbeat service."""
        async with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = new_status
        
        # Handle node failure
        if new_status == NodeStatus.DEAD:
            await self.message_broker.publish(Message(
                type=MessageType.NODE_FAILED,
                payload={
                    "node_id": node_id,
                    "old_status": old_status.value,
                },
            ))
        
        # Update cluster state
        await self._update_cluster_state()
    
    async def _state_check_loop(self):
        """Periodically check and update cluster state."""
        try:
            while self._running:
                # Check leader status
                new_leader = self.raft_node.leader_id
                if new_leader != self._leader_id:
                    old_leader = self._leader_id
                    self._leader_id = new_leader
                    
                    # Notify callbacks
                    for callback in self._on_leader_change:
                        try:
                            await callback(old_leader, new_leader)
                        except Exception as e:
                            logger.error(f"Leader change callback error: {e}")
                    
                    # Broadcast event
                    await self.message_broker.publish(Message(
                        type=MessageType.LEADER_ELECTED,
                        payload={
                            "old_leader": old_leader,
                            "new_leader": new_leader,
                        },
                    ))
                
                # Update cluster state
                await self._update_cluster_state()
                
                await asyncio.sleep(5.0)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"State check error: {e}")
    
    async def _update_cluster_state(self):
        """Update overall cluster state based on node health."""
        async with self._lock:
            healthy_count = sum(
                1 for node in self._nodes.values()
                if node.status == NodeStatus.HEALTHY
            )
            suspect_count = sum(
                1 for node in self._nodes.values()
                if node.status == NodeStatus.SUSPECT
            )
            dead_count = sum(
                1 for node in self._nodes.values()
                if node.status == NodeStatus.DEAD
            )
            total_count = len(self._nodes)
            
            if healthy_count >= self.min_healthy_nodes:
                if suspect_count == 0 and dead_count == 0:
                    self._cluster_state = ClusterState.HEALTHY
                elif dead_count > 0:
                    self._cluster_state = ClusterState.RECOVERING
                else:
                    self._cluster_state = ClusterState.DEGRADED
            elif healthy_count > 0:
                self._cluster_state = ClusterState.DEGRADED
            else:
                self._cluster_state = ClusterState.CRITICAL
    
    def get_node(self, node_id: str) -> Optional[NodeMembership]:
        """Get node membership info."""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[NodeMembership]:
        """Get all nodes in the cluster."""
        return list(self._nodes.values())
    
    def get_healthy_nodes(self) -> List[NodeMembership]:
        """Get all healthy nodes."""
        return [
            node for node in self._nodes.values()
            if node.status == NodeStatus.HEALTHY
        ]
    
    def get_nodes_by_role(self, role: NodeRole) -> List[NodeMembership]:
        """Get nodes by role."""
        return [
            node for node in self._nodes.values()
            if node.role == role
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get cluster manager status."""
        return {
            "node_id": self.node_id,
            "role": self.role.value,
            "cluster_state": self._cluster_state.value,
            "leader_id": self._leader_id,
            "is_leader": self.is_leader,
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(self.get_healthy_nodes()),
            "nodes": {
                node_id: node.to_dict()
                for node_id, node in self._nodes.items()
            },
        }
