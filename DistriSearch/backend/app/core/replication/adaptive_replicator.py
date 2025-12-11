# -*- coding: utf-8 -*-
"""
Adaptive Replication Manager

Wraps AffinityReplicator with adaptive configuration support.
Adjusts replication behavior based on cluster size.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

from .affinity_replicator import (
    AffinityReplicator,
    ReplicationConfig,
    ReplicationPriority,
    ReplicationTask
)
from .replica_tracker import DocumentReplicas, ReplicaStatus

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveReplicationConfig:
    """
    Adaptive replication configuration.
    
    Adjusts replication factor based on available nodes.
    """
    target_replication_factor: int = 2
    min_replication_factor: int = 1
    max_concurrent_replications: int = 5
    replication_timeout_sec: float = 60.0
    
    # Current effective settings (updated dynamically)
    effective_replication_factor: int = field(init=False)
    available_nodes: int = field(default=1)
    
    def __post_init__(self):
        self.effective_replication_factor = min(
            self.target_replication_factor,
            max(0, self.available_nodes - 1)
        )
    
    def update_for_nodes(self, node_count: int) -> Dict[str, Any]:
        """
        Update configuration for current node count.
        
        Args:
            node_count: Number of available nodes
            
        Returns:
            Changes made
        """
        old_factor = self.effective_replication_factor
        self.available_nodes = node_count
        
        # Calculate new effective factor
        # With n nodes, we can have at most n-1 replicas (plus primary)
        if node_count <= 1:
            self.effective_replication_factor = 0
        elif node_count <= self.target_replication_factor:
            self.effective_replication_factor = node_count - 1
        else:
            self.effective_replication_factor = self.target_replication_factor
        
        changes = {}
        if old_factor != self.effective_replication_factor:
            changes["replication_factor"] = {
                "old": old_factor,
                "new": self.effective_replication_factor
            }
            logger.info(
                f"Replication factor adjusted: {old_factor} -> "
                f"{self.effective_replication_factor} (nodes: {node_count})"
            )
        
        return changes


class AdaptiveReplicator:
    """
    Adaptive document replicator.
    
    Features:
    - Dynamically adjusts replication factor based on cluster size
    - Handles single-node operation (no replication)
    - Upgrades replication when nodes join
    - Degrades gracefully when nodes leave
    """
    
    def __init__(
        self,
        config: Optional[AdaptiveReplicationConfig] = None,
        replicate_func: Optional[Callable[[str, str, str], Awaitable[bool]]] = None,
        get_document_vectors: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None
    ):
        """
        Initialize adaptive replicator.
        
        Args:
            config: Adaptive configuration
            replicate_func: Function to replicate documents
            get_document_vectors: Function to get document vectors
        """
        self.config = config or AdaptiveReplicationConfig()
        
        # Create underlying replicator with current config
        base_config = ReplicationConfig(
            replication_factor=self.config.effective_replication_factor + 1,  # includes primary
            max_concurrent_replications=self.config.max_concurrent_replications,
            replication_timeout_sec=self.config.replication_timeout_sec
        )
        
        self._replicator = AffinityReplicator(
            config=base_config,
            replicate_func=replicate_func,
            get_document_vectors=get_document_vectors
        )
        
        self._cluster_nodes: List[str] = []
        self._pending_upgrades: Dict[str, int] = {}  # doc_id -> target_replicas
        self._is_running = False
        self._upgrade_task: Optional[asyncio.Task] = None
    
    @property
    def replication_factor(self) -> int:
        """Current effective replication factor."""
        return self.config.effective_replication_factor
    
    @property
    def can_replicate(self) -> bool:
        """Check if replication is possible."""
        return self.config.effective_replication_factor > 0
    
    def set_replicate_function(
        self,
        func: Callable[[str, str, str], Awaitable[bool]]
    ) -> None:
        """Set the replication function."""
        self._replicator.set_replicate_function(func)
    
    def set_vector_function(
        self,
        func: Callable[[str], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Set the vector retrieval function."""
        self._replicator.set_vector_function(func)
    
    def node_joined(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node joining the cluster.
        
        Args:
            node_id: New node ID
            
        Returns:
            Configuration changes
        """
        if node_id not in self._cluster_nodes:
            self._cluster_nodes.append(node_id)
        
        self._replicator.register_cluster_node(node_id)
        
        # Update configuration
        changes = self.config.update_for_nodes(len(self._cluster_nodes))
        
        # If replication factor increased, schedule upgrades
        if changes.get("replication_factor", {}).get("new", 0) > \
           changes.get("replication_factor", {}).get("old", 0):
            self._schedule_replication_upgrades()
        
        return changes
    
    def node_left(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node leaving the cluster.
        
        Args:
            node_id: Node that left
            
        Returns:
            Configuration changes and affected documents
        """
        if node_id in self._cluster_nodes:
            self._cluster_nodes.remove(node_id)
        
        # Mark replicas on this node as failed
        affected = self._replicator.unregister_cluster_node(node_id)
        
        # Update configuration
        changes = self.config.update_for_nodes(len(self._cluster_nodes))
        
        return {
            "config_changes": changes,
            "affected_documents": affected,
            "replication_enabled": self.can_replicate
        }
    
    async def register_document(
        self,
        document_id: str,
        primary_node: str,
        document_vectors: Optional[Dict[str, Any]] = None,
        size_bytes: int = 0,
        checksum: Optional[str] = None
    ) -> DocumentReplicas:
        """
        Register a document for replication.
        
        Args:
            document_id: Document ID
            primary_node: Node storing primary copy
            document_vectors: Document vectors for affinity
            size_bytes: Document size
            checksum: Document checksum
            
        Returns:
            Replica information
        """
        if not self.can_replicate:
            # Single node mode - just track the document without replicas
            logger.info(f"Single node mode: document {document_id} stored without replicas")
            return DocumentReplicas(
                document_id=document_id,
                replication_factor=1,
                primary_node=primary_node,
                replicas=[]
            )
        
        # Update the underlying replicator's config
        self._replicator.config.replication_factor = self.config.effective_replication_factor + 1
        
        return await self._replicator.register_document(
            document_id=document_id,
            primary_node=primary_node,
            document_vectors=document_vectors,
            size_bytes=size_bytes,
            checksum=checksum
        )
    
    def _schedule_replication_upgrades(self) -> None:
        """
        Schedule replication upgrades for under-replicated documents.
        
        Called when new nodes join and replication factor increases.
        """
        under_replicated = self._replicator.replica_tracker.get_under_replicated()
        
        for doc_id in under_replicated:
            self._pending_upgrades[doc_id] = self.config.effective_replication_factor
        
        if self._pending_upgrades:
            logger.info(f"Scheduled {len(self._pending_upgrades)} documents for replication upgrade")
    
    async def process_upgrades(self) -> Dict[str, Any]:
        """
        Process pending replication upgrades.
        
        Returns:
            Upgrade results
        """
        if not self._pending_upgrades:
            return {"processed": 0, "successful": 0}
        
        processed = 0
        successful = 0
        
        for doc_id, target_replicas in list(self._pending_upgrades.items()):
            try:
                doc = self._replicator.replica_tracker.get_document_replicas(doc_id)
                
                if doc and doc.healthy_count < target_replicas + 1:  # +1 for primary
                    # Queue additional replication
                    self._replicator._queue_replication(
                        doc_id,
                        priority=ReplicationPriority.NORMAL
                    )
                    successful += 1
                
                del self._pending_upgrades[doc_id]
                processed += 1
                
            except Exception as e:
                logger.error(f"Error upgrading replication for {doc_id}: {e}")
                processed += 1
        
        return {"processed": processed, "successful": successful}
    
    async def start(self) -> None:
        """Start adaptive replication."""
        self._is_running = True
        await self._replicator.start_background_replication()
        
        # Start upgrade processing task
        self._upgrade_task = asyncio.create_task(self._upgrade_loop())
        
        logger.info("Adaptive replicator started")
    
    async def stop(self) -> None:
        """Stop adaptive replication."""
        self._is_running = False
        
        if self._upgrade_task:
            self._upgrade_task.cancel()
            try:
                await self._upgrade_task
            except asyncio.CancelledError:
                pass
        
        await self._replicator.stop_background_replication()
        
        logger.info("Adaptive replicator stopped")
    
    async def _upgrade_loop(self) -> None:
        """Background loop for processing replication upgrades."""
        while self._is_running:
            try:
                if self._pending_upgrades:
                    await self.process_upgrades()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Upgrade loop error: {e}")
                await asyncio.sleep(60)
    
    def get_status(self) -> Dict[str, Any]:
        """Get replicator status."""
        return {
            "cluster_nodes": len(self._cluster_nodes),
            "effective_replication_factor": self.config.effective_replication_factor,
            "target_replication_factor": self.config.target_replication_factor,
            "can_replicate": self.can_replicate,
            "pending_upgrades": len(self._pending_upgrades),
            "is_running": self._is_running
        }
