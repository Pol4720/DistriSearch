# -*- coding: utf-8 -*-
"""
Affinity Replicator - Handles semantic affinity-based replication.

Per architecture spec:
- Replication factor 2 (configurable)
- "similarity graph, place replicas on nodes with neighboring documents"
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .similarity_graph import SimilarityGraph, DocumentNode
from .replica_tracker import ReplicaTracker, ReplicaInfo, ReplicaStatus, DocumentReplicas

logger = logging.getLogger(__name__)


class ReplicationPriority(Enum):
    """Priority levels for replication tasks."""
    CRITICAL = 4  # Primary lost, no replicas
    HIGH = 3      # Under-replicated
    NORMAL = 2    # New document
    LOW = 1       # Background optimization


@dataclass
class ReplicationConfig:
    """Configuration for replication."""
    replication_factor: int = 2
    max_concurrent_replications: int = 5
    replication_timeout_sec: float = 60.0
    retry_count: int = 3
    retry_delay_sec: float = 5.0
    sync_batch_size: int = 10
    check_interval_sec: float = 30.0


@dataclass
class ReplicationTask:
    """A pending replication task."""
    task_id: str
    document_id: str
    source_node: str
    target_node: str
    priority: ReplicationPriority
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    error: Optional[str] = None
    retry_count: int = 0


class AffinityReplicator:
    """
    Manages document replication with semantic affinity placement.
    
    Features:
    - Automatic replica placement based on document similarity
    - Background replication monitoring
    - Re-replication on node failure
    - Replica synchronization
    """
    
    def __init__(
        self,
        config: Optional[ReplicationConfig] = None,
        replicate_func: Optional[Callable[[str, str, str], Awaitable[bool]]] = None,
        get_document_vectors: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None
    ):
        """
        Initialize affinity replicator.
        
        Args:
            config: Replication configuration
            replicate_func: Function to replicate document
                           Signature: (doc_id, source_node, target_node) -> success
            get_document_vectors: Function to get document vectors
                                  Signature: (doc_id) -> vectors dict
        """
        self.config = config or ReplicationConfig()
        self._replicate_func = replicate_func
        self._get_vectors_func = get_document_vectors
        
        # Components
        self.similarity_graph = SimilarityGraph()
        self.replica_tracker = ReplicaTracker(
            default_replication_factor=self.config.replication_factor
        )
        
        # Task queue
        self._pending_tasks: Dict[str, ReplicationTask] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        
        # State
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._cluster_nodes: List[str] = []
        
        # Stats
        self._total_replications = 0
        self._failed_replications = 0
    
    def set_replicate_function(
        self,
        func: Callable[[str, str, str], Awaitable[bool]]
    ) -> None:
        """Set the replication function."""
        self._replicate_func = func
    
    def set_vector_function(
        self,
        func: Callable[[str], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Set the function to retrieve document vectors."""
        self._get_vectors_func = func
    
    def register_cluster_node(self, node_id: str) -> None:
        """Register a cluster node as available for replicas."""
        if node_id not in self._cluster_nodes:
            self._cluster_nodes.append(node_id)
            logger.info(f"Registered cluster node: {node_id}")
    
    def unregister_cluster_node(self, node_id: str) -> List[str]:
        """
        Unregister a cluster node (e.g., on failure).
        
        Args:
            node_id: Node to remove
            
        Returns:
            Documents needing re-replication
        """
        if node_id in self._cluster_nodes:
            self._cluster_nodes.remove(node_id)
        
        # Mark replicas as failed
        affected = self.replica_tracker.mark_node_failed(node_id)
        
        # Queue re-replication for affected documents
        for doc_id in affected:
            self._queue_replication(
                doc_id,
                priority=ReplicationPriority.HIGH
            )
        
        return affected
    
    async def register_document(
        self,
        document_id: str,
        primary_node: str,
        document_vectors: Optional[Dict[str, Any]] = None,
        size_bytes: int = 0,
        checksum: Optional[str] = None
    ) -> DocumentReplicas:
        """
        Register a new document and initiate replication.
        
        Args:
            document_id: Document identifier
            primary_node: Node storing the primary
            document_vectors: Document vectors for affinity calculation
            size_bytes: Document size
            checksum: Document checksum
            
        Returns:
            Document replicas info
        """
        # Select replica nodes using affinity
        replica_nodes = await self._select_replica_nodes(
            document_id,
            primary_node,
            document_vectors
        )
        
        # Register in tracker
        doc_replicas = self.replica_tracker.register_document(
            document_id=document_id,
            primary_node=primary_node,
            replica_nodes=replica_nodes,
            replication_factor=self.config.replication_factor,
            size_bytes=size_bytes,
            checksum=checksum
        )
        
        # Add to similarity graph
        self.similarity_graph.add_document(
            document_id=document_id,
            primary_node=primary_node,
            document_vectors=document_vectors,
            replica_nodes=replica_nodes
        )
        
        # Queue replication tasks
        for replica_node in replica_nodes:
            task = self._create_task(
                document_id=document_id,
                source_node=primary_node,
                target_node=replica_node,
                priority=ReplicationPriority.NORMAL
            )
            self._pending_tasks[task.task_id] = task
        
        logger.info(
            f"Registered document {document_id} with "
            f"{len(replica_nodes)} pending replicas"
        )
        
        return doc_replicas
    
    async def _select_replica_nodes(
        self,
        document_id: str,
        primary_node: str,
        document_vectors: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Select nodes for replicas using semantic affinity.
        
        Args:
            document_id: Document to replicate
            primary_node: Primary node (excluded)
            document_vectors: Document vectors
            
        Returns:
            List of selected node IDs
        """
        num_replicas = self.config.replication_factor - 1
        
        if num_replicas <= 0:
            return []
        
        available_nodes = [n for n in self._cluster_nodes if n != primary_node]
        
        if not available_nodes:
            logger.warning("No available nodes for replicas")
            return []
        
        # If we have vectors and existing documents, use affinity
        if document_vectors and len(self.similarity_graph._nodes) > 0:
            # Find nodes with similar documents
            affinity_scores = self.similarity_graph.find_best_replica_nodes(
                document_id=document_id,
                candidate_nodes=available_nodes,
                num_replicas=num_replicas
            )
            
            if affinity_scores:
                return [node for node, _ in affinity_scores[:num_replicas]]
        
        # Fallback: round-robin or random selection
        return available_nodes[:num_replicas]
    
    def _create_task(
        self,
        document_id: str,
        source_node: str,
        target_node: str,
        priority: ReplicationPriority
    ) -> ReplicationTask:
        """Create a replication task."""
        task_id = f"repl_{document_id}_{target_node}_{datetime.utcnow().timestamp()}"
        
        return ReplicationTask(
            task_id=task_id,
            document_id=document_id,
            source_node=source_node,
            target_node=target_node,
            priority=priority
        )
    
    def _queue_replication(
        self,
        document_id: str,
        priority: ReplicationPriority = ReplicationPriority.NORMAL
    ) -> None:
        """Queue replication for an under-replicated document."""
        doc = self.replica_tracker.get_document_replicas(document_id)
        if not doc or not doc.is_under_replicated:
            return
        
        # Find source (healthy replica)
        source_node = None
        for replica in doc.all_replicas:
            if replica.is_healthy:
                source_node = replica.node_id
                break
        
        if not source_node:
            logger.error(f"No healthy replica for {document_id}")
            return
        
        # Select new replica nodes
        current_nodes = set(doc.all_nodes)
        available = [n for n in self._cluster_nodes if n not in current_nodes]
        
        needed = doc.replication_factor - doc.healthy_count
        
        for target in available[:needed]:
            task = self._create_task(
                document_id=document_id,
                source_node=source_node,
                target_node=target,
                priority=priority
            )
            self._pending_tasks[task.task_id] = task
    
    async def start_background_replication(self) -> None:
        """Start background replication processing."""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._process_loop())
        logger.info("Started background replication")
    
    async def stop_background_replication(self) -> None:
        """Stop background replication."""
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped background replication")
    
    async def _process_loop(self) -> None:
        """Main processing loop for replication tasks."""
        while self._is_running:
            try:
                # Check for under-replicated documents
                under_replicated = self.replica_tracker.get_under_replicated()
                for doc_id in under_replicated:
                    self._queue_replication(doc_id, ReplicationPriority.HIGH)
                
                # Process pending tasks
                await self._process_pending_tasks()
                
            except Exception as e:
                logger.error(f"Replication loop error: {e}")
            
            await asyncio.sleep(self.config.check_interval_sec)
    
    async def _process_pending_tasks(self) -> None:
        """Process pending replication tasks."""
        # Sort by priority
        sorted_tasks = sorted(
            self._pending_tasks.values(),
            key=lambda t: t.priority.value,
            reverse=True
        )
        
        # Process up to max concurrent
        active_count = len(self._active_tasks)
        available_slots = self.config.max_concurrent_replications - active_count
        
        for task in sorted_tasks[:available_slots]:
            if task.task_id not in self._active_tasks:
                self._active_tasks[task.task_id] = asyncio.create_task(
                    self._execute_task(task)
                )
    
    async def _execute_task(self, task: ReplicationTask) -> bool:
        """
        Execute a single replication task.
        
        Args:
            task: Task to execute
            
        Returns:
            True if successful
        """
        task.started_at = datetime.utcnow()
        task.status = "in_progress"
        
        try:
            success = await self._do_replicate(
                task.document_id,
                task.source_node,
                task.target_node
            )
            
            if success:
                task.status = "completed"
                task.completed_at = datetime.utcnow()
                
                # Update tracker
                self.replica_tracker.add_replica(
                    task.document_id,
                    task.target_node
                )
                self.replica_tracker.update_replica_status(
                    task.document_id,
                    task.target_node,
                    ReplicaStatus.ACTIVE
                )
                
                # Update similarity graph
                self.similarity_graph.update_document_location(
                    task.document_id,
                    replica_nodes=self.replica_tracker.get_document_replicas(
                        task.document_id
                    ).all_nodes[1:]  # Skip primary
                )
                
                self._total_replications += 1
                logger.info(f"Replicated {task.document_id} to {task.target_node}")
                
            else:
                raise RuntimeError("Replication failed")
            
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            
            if task.retry_count < self.config.retry_count:
                task.status = "pending"
                await asyncio.sleep(self.config.retry_delay_sec)
            else:
                task.status = "failed"
                task.completed_at = datetime.utcnow()
                self._failed_replications += 1
                logger.error(f"Replication failed for {task.document_id}: {e}")
            
            success = False
        
        finally:
            # Clean up
            self._pending_tasks.pop(task.task_id, None)
            self._active_tasks.pop(task.task_id, None)
        
        return success
    
    async def _do_replicate(
        self,
        document_id: str,
        source_node: str,
        target_node: str
    ) -> bool:
        """Actually perform the replication."""
        if self._replicate_func:
            return await asyncio.wait_for(
                self._replicate_func(document_id, source_node, target_node),
                timeout=self.config.replication_timeout_sec
            )
        
        # Mock implementation
        logger.warning("No replicate function set, using mock")
        await asyncio.sleep(0.1)
        return True
    
    async def handle_node_failure(self, node_id: str) -> int:
        """
        Handle a node failure by re-replicating affected documents.
        
        Args:
            node_id: Failed node
            
        Returns:
            Number of documents queued for re-replication
        """
        affected = self.unregister_cluster_node(node_id)
        
        # Promote replicas where this was primary
        for doc_id in affected:
            doc = self.replica_tracker.get_document_replicas(doc_id)
            if doc and doc.primary and doc.primary.node_id == node_id:
                # Find healthy replica to promote
                for replica in doc.replicas:
                    if replica.is_healthy:
                        self.replica_tracker.promote_replica_to_primary(
                            doc_id,
                            replica.node_id
                        )
                        break
        
        return len(affected)
    
    def get_document_locations(
        self,
        document_id: str
    ) -> Tuple[Optional[str], List[str]]:
        """
        Get primary and replica locations for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            Tuple of (primary_node, replica_nodes)
        """
        doc = self.replica_tracker.get_document_replicas(document_id)
        if not doc:
            return None, []
        
        primary = doc.primary.node_id if doc.primary else None
        replicas = [r.node_id for r in doc.replicas if r.is_healthy]
        
        return primary, replicas
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get replication statistics."""
        tracker_stats = self.replica_tracker.get_statistics()
        graph_stats = self.similarity_graph.get_statistics()
        
        return {
            "is_running": self._is_running,
            "pending_tasks": len(self._pending_tasks),
            "active_tasks": len(self._active_tasks),
            "total_replications": self._total_replications,
            "failed_replications": self._failed_replications,
            "cluster_nodes": len(self._cluster_nodes),
            "tracker": tracker_stats,
            "similarity_graph": graph_stats,
            "config": {
                "replication_factor": self.config.replication_factor,
                "max_concurrent": self.config.max_concurrent_replications
            }
        }
