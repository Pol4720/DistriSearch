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

from ..consensus import RaftNode, Command, CommandType
from ..communication import (
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
    
    @property
    def leader_address(self) -> Optional[str]:
        """Get current leader's address for forwarding requests."""
        if self._leader_id is None:
            return None
        if self._leader_id in self._nodes:
            leader_node = self._nodes[self._leader_id]
            return leader_node.address
        return None
    
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
        
        # Start Raft node (if available)
        if self.raft_node is not None:
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
        
        if self.raft_node is not None:
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
                if self.raft_node is not None:
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
            
            # In single-node or leader-only mode, we can skip Raft consensus
            # for adding slaves since they don't participate in Raft
            is_single_node = len(self._nodes) <= 1
            success = True
            
            if not is_single_node and role != NodeRole.SLAVE:
                # Only use Raft for non-slave nodes in multi-node setup
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
                
                try:
                    if self.raft_node is not None:
                        success = await self.raft_node.submit_command(command)
                    else:
                        success = True  # No Raft, proceed anyway
                except Exception as e:
                    logger.warning(f"Raft submit failed, proceeding anyway: {e}")
                    success = True  # Proceed in degraded mode
            
            if success:
                self._nodes[node_id] = membership
                await self.heartbeat_service.register_node(node_id, address)
                if self.raft_node is not None:
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
            
            # Submit to Raft (if available)
            command = Command(
                type=CommandType.REMOVE_NODE,
                data={"node_id": node_id},
            )
            
            if self.raft_node is not None:
                success = await self.raft_node.submit_command(command)
            else:
                success = True  # No Raft, proceed anyway
            
            if success:
                del self._nodes[node_id]
                await self.heartbeat_service.unregister_node(node_id)
                if self.raft_node is not None:
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
                # Check leader status (if Raft is available)
                if self.raft_node is not None:
                    new_leader = self.raft_node.leader_id
                else:
                    new_leader = self._leader_id  # Keep current leader (set by Bully)
                
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
                
                # Periodically check health of all nodes (if we are leader)
                if self.is_leader:
                    await self._check_all_nodes_health()
                
                # Update cluster state
                await self._update_cluster_state()
                
                await asyncio.sleep(5.0)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"State check error: {e}")
    
    async def _check_all_nodes_health(self):
        """Check health of all registered nodes."""
        for node_id, node in list(self._nodes.items()):
            if node_id == self.node_id:
                continue  # Skip self
            
            # Build address with port
            address = node.address
            port = getattr(node, 'port', 8000) or 8000
            if ':' not in address:
                address = f"{address}:{port}"
            
            is_healthy = await self._check_peer_health(address)
            old_status = node.status
            new_status = NodeStatus.HEALTHY if is_healthy else NodeStatus.DEAD
            
            if old_status != new_status:
                node.status = new_status
                logger.info(f"Node {node_id} status changed: {old_status.value} -> {new_status.value}")
    
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
    
    async def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """Get all cluster nodes as dicts for API use."""
        return [
            {
                "node_id": node.node_id,
                "address": node.address.split(":")[0] if ":" in node.address else node.address,
                "port": int(node.address.split(":")[1]) if ":" in node.address else 8000,
                "status": node.status.value,
                "role": node.role.value,
            }
            for node in self._nodes.values()
        ]
    
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

    # =========================================================================
    # Additional methods required by API endpoints
    # =========================================================================
    
    @property
    def is_initialized(self) -> bool:
        """Check if cluster manager is fully initialized."""
        return self._running
    
    @property
    def is_registered(self) -> bool:
        """Check if this node is registered in the cluster."""
        return self.node_id in self._nodes
    
    @property
    def is_master(self) -> bool:
        """Check if this node is the master."""
        return self.role == NodeRole.MASTER
    
    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get comprehensive cluster status for API."""
        return {
            "cluster_id": getattr(self, 'cluster_id', 'default'),
            "cluster_state": self._cluster_state.value,
            "leader_id": self._leader_id,
            "is_leader": self.is_leader,
            "node_id": self.node_id,
            "node_role": self.role.value,
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(self.get_healthy_nodes()),
            "nodes": [node.to_dict() for node in self._nodes.values()],
        }
    
    async def get_cluster_stats(self) -> Dict[str, Any]:
        """Get cluster statistics."""
        healthy_nodes = self.get_healthy_nodes()
        total_documents = sum(n.documents_count for n in self._nodes.values())
        total_partitions = sum(len(n.partitions) for n in self._nodes.values())
        avg_load = sum(n.load for n in self._nodes.values()) / max(len(self._nodes), 1)
        
        return {
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(healthy_nodes),
            "total_documents": total_documents,
            "total_partitions": total_partitions,
            "average_load": avg_load,
            "cluster_state": self._cluster_state.value,
            "replication_factor": getattr(self, 'replication_factor', 2),
        }
    
    async def get_master_node_id(self) -> Optional[str]:
        """Get the master node ID."""
        for node in self._nodes.values():
            if node.role == NodeRole.MASTER:
                return node.node_id
        return self._leader_id
    
    async def get_partitions(self, node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get partitions, optionally filtered by node."""
        partitions = []
        for node in self._nodes.values():
            if node_id and node.node_id != node_id:
                continue
            for partition_id in node.partitions:
                partitions.append({
                    "partition_id": partition_id,
                    "node_id": node.node_id,
                    "node_address": node.address,
                })
        return partitions
    
    async def get_partitions_for_query(self, query_vector: Any, top_k: int = 10) -> List[str]:
        """Get partitions relevant for a search query."""
        # Return all partitions from healthy nodes for now
        # In production, use VP-tree to find closest partitions
        partitions = []
        for node in self.get_healthy_nodes():
            partitions.extend(node.partitions)
        return partitions[:top_k] if partitions else ["default"]
    
    async def assign_partition(self, vectors: Any) -> str:
        """Assign a partition for new document vectors."""
        import hashlib
        import json
        
        # Simple hash-based partition assignment
        # In production, use VP-tree for semantic partitioning
        vector_str = json.dumps(vectors, sort_keys=True, default=str)
        hash_value = hashlib.md5(vector_str.encode()).hexdigest()[:8]
        return f"partition-{hash_value}"
    
    async def get_node_for_partition(self, partition_id: str) -> str:
        """Get the node responsible for a partition."""
        # Find node that has this partition
        for node in self.get_healthy_nodes():
            if partition_id in node.partitions:
                return node.node_id
        
        # If no node has it, assign to least loaded healthy node
        healthy_nodes = self.get_healthy_nodes()
        if healthy_nodes:
            least_loaded = min(healthy_nodes, key=lambda n: n.load)
            least_loaded.partitions.add(partition_id)
            return least_loaded.node_id
        
        # Fallback to self
        return self.node_id
    
    async def replicate_document(self, doc_id: str, primary_node_id: str, document_data: dict = None):
        """
        Initiate document replication to other nodes via HTTP.
        
        Args:
            doc_id: Document ID to replicate
            primary_node_id: Node ID where the primary copy is stored
            document_data: Full document data to replicate (if None, will fetch from primary)
        """
        import aiohttp
        import base64
        
        replication_factor = getattr(self, 'replication_factor', 2)
        healthy_nodes = [
            n for n in self.get_healthy_nodes()
            if n.node_id != primary_node_id
        ]
        
        # Select replica nodes
        replica_count = min(replication_factor - 1, len(healthy_nodes))
        if replica_count <= 0:
            logger.debug(f"No nodes available for replicating {doc_id}")
            return {"replicated_to": [], "failed": []}
        
        # Sort by load to prefer less loaded nodes
        replica_nodes = sorted(healthy_nodes, key=lambda n: n.load)[:replica_count]
        
        replicated_to = []
        failed = []
        
        # Check if document has a file and read it
        file_content_base64 = None
        if document_data:
            metadata = document_data.get("metadata", {})
            file_path = metadata.get("file_path")
            
            if file_path:
                try:
                    from ..storage.file_handler import FileHandler
                    file_handler = FileHandler()
                    file_content = await file_handler.get_file(file_path)
                    if file_content:
                        file_content_base64 = base64.b64encode(file_content).decode('utf-8')
                        logger.info(f"Including file content ({len(file_content)} bytes) in replication for {doc_id}")
                except Exception as e:
                    logger.warning(f"Could not read file for replication: {e}")
        
        for node in replica_nodes:
            try:
                # Get port from node or use default
                port = getattr(node, 'port', 8000) or 8000
                address = node.address
                if ':' not in address:
                    address = f"{address}:{port}"
                
                url = f"http://{address}/api/v1/internal/document/replicate"
                
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "document_id": doc_id,
                        "source_node_id": primary_node_id,
                        "document_data": document_data or {}
                    }
                    
                    # Include file content if available
                    if file_content_base64:
                        payload["file_content_base64"] = file_content_base64
                    
                    async with session.post(
                        url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)  # Longer timeout for large files
                    ) as resp:
                        result = await resp.json()
                        if resp.status == 200 and result.get("status") in ["replicated", "already_exists"]:
                            replicated_to.append(node.node_id)
                            file_info = " (with file)" if file_content_base64 and result.get("file_replicated") else ""
                            logger.info(f"Replicated {doc_id} to {node.node_id}{file_info}")
                        else:
                            failed.append({"node": node.node_id, "error": result.get("message", "Unknown error")})
                            logger.warning(f"Failed to replicate {doc_id} to {node.node_id}: {result}")
                            
            except Exception as e:
                failed.append({"node": node.node_id, "error": str(e)})
                logger.error(f"Failed to replicate {doc_id} to {node.node_id}: {e}")
        
        return {"replicated_to": replicated_to, "failed": failed}
    
    async def delete_document_replicas(self, doc_id: str, retries: int = 3, backoff: float = 1.0, require_quorum: bool = True):
        """
        Delete document replicas from all other nodes via HTTP.
        
        This implements eventual consistency - we try to delete from all nodes
        but don't fail if some nodes are unreachable.
        
        Args:
            doc_id: Document ID to delete
        """
        import aiohttp
        import asyncio
        
        deleted_from = []
        failed = []

        # Get all healthy nodes except ourselves
        other_nodes = [
            n for n in self.get_healthy_nodes()
            if n.node_id != self.node_id
        ]

        if not other_nodes:
            logger.debug(f"No other nodes to delete replica {doc_id} from")
            return {"deleted_from": [], "failed": [], "success": True}

        # Determine required successes (replication_factor - 1)
        replication_factor = getattr(self, 'replication_factor', 2)
        required_successes = max(0, replication_factor - 1)

        # Helper to attempt deletion on a set of nodes
        async def attempt_delete(nodes):
            results = []
            async def delete_from_node(node):
                try:
                    port = getattr(node, 'port', 8000) or 8000
                    address = node.address
                    if ':' not in address:
                        address = f"{address}:{port}"

                    url = f"http://{address}/api/v1/internal/document/delete"

                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            url,
                            json={
                                "document_id": doc_id,
                                "propagate": False  # Don't propagate further
                            },
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            try:
                                result = await resp.json()
                            except Exception:
                                result = {}
                            if resp.status == 200 and result.get("status") in ["deleted", "not_found"]:
                                return (True, node.node_id, None)
                            else:
                                return (False, node.node_id, result.get("message", "Unknown error"))

                except Exception as e:
                    return (False, node.node_id, str(e))

            tasks = [delete_from_node(n) for n in nodes]
            res = await asyncio.gather(*tasks, return_exceptions=True)
            for r in res:
                if isinstance(r, Exception):
                    logger.error(f"Exception during replica deletion attempt: {r}")
                else:
                    results.append(r)
            return results

        # Start attempts with retries and exponential backoff
        remaining_nodes = other_nodes.copy()
        attempt = 0
        success_node_ids: Set[str] = set()

        while attempt <= retries and remaining_nodes:
            attempt += 1
            logger.debug(f"Attempt {attempt} to delete {doc_id} from {len(remaining_nodes)} nodes")
            results = await attempt_delete(remaining_nodes)

            # Reset remaining list and collect failures
            new_remaining = []
            for ok, node_id, err in results:
                if ok:
                    success_node_ids.add(node_id)
                    logger.info(f"Deleted replica {doc_id} from {node_id}")
                else:
                    new_remaining.append(node_id)
                    failed.append({"node": node_id, "error": err})
                    logger.warning(f"Failed to delete replica {doc_id} from {node_id}: {err}")

            # If we've reached required successes, break
            if len(success_node_ids) >= required_successes:
                break

            # Prepare for next retry only on nodes that failed
            remaining_nodes = [n for n in remaining_nodes if n.node_id in new_remaining]

            if remaining_nodes:
                await asyncio.sleep(backoff * attempt)

        deleted_from = list(success_node_ids)

        # Determine overall success based on quorum requirement
        if require_quorum:
            success = len(deleted_from) >= required_successes
        else:
            success = True

        return {"deleted_from": deleted_from, "failed": failed, "success": success}
    
    async def register_node(
        self,
        node_id: str,
        address: str,
        port: int = 8000,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register a new node to the cluster.
        
        This is a wrapper around add_node for API compatibility.
        
        Args:
            node_id: Node's unique ID
            address: Node's network address (hostname or IP)
            port: Node's API port
            capabilities: Node capabilities and metadata
            
        Returns:
            Registration result with cluster info
        """
        full_address = f"{address}:{port}"
        metadata = {"capabilities": capabilities or {}, "port": port}
        
        success = await self.add_node(
            node_id=node_id,
            address=full_address,
            role=NodeRole.SLAVE,
            metadata=metadata,
        )
        
        if success:
            return {
                "success": True,
                "cluster_id": getattr(self, 'cluster_id', 'distrisearch-cluster'),
                "master_node_id": await self.get_master_node_id(),
                "assigned_partitions": [],
            }
        else:
            raise Exception("Failed to add node to cluster")
    
    async def shutdown(self):
        """Shutdown the cluster manager gracefully."""
        logger.info("Shutting down cluster manager...")
        await self.stop()
        logger.info("Cluster manager shutdown complete")
    
    async def handle_leader_elected(self, leader_id: str, peers: Optional[Dict[str, str]] = None):
        """
        Handle leader election from Bully algorithm.
        
        Args:
            leader_id: The ID of the newly elected leader
            peers: Dictionary of peer_id -> address (for registering nodes)
        """
        async with self._lock:
            old_leader = self._leader_id
            self._leader_id = leader_id
            
            # Update role
            if leader_id == self.node_id:
                self._role = NodeRole.MASTER
                logger.info(f"This node ({self.node_id}) is now the MASTER")
                
                # Register ourselves first
                if self.node_id not in self._nodes:
                    membership = NodeMembership(
                        node_id=self.node_id,
                        address=self._address,
                        role=NodeRole.MASTER,
                        status=NodeStatus.HEALTHY,
                        metadata={},
                    )
                    self._nodes[self.node_id] = membership
                else:
                    self._nodes[self.node_id].role = NodeRole.MASTER
                    self._nodes[self.node_id].status = NodeStatus.HEALTHY
                
                # Register all peers as nodes - check their actual health
                if peers:
                    for peer_id, peer_address in peers.items():
                        # Check if peer is actually reachable
                        is_healthy = await self._check_peer_health(peer_address)
                        peer_status = NodeStatus.HEALTHY if is_healthy else NodeStatus.DEAD
                        
                        if peer_id not in self._nodes:
                            membership = NodeMembership(
                                node_id=peer_id,
                                address=peer_address.split(":")[0],  # Remove port
                                role=NodeRole.SLAVE,
                                status=peer_status,
                                metadata={},
                            )
                            self._nodes[peer_id] = membership
                            logger.info(f"Registered peer {peer_id} as {peer_status.value}")
                        else:
                            self._nodes[peer_id].status = peer_status
            else:
                self._role = NodeRole.SLAVE
                logger.info(f"Node {leader_id} is now the MASTER, we are SLAVE")
            
            # Notify callbacks
            if old_leader != leader_id:
                for callback in self._on_leader_change:
                    try:
                        await callback(old_leader, leader_id)
                    except Exception as e:
                        logger.error(f"Leader change callback error: {e}")
                
                # Broadcast event
                await self.message_broker.publish(Message(
                    type=MessageType.LEADER_ELECTED,
                    payload={
                        "old_leader": old_leader,
                        "new_leader": leader_id,
                    },
                ))
    
    async def _check_peer_health(self, peer_address: str) -> bool:
        """Check if a peer is reachable and healthy."""
        import aiohttp
        try:
            url = f"http://{peer_address}/api/v1/health/live"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    return resp.status == 200
        except Exception:
            return False
