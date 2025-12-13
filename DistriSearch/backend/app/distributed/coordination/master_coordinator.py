"""
Master Coordinator for DistriSearch.

Coordinates all master node operations including:
- Cluster management
- Document partitioning
- Rebalancing orchestration
- Search coordination
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from datetime import datetime

from .core.partitioning import PartitionManager, VPTree
from .core.rebalancing import ActiveRebalancer
from .core.replication import AffinityReplicator
from .core.recovery import RecoveryService
from .core.search import SearchEngine

from ..consensus import RaftNode, Command, CommandType
from .communication import (
    MessageBroker,
    Message,
    MessageType,
    WebSocketManager,
    NodeClientPool,
)
from .coordination.cluster_manager import (
    ClusterManager,
    NodeMembership,
    NodeRole,
    ClusterState,
)

logger = logging.getLogger(__name__)


@dataclass
class MasterConfig:
    """Configuration for master coordinator."""
    
    # Rebalancing
    rebalance_interval: float = 300.0  # 5 minutes
    rebalance_threshold: float = 0.2   # 20% load imbalance
    enable_auto_rebalance: bool = True
    
    # Replication
    replication_factor: int = 2
    enable_affinity_replication: bool = True
    
    # Partitioning
    initial_partitions: int = 16
    max_documents_per_partition: int = 10000
    
    # Search
    search_timeout: float = 30.0
    max_results_per_node: int = 100


class MasterCoordinator:
    """
    Coordinator for master node operations.
    
    Orchestrates:
    - VP-Tree based document partitioning
    - Active rebalancing across nodes
    - Semantic affinity replication
    - Distributed search coordination
    - Failure recovery
    """
    
    def __init__(
        self,
        node_id: str,
        cluster_manager: ClusterManager,
        raft_node: RaftNode,
        message_broker: MessageBroker,
        ws_manager: WebSocketManager,
        node_client_pool: NodeClientPool,
        config: Optional[MasterConfig] = None,
    ):
        """
        Initialize master coordinator.
        
        Args:
            node_id: This master's ID
            cluster_manager: Cluster membership manager
            raft_node: Raft consensus node
            message_broker: Message broker for events
            ws_manager: WebSocket manager for dashboard
            node_client_pool: Pool of REST clients to nodes
            config: Master configuration
        """
        self.node_id = node_id
        self.cluster_manager = cluster_manager
        self.raft_node = raft_node
        self.message_broker = message_broker
        self.ws_manager = ws_manager
        self.node_client_pool = node_client_pool
        self.config = config or MasterConfig()
        
        # Core components (initialized on start)
        self.partition_manager: Optional[PartitionManager] = None
        self.rebalancer: Optional[ActiveRebalancer] = None
        self.replicator: Optional[AffinityReplicator] = None
        self.recovery_service: Optional[RecoveryService] = None
        self.search_engine: Optional[SearchEngine] = None
        
        # State
        self._running = False
        self._is_active_master = False
        
        # Background tasks
        self._rebalance_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._documents_indexed = 0
        self._searches_completed = 0
        self._rebalances_completed = 0
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Register callbacks
        self.cluster_manager.on_node_joined(self._on_node_joined)
        self.cluster_manager.on_node_left(self._on_node_left)
        self.cluster_manager.on_leader_change(self._on_leader_change)
        
        # Subscribe to events
        self._setup_message_handlers()
        
        logger.info(f"MasterCoordinator initialized for node {node_id}")
    
    def _setup_message_handlers(self):
        """Set up message broker handlers."""
        self.message_broker.subscribe(
            MessageType.NODE_FAILED.value,
            self._handle_node_failed,
        )
        self.message_broker.subscribe(
            MessageType.REBALANCE_STARTED.value,
            self._handle_rebalance_event,
        )
    
    async def start(self):
        """Start the master coordinator."""
        if self._running:
            return
        
        self._running = True
        
        # Initialize components
        await self._initialize_components()
        
        # Start background tasks
        if self.config.enable_auto_rebalance:
            self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        # Check if we should be active master
        if self.cluster_manager.is_leader:
            await self._become_active_master()
        
        logger.info("MasterCoordinator started")
    
    async def stop(self):
        """Stop the master coordinator."""
        self._running = False
        
        if self._rebalance_task and not self._rebalance_task.done():
            self._rebalance_task.cancel()
            try:
                await self._rebalance_task
            except asyncio.CancelledError:
                pass
        
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MasterCoordinator stopped")
    
    async def _initialize_components(self):
        """Initialize core components."""
        # These would be properly initialized with dependencies
        # For now, just setting up placeholders
        logger.info("Initializing master coordinator components")
    
    async def _become_active_master(self):
        """Transition to active master role."""
        async with self._lock:
            if self._is_active_master:
                return
            
            self._is_active_master = True
            logger.info(f"Node {self.node_id} became active master")
            
            # Broadcast status
            await self.message_broker.publish(Message(
                type=MessageType.LEADER_ELECTED,
                payload={
                    "new_leader": self.node_id,
                    "timestamp": datetime.now().isoformat(),
                },
            ))
    
    async def _become_standby_master(self):
        """Transition to standby master role."""
        async with self._lock:
            if not self._is_active_master:
                return
            
            self._is_active_master = False
            logger.info(f"Node {self.node_id} became standby master")
    
    # Cluster event handlers
    
    async def _on_node_joined(self, node: NodeMembership):
        """Handle node joining the cluster."""
        if not self._is_active_master:
            return
        
        logger.info(f"Handling node join: {node.node_id}")
        
        # Assign initial partitions to new node
        # This would trigger rebalancing if needed
        await self._maybe_trigger_rebalance()
    
    async def _on_node_left(self, node_id: str):
        """Handle node leaving the cluster."""
        if not self._is_active_master:
            return
        
        logger.info(f"Handling node leave: {node_id}")
        
        # Trigger recovery for documents on failed node
        # This would re-replicate documents and rebalance
        await self._handle_node_failure(node_id)
    
    async def _on_leader_change(
        self,
        old_leader: Optional[str],
        new_leader: Optional[str],
    ):
        """Handle leader change in the cluster."""
        if new_leader == self.node_id:
            await self._become_active_master()
        else:
            await self._become_standby_master()
    
    # Message handlers
    
    async def _handle_node_failed(self, message: Message):
        """Handle node failure message."""
        if not self._is_active_master:
            return
        
        node_id = message.payload.get("node_id")
        if node_id:
            await self._handle_node_failure(node_id)
    
    async def _handle_rebalance_event(self, message: Message):
        """Handle rebalance event message."""
        # Forward to dashboard
        from .communication import WebSocketEventType
        await self.ws_manager.broadcast_to_subscribers(
            WebSocketEventType.REBALANCE_PROGRESS,
            message.payload,
        )
    
    # Core operations
    
    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Index a new document.
        
        Args:
            doc_id: Document ID
            content: Document content
            metadata: Document metadata
            
        Returns:
            True if indexed successfully
        """
        if not self._is_active_master:
            logger.warning("Cannot index: not active master")
            return False
        
        try:
            # Determine target node using partitioning
            # For now, use round-robin among healthy nodes
            healthy_nodes = self.cluster_manager.get_healthy_nodes()
            if not healthy_nodes:
                logger.error("No healthy nodes available for indexing")
                return False
            
            # Select node (simplified - real implementation uses VP-Tree)
            target_node = min(healthy_nodes, key=lambda n: n.documents_count)
            
            # Send document to target node
            client = await self.node_client_pool.get_client(target_node.address)
            response = await client.index_document(doc_id, content, metadata)
            
            if response.success:
                # Record in Raft state
                command = Command(
                    type=CommandType.ADD_DOCUMENT,
                    data={
                        "doc_id": doc_id,
                        "metadata": {
                            "primary_node": target_node.node_id,
                            **(metadata or {}),
                        },
                    },
                )
                await self.raft_node.submit_command(command)
                
                # Create replicas
                await self._create_replicas(
                    doc_id,
                    target_node.node_id,
                    content,
                )
                
                self._documents_indexed += 1
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error indexing document {doc_id}: {e}")
            return False
    
    async def _create_replicas(
        self,
        doc_id: str,
        primary_node_id: str,
        content: str,
    ):
        """Create replicas for a document."""
        healthy_nodes = self.cluster_manager.get_healthy_nodes()
        
        # Select replica nodes (excluding primary)
        replica_candidates = [
            n for n in healthy_nodes
            if n.node_id != primary_node_id
        ]
        
        # Select nodes with lowest load
        replica_nodes = sorted(
            replica_candidates,
            key=lambda n: n.load,
        )[:self.config.replication_factor - 1]
        
        for node in replica_nodes:
            try:
                client = await self.node_client_pool.get_client(node.address)
                response = await client.index_document(
                    doc_id,
                    content,
                    {"is_replica": True, "primary_node": primary_node_id},
                )
                
                if response.success:
                    # Record replica in Raft
                    command = Command(
                        type=CommandType.ADD_REPLICA,
                        data={
                            "doc_id": doc_id,
                            "node_id": node.node_id,
                        },
                    )
                    await self.raft_node.submit_command(command)
                    
            except Exception as e:
                logger.warning(
                    f"Failed to create replica on {node.node_id}: {e}"
                )
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute distributed search.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Search filters
            
        Returns:
            List of search results
        """
        try:
            # Get healthy nodes to search
            healthy_nodes = self.cluster_manager.get_healthy_nodes()
            
            if not healthy_nodes:
                logger.error("No healthy nodes available for search")
                return []
            
            # Search all nodes in parallel
            tasks = []
            for node in healthy_nodes:
                client = await self.node_client_pool.get_client(node.address)
                task = client.search(
                    query,
                    limit=self.config.max_results_per_node,
                    filters=filters,
                )
                tasks.append((node.node_id, task))
            
            # Gather results with timeout
            results = []
            for node_id, task in tasks:
                try:
                    response = await asyncio.wait_for(
                        task,
                        timeout=self.config.search_timeout,
                    )
                    if response.success and response.data:
                        node_results = response.data.get("results", [])
                        results.extend(node_results)
                except asyncio.TimeoutError:
                    logger.warning(f"Search timeout on node {node_id}")
                except Exception as e:
                    logger.warning(f"Search error on node {node_id}: {e}")
            
            # Sort by score and limit
            results.sort(key=lambda r: r.get("score", 0), reverse=True)
            results = results[:limit]
            
            self._searches_completed += 1
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def _handle_node_failure(self, node_id: str):
        """Handle a node failure - trigger recovery."""
        logger.info(f"Handling failure of node {node_id}")
        
        # Get documents that were on failed node
        # (from Raft state machine)
        cluster_state = self.raft_node.get_cluster_state()
        documents = cluster_state.get("documents", {})
        
        affected_docs = [
            doc_id for doc_id, info in documents.items()
            if info.get("primary_node") == node_id
        ]
        
        # Re-replicate affected documents
        for doc_id in affected_docs:
            # Promote replica to primary
            replicas = self.raft_node.state_machine.get_document_replicas(doc_id)
            
            if replicas:
                new_primary = replicas[0]
                
                # Update state
                command = Command(
                    type=CommandType.UPDATE_DOCUMENT,
                    data={
                        "doc_id": doc_id,
                        "updates": {"primary_node": new_primary},
                    },
                )
                await self.raft_node.submit_command(command)
                
                logger.info(
                    f"Promoted replica on {new_primary} to primary "
                    f"for document {doc_id}"
                )
    
    # Rebalancing
    
    async def _rebalance_loop(self):
        """Periodically check and trigger rebalancing."""
        try:
            while self._running:
                await asyncio.sleep(self.config.rebalance_interval)
                
                if self._is_active_master:
                    await self._maybe_trigger_rebalance()
                    
        except asyncio.CancelledError:
            pass
    
    async def _maybe_trigger_rebalance(self):
        """Check if rebalancing is needed and trigger it."""
        healthy_nodes = self.cluster_manager.get_healthy_nodes()
        
        if len(healthy_nodes) < 2:
            return
        
        # Calculate load variance
        loads = [n.load for n in healthy_nodes]
        avg_load = sum(loads) / len(loads)
        max_deviation = max(abs(l - avg_load) for l in loads)
        
        if max_deviation > self.config.rebalance_threshold:
            logger.info(
                f"Triggering rebalance: max deviation {max_deviation:.2%}"
            )
            await self._trigger_rebalance()
    
    async def _trigger_rebalance(self):
        """Trigger cluster rebalancing."""
        # Broadcast rebalance start
        await self.message_broker.publish(Message(
            type=MessageType.REBALANCE_STARTED,
            payload={
                "timestamp": datetime.now().isoformat(),
                "initiated_by": self.node_id,
            },
        ))
        
        # Actual rebalancing would be done by ActiveRebalancer
        # This is simplified for now
        
        self._rebalances_completed += 1
        
        # Broadcast rebalance complete
        await self.message_broker.publish(Message(
            type=MessageType.REBALANCE_COMPLETED,
            payload={
                "timestamp": datetime.now().isoformat(),
            },
        ))
    
    # Health checks
    
    async def _health_check_loop(self):
        """Periodically perform health checks."""
        try:
            while self._running:
                await asyncio.sleep(30.0)
                
                if self._is_active_master:
                    # Broadcast cluster state to dashboard
                    from .communication import WebSocketEventType
                    await self.ws_manager.broadcast_to_subscribers(
                        WebSocketEventType.CLUSTER_STATE,
                        self.get_status(),
                    )
                    
        except asyncio.CancelledError:
            pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status."""
        return {
            "node_id": self.node_id,
            "is_active_master": self._is_active_master,
            "cluster_state": self.cluster_manager.cluster_state.value,
            "total_nodes": len(self.cluster_manager.get_all_nodes()),
            "healthy_nodes": len(self.cluster_manager.get_healthy_nodes()),
            "documents_indexed": self._documents_indexed,
            "searches_completed": self._searches_completed,
            "rebalances_completed": self._rebalances_completed,
            "running": self._running,
        }
