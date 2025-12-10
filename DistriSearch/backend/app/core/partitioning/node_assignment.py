# -*- coding: utf-8 -*-
"""
Node Assignment - Strategies for assigning documents to cluster nodes.

Implements various assignment strategies including semantic affinity
and load balancing considerations.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict

from .distance_metrics import DistanceCalculator

logger = logging.getLogger(__name__)


class AssignmentStrategy(Enum):
    """Document assignment strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    SEMANTIC_AFFINITY = "semantic_affinity"
    CONSISTENT_HASH = "consistent_hash"
    VP_TREE_PARTITION = "vp_tree_partition"


@dataclass
class NodeStats:
    """Statistics for a cluster node."""
    node_id: str
    document_count: int = 0
    total_size_bytes: int = 0
    avg_load: float = 0.0
    is_healthy: bool = True
    last_heartbeat: float = 0.0
    capacity: int = 10000  # Max documents
    
    @property
    def load_factor(self) -> float:
        """Calculate load factor (0-1)."""
        return self.document_count / self.capacity if self.capacity > 0 else 1.0
    
    @property
    def available_capacity(self) -> int:
        """Get remaining capacity."""
        return max(0, self.capacity - self.document_count)


@dataclass
class AssignmentResult:
    """Result of a document assignment."""
    document_id: str
    assigned_node: str
    partition_id: Optional[str] = None
    replica_nodes: List[str] = field(default_factory=list)
    assignment_reason: str = ""


