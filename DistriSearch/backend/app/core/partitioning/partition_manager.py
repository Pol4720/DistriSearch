# -*- coding: utf-8 -*-
"""
Partition Manager - High-level partition management.

Coordinates VP-Tree partitioning with node assignment and
provides APIs for document routing and partition queries.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from .vp_tree import VPTree, VPNode, VantagePointSelection
from .node_assignment import NodeAssigner, AssignmentStrategy, AssignmentResult, NodeStats
from .distance_metrics import DistanceCalculator, DistanceWeights

logger = logging.getLogger(__name__)


@dataclass
class PartitionInfo:
    """Information about a partition."""
    partition_id: str
    assigned_node: Optional[str]
    document_count: int
    depth: int
    is_leaf: bool
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RoutingResult:
    """Result of document routing."""
    document_id: str
    partition_id: str
    primary_node: str
    replica_nodes: List[str]
    distance_to_vp: Optional[float] = None


class PartitionManager:
    """
    Manages document partitioning and routing.
    
    Combines VP-Tree for semantic partitioning with node assignment
    for distributed storage. Provides unified API for:
    - Building/rebuilding partitions
    - Routing documents to appropriate nodes
    - Finding nearest neighbors
    - Rebalancing partitions
    """
    
    def __init__(
        self,
        leaf_size: int = 50,
        replication_factor: int = 2,
        distance_weights: Optional[DistanceWeights] = None,
        vp_selection: VantagePointSelection = VantagePointSelection.K_MEDOIDS
    ):
        """
        Initialize partition manager.
        
        Args:
            leaf_size: Maximum documents per VP-Tree leaf
            replication_factor: Number of replicas per document
            distance_weights: Weights for distance calculation
            vp_selection: Vantage point selection strategy
        """
        self.leaf_size = leaf_size
        self.replication_factor = replication_factor
        
        # Initialize components
        self.distance_calc = DistanceCalculator(distance_weights)
        self.vp_tree = VPTree(
            distance_calculator=self.distance_calc,
            leaf_size=leaf_size,
            selection_strategy=vp_selection
        )
        self.node_assigner = NodeAssigner(
            distance_calculator=self.distance_calc,
            replication_factor=replication_factor
        )
        
        # State tracking
        self._initialized = False
        self._last_rebuild: Optional[datetime] = None
        self._document_count = 0
        self._partition_assignments: Dict[str, str] = {}  # partition_id -> node_id
    
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
            initial_docs: Initial documents on node
        """
        self.node_assigner.register_node(node_id, capacity, initial_docs)
        logger.info(f"Registered node {node_id}")
    
    def unregister_node(self, node_id: str) -> List[str]:
        """
        Unregister a cluster node.
        
        Args:
            node_id: Node to remove
            
        Returns:
            Document IDs needing reassignment
        """
        # Update partition assignments
        for partition_id, assigned_node in list(self._partition_assignments.items()):
            if assigned_node == node_id:
                # Reassign partition to another node
                new_node = self._find_replacement_node(partition_id)
                if new_node:
                    self._partition_assignments[partition_id] = new_node
                else:
                    del self._partition_assignments[partition_id]
        
        return self.node_assigner.unregister_node(node_id)
    
    def _find_replacement_node(self, partition_id: str) -> Optional[str]:
        """Find replacement node for a partition."""
        healthy = self.node_assigner.get_healthy_nodes()
        if not healthy:
            return None
        
        # Find least loaded node
        return min(healthy, key=lambda n: n.load_factor).node_id
    
    def build_partitions(
        self,
        documents: List[Dict[str, Any]],
        cluster_nodes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build VP-Tree partitions from documents.
        
        Args:
            documents: Documents with vector representations
            cluster_nodes: Node IDs to assign partitions to
            
        Returns:
            Build statistics
        """
        logger.info(f"Building partitions for {len(documents)} documents")
        
        # Build VP-Tree
        self.vp_tree.build(documents)
        
        # Get available nodes
        if cluster_nodes is None:
            cluster_nodes = [n.node_id for n in self.node_assigner.get_healthy_nodes()]
        
        # Assign partitions to nodes
        if cluster_nodes:
            self._partition_assignments = self.vp_tree.assign_nodes_to_partitions(
                cluster_nodes,
                strategy="balanced"
            )
        
        self._initialized = True
        self._last_rebuild = datetime.utcnow()
        self._document_count = len(documents)
        
        stats = self.vp_tree.get_statistics()
        stats["partition_assignments"] = len(self._partition_assignments)
        stats["last_rebuild"] = self._last_rebuild.isoformat()
        
        logger.info(f"Partitions built: {stats}")
        return stats
    
    async def build_partitions_async(
        self,
        documents: List[Dict[str, Any]],
        cluster_nodes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Async version of build_partitions."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.build_partitions(documents, cluster_nodes)
        )
    
    def route_document(
        self,
        document: Dict[str, Any],
        strategy: AssignmentStrategy = AssignmentStrategy.VP_TREE_PARTITION
    ) -> RoutingResult:
        """
        Route a document to appropriate nodes.
        
        Args:
            document: Document with vectors
            strategy: Assignment strategy
            
        Returns:
            Routing result with node assignments
        """
        doc_id = document.get("id") or document.get("document_id")
        
        # Find VP-Tree partition
        partition_id = None
        distance_to_vp = None
        
        if self._initialized and strategy == AssignmentStrategy.VP_TREE_PARTITION:
            partition_id = self.vp_tree.find_partition(document)
            
            # Get assigned node for partition
            if partition_id and partition_id in self._partition_assignments:
                assigned_node = self._partition_assignments[partition_id]
                # Still use node assigner to get replicas
                result = self.node_assigner.assign_document(
                    document,
                    strategy=AssignmentStrategy.SEMANTIC_AFFINITY,
                    partition_id=partition_id
                )
                result.assigned_node = assigned_node
                
                return RoutingResult(
                    document_id=doc_id,
                    partition_id=partition_id,
                    primary_node=assigned_node,
                    replica_nodes=result.replica_nodes,
                    distance_to_vp=distance_to_vp
                )
        
        # Fall back to node assigner
        result = self.node_assigner.assign_document(
            document,
            strategy=strategy,
            partition_id=partition_id
        )
        
        return RoutingResult(
            document_id=doc_id,
            partition_id=partition_id or "unpartitioned",
            primary_node=result.assigned_node,
            replica_nodes=result.replica_nodes,
            distance_to_vp=distance_to_vp
        )
    
    def find_nearest_documents(
        self,
        query: Dict[str, Any],
        k: int = 10,
        max_distance: Optional[float] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find k nearest documents to query.
        
        Args:
            query: Query document with vectors
            k: Number of results
            max_distance: Maximum distance threshold
            
        Returns:
            List of (document, distance) tuples
        """
        if not self._initialized:
            logger.warning("Partitions not initialized, returning empty results")
            return []
        
        return self.vp_tree.search_knn(query, k, max_distance)
    
    def find_documents_in_range(
        self,
        query: Dict[str, Any],
        radius: float
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find all documents within radius of query.
        
        Args:
            query: Query document with vectors
            radius: Search radius
            
        Returns:
            List of (document, distance) tuples
        """
        if not self._initialized:
            return []
        
        return self.vp_tree.search_range(query, radius)
    
    def get_nodes_for_query(self, query: Dict[str, Any]) -> List[str]:
        """
        Get nodes that should be queried for a search.
        
        Uses VP-Tree to identify relevant partitions and their nodes.
        
        Args:
            query: Query document with vectors
            
        Returns:
            List of node IDs to query
        """
        nodes = set()
        
        if self._initialized:
            # Find partition for query
            partition_id = self.vp_tree.find_partition(query)
            if partition_id and partition_id in self._partition_assignments:
                nodes.add(self._partition_assignments[partition_id])
            
            # Also get nodes for nearby partitions (for better recall)
            nearby = self.vp_tree.search_range(query, 0.3)
            for doc, _ in nearby[:5]:
                part_id = doc.get("_partition_id")
                if part_id and part_id in self._partition_assignments:
                    nodes.add(self._partition_assignments[part_id])
        
        # If no nodes found, query all healthy nodes
        if not nodes:
            nodes = {n.node_id for n in self.node_assigner.get_healthy_nodes()}
        
        return list(nodes)
    
    def get_partition_info(self, partition_id: str) -> Optional[PartitionInfo]:
        """
        Get information about a partition.
        
        Args:
            partition_id: Partition identifier
            
        Returns:
            Partition info or None
        """
        node = self.vp_tree._all_nodes.get(partition_id)
        if not node:
            return None
        
        return PartitionInfo(
            partition_id=partition_id,
            assigned_node=self._partition_assignments.get(partition_id),
            document_count=len(node.documents) if node.is_leaf else 0,
            depth=node.depth,
            is_leaf=node.is_leaf
        )
    
    def get_all_partitions(self) -> List[PartitionInfo]:
        """Get info for all partitions."""
        partitions = []
        for node in self.vp_tree._all_nodes.values():
            if node.is_leaf:
                partitions.append(PartitionInfo(
                    partition_id=node.node_id,
                    assigned_node=self._partition_assignments.get(node.node_id),
                    document_count=len(node.documents),
                    depth=node.depth,
                    is_leaf=True
                ))
        return partitions
    
    def get_node_partitions(self, node_id: str) -> List[str]:
        """
        Get partitions assigned to a node.
        
        Args:
            node_id: Node identifier
            
        Returns:
            List of partition IDs
        """
        return [
            part_id for part_id, assigned in self._partition_assignments.items()
            if assigned == node_id
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get partition manager statistics."""
        tree_stats = self.vp_tree.get_statistics() if self._initialized else {}
        
        return {
            "initialized": self._initialized,
            "document_count": self._document_count,
            "last_rebuild": self._last_rebuild.isoformat() if self._last_rebuild else None,
            "partition_count": len(self._partition_assignments),
            "registered_nodes": len(self.node_assigner.get_all_nodes()),
            "healthy_nodes": len(self.node_assigner.get_healthy_nodes()),
            "load_distribution": self.node_assigner.get_load_distribution(),
            "is_balanced": self.node_assigner.is_balanced(),
            **tree_stats
        }
    
    def needs_rebalance(self, threshold: float = 0.3) -> bool:
        """
        Check if partitions need rebalancing.
        
        Args:
            threshold: Load imbalance threshold
            
        Returns:
            True if rebalance needed
        """
        return not self.node_assigner.is_balanced(threshold)
    
    def export_state(self) -> Dict[str, Any]:
        """Export partition state for persistence."""
        return {
            "partition_assignments": self._partition_assignments,
            "document_count": self._document_count,
            "last_rebuild": self._last_rebuild.isoformat() if self._last_rebuild else None,
            "tree_stats": self.vp_tree.get_statistics() if self._initialized else {},
        }
    
    def import_state(self, state: Dict[str, Any]) -> None:
        """Import partition state from persistence."""
        self._partition_assignments = state.get("partition_assignments", {})
        self._document_count = state.get("document_count", 0)
        
        rebuild_str = state.get("last_rebuild")
        if rebuild_str:
            self._last_rebuild = datetime.fromisoformat(rebuild_str)
        
        self._initialized = bool(self._partition_assignments)