class NodeAssigner:
    """
    Assigns documents to cluster nodes using various strategies.
    
    Supports semantic affinity-based placement where documents
    similar to existing documents on a node are placed together.
    """
    
    def __init__(
        self,
        distance_calculator: Optional[DistanceCalculator] = None,
        replication_factor: int = 2,
        default_strategy: AssignmentStrategy = AssignmentStrategy.SEMANTIC_AFFINITY
    ):
        """
        Initialize node assigner.
        
        Args:
            distance_calculator: Calculator for document distances
            replication_factor: Number of replicas per document
            default_strategy: Default assignment strategy
        """
        self.distance_calc = distance_calculator or DistanceCalculator()
        self.replication_factor = replication_factor
        self.default_strategy = default_strategy
        
        # Node tracking
        self._nodes: Dict[str, NodeStats] = {}
        self._node_documents: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._document_assignments: Dict[str, AssignmentResult] = {}
        
        # Consistent hashing ring
        self._hash_ring: List[Tuple[int, str]] = []
        self._virtual_nodes = 150
    
    def register_node(
        self,
        node_id: str,
        capacity: int = 10000,
        initial_docs: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Register a cluster node.
        
        Args:
            node_id: Unique node identifier
            capacity: Maximum document capacity
            initial_docs: Initial documents on the node
        """
        self._nodes[node_id] = NodeStats(
            node_id=node_id,
            capacity=capacity,
            document_count=len(initial_docs) if initial_docs else 0
        )
        
        if initial_docs:
            self._node_documents[node_id] = initial_docs
        
        self._rebuild_hash_ring()
        logger.info(f"Registered node {node_id} with capacity {capacity}")
    
    def unregister_node(self, node_id: str) -> List[str]:
        """
        Unregister a cluster node.
        
        Args:
            node_id: Node to remove
            
        Returns:
            List of document IDs that need reassignment
        """
        orphaned_docs = []
        
        if node_id in self._nodes:
            del self._nodes[node_id]
        
        if node_id in self._node_documents:
            for doc in self._node_documents[node_id]:
                doc_id = doc.get("id") or doc.get("document_id")
                if doc_id:
                    orphaned_docs.append(doc_id)
            del self._node_documents[node_id]
        
        # Update document assignments
        for doc_id, result in list(self._document_assignments.items()):
            if result.assigned_node == node_id:
                if result.replica_nodes:
                    # Promote replica to primary
                    result.assigned_node = result.replica_nodes[0]
                    result.replica_nodes = result.replica_nodes[1:]
                else:
                    orphaned_docs.append(doc_id)
        
        self._rebuild_hash_ring()
        logger.info(f"Unregistered node {node_id}, {len(orphaned_docs)} docs need reassignment")
        
        return orphaned_docs
    
    def update_node_stats(
        self,
        node_id: str,
        document_count: Optional[int] = None,
        is_healthy: Optional[bool] = None,
        last_heartbeat: Optional[float] = None
    ) -> None:
        """
        Update statistics for a node.
        
        Args:
            node_id: Node to update
            document_count: New document count
            is_healthy: Health status
            last_heartbeat: Last heartbeat timestamp
        """
        if node_id not in self._nodes:
            logger.warning(f"Unknown node: {node_id}")
            return
        
        stats = self._nodes[node_id]
        
        if document_count is not None:
            stats.document_count = document_count
        if is_healthy is not None:
            stats.is_healthy = is_healthy
        if last_heartbeat is not None:
            stats.last_heartbeat = last_heartbeat
    
    def _rebuild_hash_ring(self) -> None:
        """Rebuild consistent hash ring."""
        self._hash_ring.clear()
        
        for node_id in self._nodes:
            for i in range(self._virtual_nodes):
                key = f"{node_id}:{i}"
                hash_val = hash(key) & 0xFFFFFFFF
                self._hash_ring.append((hash_val, node_id))
        
        self._hash_ring.sort(key=lambda x: x[0])
    
    def _hash_assignment(self, document_id: str) -> Optional[str]:
        """
        Assign using consistent hashing.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Assigned node ID
        """
        if not self._hash_ring:
            return None
        
        doc_hash = hash(document_id) & 0xFFFFFFFF
        
        # Binary search for position in ring
        left, right = 0, len(self._hash_ring)
        while left < right:
            mid = (left + right) // 2
            if self._hash_ring[mid][0] < doc_hash:
                left = mid + 1
            else:
                right = mid
        
        # Wrap around
        if left >= len(self._hash_ring):
            left = 0
        
        return self._hash_ring[left][1]
    
    def _round_robin_assignment(self, document_id: str) -> Optional[str]:
        """
        Assign using round-robin.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Assigned node ID
        """
        healthy_nodes = [
            n for n in self._nodes.values()
            if n.is_healthy and n.available_capacity > 0
        ]
        
        if not healthy_nodes:
            return None
        
        # Use document hash to deterministically select
        idx = hash(document_id) % len(healthy_nodes)
        return healthy_nodes[idx].node_id
    
    def _least_loaded_assignment(self, document_id: str) -> Optional[str]:
        """
        Assign to least loaded node.
        
        Args:
            document_id: Document identifier (unused but kept for signature)
            
        Returns:
            Assigned node ID
        """
        healthy_nodes = [
            n for n in self._nodes.values()
            if n.is_healthy and n.available_capacity > 0
        ]
        
        if not healthy_nodes:
            return None
        
        # Find node with lowest load factor
        return min(healthy_nodes, key=lambda n: n.load_factor).node_id
    
    def _semantic_affinity_assignment(
        self,
        document: Dict[str, Any],
        exclude_nodes: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Assign based on semantic affinity.
        
        Places document on node that has most similar existing documents.
        
        Args:
            document: Document with vectors
            exclude_nodes: Nodes to exclude from consideration
            
        Returns:
            Assigned node ID
        """
        exclude = set(exclude_nodes or [])
        
        healthy_nodes = [
            n for n in self._nodes.values()
            if n.is_healthy and n.available_capacity > 0 and n.node_id not in exclude
        ]
        
        if not healthy_nodes:
            return None
        
        best_node = None
        best_affinity = float('inf')
        
        for node in healthy_nodes:
            node_docs = self._node_documents.get(node.node_id, [])
            
            if not node_docs:
                # Empty node - neutral affinity
                affinity = 0.5
            else:
                # Calculate average distance to documents on node
                # Lower distance = higher affinity
                sample_size = min(10, len(node_docs))
                sample = node_docs[:sample_size]
                
                distances = [
                    self.distance_calc.weighted_distance(document, doc)
                    for doc in sample
                ]
                affinity = np.mean(distances)
            
            # Apply load balancing factor
            load_penalty = node.load_factor * 0.2
            adjusted_affinity = affinity + load_penalty
            
            if adjusted_affinity < best_affinity:
                best_affinity = adjusted_affinity
                best_node = node.node_id
        
        return best_node
    
    def assign_document(
        self,
        document: Dict[str, Any],
        strategy: Optional[AssignmentStrategy] = None,
        partition_id: Optional[str] = None
    ) -> AssignmentResult:
        """
        Assign a document to cluster nodes.
        
        Args:
            document: Document with vectors and metadata
            strategy: Assignment strategy (uses default if None)
            partition_id: Pre-determined partition ID (from VP-Tree)
            
        Returns:
            Assignment result with primary and replica nodes
        """
        strategy = strategy or self.default_strategy
        doc_id = document.get("id") or document.get("document_id") or str(hash(str(document)))
        
        # Select primary node
        if strategy == AssignmentStrategy.ROUND_ROBIN:
            primary = self._round_robin_assignment(doc_id)
        elif strategy == AssignmentStrategy.LEAST_LOADED:
            primary = self._least_loaded_assignment(doc_id)
        elif strategy == AssignmentStrategy.CONSISTENT_HASH:
            primary = self._hash_assignment(doc_id)
        elif strategy == AssignmentStrategy.SEMANTIC_AFFINITY:
            primary = self._semantic_affinity_assignment(document)
        elif strategy == AssignmentStrategy.VP_TREE_PARTITION:
            # Partition ID should map to a node
            primary = self._get_node_for_partition(partition_id)
            if not primary:
                primary = self._semantic_affinity_assignment(document)
        else:
            primary = self._least_loaded_assignment(doc_id)
        
        if not primary:
            raise RuntimeError("No available nodes for document assignment")
        
        # Select replica nodes using semantic affinity
        replicas = self._select_replica_nodes(document, primary)
        
        result = AssignmentResult(
            document_id=doc_id,
            assigned_node=primary,
            partition_id=partition_id,
            replica_nodes=replicas,
            assignment_reason=f"Strategy: {strategy.value}"
        )
        
        # Track assignment
        self._document_assignments[doc_id] = result
        self._node_documents[primary].append(document)
        self._nodes[primary].document_count += 1
        
        return result
    
    def _get_node_for_partition(self, partition_id: Optional[str]) -> Optional[str]:
        """Get node assigned to a partition."""
        # This would be looked up from VP-Tree partition assignments
        # For now, return None to fall back to semantic affinity
        return None
    
    def _select_replica_nodes(
        self,
        document: Dict[str, Any],
        primary_node: str
    ) -> List[str]:
        """
        Select nodes for replicas using semantic affinity.
        
        Per architecture: "similarity graph, place replicas on nodes
        with neighboring documents"
        
        Args:
            document: Document to replicate
            primary_node: Primary node (excluded)
            
        Returns:
            List of replica node IDs
        """
        replicas = []
        exclude = [primary_node]
        
        for _ in range(self.replication_factor - 1):
            replica = self._semantic_affinity_assignment(document, exclude)
            if replica:
                replicas.append(replica)
                exclude.append(replica)
            else:
                break
        
        return replicas
    
    def get_document_location(self, document_id: str) -> Optional[AssignmentResult]:
        """
        Get location of a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Assignment result or None if not found
        """
        return self._document_assignments.get(document_id)
    
    def get_node_stats(self, node_id: str) -> Optional[NodeStats]:
        """Get statistics for a node."""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[NodeStats]:
        """Get all registered nodes."""
        return list(self._nodes.values())
    
    def get_healthy_nodes(self) -> List[NodeStats]:
        """Get all healthy nodes."""
        return [n for n in self._nodes.values() if n.is_healthy]
    
    def get_load_distribution(self) -> Dict[str, float]:
        """
        Get load distribution across nodes.
        
        Returns:
            Dict mapping node_id to load factor
        """
        return {
            node_id: stats.load_factor
            for node_id, stats in self._nodes.items()
        }
    
    def is_balanced(self, threshold: float = 0.2) -> bool:
        """
        Check if load is balanced across nodes.
        
        Args:
            threshold: Maximum allowed variance
            
        Returns:
            True if balanced
        """
        loads = list(self.get_load_distribution().values())
        if not loads:
            return True
        
        return (max(loads) - min(loads)) <= threshold
