# -*- coding: utf-8 -*-
"""
VP-Tree (Vantage-Point Tree) - Metric space partitioning structure.

Implements VP-Tree for efficient nearest-neighbor search in document
vector space. Used for organizing documents across distributed nodes
with semantic locality preservation.

Architecture spec: Use k-medoids to find vantage point that minimizes
the sum of distances to all documents in the partition.
"""

import numpy as np
from typing import List, Optional, Tuple, Callable, Any, Dict
from dataclasses import dataclass, field
from enum import Enum
import logging
import random
from collections import deque

from .distance_metrics import DistanceCalculator, MetricType

logger = logging.getLogger(__name__)


@dataclass
class VPNode:
    """
    Node in the VP-Tree structure.
    
    Attributes:
        vantage_point: The document chosen as vantage point
        vantage_id: ID of the vantage point document
        median_distance: Median distance threshold for partitioning
        left: Left subtree (documents closer than median)
        right: Right subtree (documents farther than median)
        documents: Documents stored at this node (for leaf nodes)
        node_id: Unique identifier for this VP node
        depth: Depth in the tree
        assigned_node: ID of the cluster node assigned to this partition
    """
    vantage_point: Optional[Dict[str, Any]] = None
    vantage_id: Optional[str] = None
    median_distance: float = 0.0
    left: Optional['VPNode'] = None
    right: Optional['VPNode'] = None
    documents: List[Dict[str, Any]] = field(default_factory=list)
    node_id: str = ""
    depth: int = 0
    assigned_node: Optional[str] = None
    
    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node."""
        return self.left is None and self.right is None
    
    @property
    def size(self) -> int:
        """Get number of documents in subtree."""
        if self.is_leaf:
            return len(self.documents)
        
        count = 1 if self.vantage_point else 0
        if self.left:
            count += self.left.size
        if self.right:
            count += self.right.size
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary."""
        return {
            "node_id": self.node_id,
            "vantage_id": self.vantage_id,
            "median_distance": self.median_distance,
            "depth": self.depth,
            "assigned_node": self.assigned_node,
            "is_leaf": self.is_leaf,
            "document_count": len(self.documents) if self.is_leaf else 0,
            "left": self.left.node_id if self.left else None,
            "right": self.right.node_id if self.right else None,
        }


class VantagePointSelection(Enum):
    """Strategy for selecting vantage points."""
    RANDOM = "random"
    K_MEDOIDS = "k_medoids"
    MAX_SPREAD = "max_spread"


class VPTree:
    """
    Vantage-Point Tree for document partitioning.
    
    Organizes documents in metric space for efficient nearest-neighbor
    queries and semantic partitioning across cluster nodes.
    """
    
    def __init__(
        self,
        distance_calculator: Optional[DistanceCalculator] = None,
        leaf_size: int = 50,
        selection_strategy: VantagePointSelection = VantagePointSelection.K_MEDOIDS,
        sample_size: int = 10
    ):
        """
        Initialize VP-Tree.
        
        Args:
            distance_calculator: Calculator for document distances
            leaf_size: Maximum documents per leaf node
            selection_strategy: Strategy for vantage point selection
            sample_size: Number of candidates to sample for vantage point
        """
        self.distance_calc = distance_calculator or DistanceCalculator()
        self.leaf_size = leaf_size
        self.selection_strategy = selection_strategy
        self.sample_size = sample_size
        self.root: Optional[VPNode] = None
        self._node_counter = 0
        self._all_nodes: Dict[str, VPNode] = {}
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID."""
        self._node_counter += 1
        return f"vpn_{self._node_counter}"
    
    def _distance(self, doc_a: Dict[str, Any], doc_b: Dict[str, Any]) -> float:
        """Calculate distance between two documents."""
        return self.distance_calc.weighted_distance(doc_a, doc_b)
    
    def _select_vantage_point_random(
        self,
        documents: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Select random vantage point.
        
        Args:
            documents: List of documents
            
        Returns:
            Tuple of (vantage_point, index)
        """
        idx = random.randint(0, len(documents) - 1)
        return documents[idx], idx
    
    def _select_vantage_point_spread(
        self,
        documents: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Select vantage point that maximizes distance spread.
        
        Samples candidates and picks the one with highest variance
        in distances to other documents.
        
        Args:
            documents: List of documents
            
        Returns:
            Tuple of (vantage_point, index)
        """
        n = len(documents)
        sample_count = min(self.sample_size, n)
        candidates = random.sample(range(n), sample_count)
        
        best_idx = candidates[0]
        best_spread = -1.0
        
        for idx in candidates:
            # Calculate distances to all other documents
            distances = []
            for j in range(n):
                if j != idx:
                    d = self._distance(documents[idx], documents[j])
                    distances.append(d)
            
            # Spread = variance of distances
            if distances:
                spread = np.var(distances)
                if spread > best_spread:
                    best_spread = spread
                    best_idx = idx
        
        return documents[best_idx], best_idx
    
    def _select_vantage_point_kmedoids(
        self,
        documents: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Select vantage point using k-medoids approach.
        
        Finds the document that minimizes sum of distances to all
        other documents (the medoid).
        
        Args:
            documents: List of documents
            
        Returns:
            Tuple of (vantage_point, index)
        """
        n = len(documents)
        
        if n <= self.sample_size:
            # Check all documents
            candidates = list(range(n))
        else:
            # Sample candidates for efficiency
            candidates = random.sample(range(n), self.sample_size)
        
        best_idx = candidates[0]
        best_total_dist = float('inf')
        
        for idx in candidates:
            # Calculate sum of distances to all documents
            total_dist = 0.0
            for j in range(n):
                if j != idx:
                    total_dist += self._distance(documents[idx], documents[j])
            
            if total_dist < best_total_dist:
                best_total_dist = total_dist
                best_idx = idx
        
        return documents[best_idx], best_idx
    
    def _select_vantage_point(
        self,
        documents: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Select vantage point using configured strategy.
        
        Args:
            documents: List of documents
            
        Returns:
            Tuple of (vantage_point, index)
        """
        if self.selection_strategy == VantagePointSelection.RANDOM:
            return self._select_vantage_point_random(documents)
        elif self.selection_strategy == VantagePointSelection.MAX_SPREAD:
            return self._select_vantage_point_spread(documents)
        else:  # K_MEDOIDS (default)
            return self._select_vantage_point_kmedoids(documents)
    
    def _build_recursive(
        self,
        documents: List[Dict[str, Any]],
        depth: int = 0
    ) -> Optional[VPNode]:
        """
        Recursively build VP-Tree.
        
        Args:
            documents: Documents to partition
            depth: Current depth
            
        Returns:
            Root node of subtree
        """
        if not documents:
            return None
        
        node_id = self._generate_node_id()
        
        # Leaf node if few documents
        if len(documents) <= self.leaf_size:
            node = VPNode(
                documents=documents.copy(),
                node_id=node_id,
                depth=depth
            )
            self._all_nodes[node_id] = node
            return node
        
        # Select vantage point
        vp, vp_idx = self._select_vantage_point(documents)
        vp_id = vp.get("id") or vp.get("document_id") or str(vp_idx)
        
        # Calculate distances from vantage point
        remaining = documents[:vp_idx] + documents[vp_idx + 1:]
        distances = []
        
        for doc in remaining:
            d = self._distance(vp, doc)
            distances.append((d, doc))
        
        # Sort by distance and find median
        distances.sort(key=lambda x: x[0])
        median_idx = len(distances) // 2
        median_distance = distances[median_idx][0] if distances else 0.0
        
        # Partition documents
        left_docs = [doc for d, doc in distances if d <= median_distance]
        right_docs = [doc for d, doc in distances if d > median_distance]
        
        # Handle edge case where all distances are equal
        if not left_docs or not right_docs:
            mid = len(remaining) // 2
            left_docs = remaining[:mid]
            right_docs = remaining[mid:]
            if left_docs and right_docs:
                median_distance = self._distance(vp, right_docs[0])
        
        # Create node
        node = VPNode(
            vantage_point=vp,
            vantage_id=vp_id,
            median_distance=median_distance,
            node_id=node_id,
            depth=depth
        )
        
        # Recursively build subtrees
        node.left = self._build_recursive(left_docs, depth + 1)
        node.right = self._build_recursive(right_docs, depth + 1)
        
        self._all_nodes[node_id] = node
        return node
    
    def build(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build VP-Tree from documents.
        
        Args:
            documents: List of documents with vector representations
        """
        logger.info(f"Building VP-Tree with {len(documents)} documents")
        self._node_counter = 0
        self._all_nodes.clear()
        
        self.root = self._build_recursive(documents)
        
        logger.info(
            f"VP-Tree built: {len(self._all_nodes)} nodes, "
            f"max depth estimated from structure"
        )
    
    def search_knn(
        self,
        query: Dict[str, Any],
        k: int = 10,
        max_distance: Optional[float] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find k nearest neighbors to query.
        
        Args:
            query: Query document with vectors
            k: Number of neighbors to find
            max_distance: Maximum distance threshold (optional)
            
        Returns:
            List of (document, distance) tuples sorted by distance
        """
        if self.root is None:
            return []
        
        # Priority queue: (negative_distance, document)
        # Using list for simplicity, could optimize with heap
        neighbors: List[Tuple[float, Dict[str, Any]]] = []
        tau = max_distance if max_distance else float('inf')
        
        def search_recursive(node: Optional[VPNode]):
            nonlocal tau
            
            if node is None:
                return
            
            if node.is_leaf:
                # Check all documents in leaf
                for doc in node.documents:
                    d = self._distance(query, doc)
                    if d < tau:
                        neighbors.append((d, doc))
                        neighbors.sort(key=lambda x: x[0])
                        if len(neighbors) > k:
                            neighbors.pop()
                        if len(neighbors) == k:
                            tau = neighbors[-1][0]
                return
            
            # Calculate distance to vantage point
            vp_dist = self._distance(query, node.vantage_point)
            
            # Check if vantage point qualifies
            if vp_dist < tau:
                neighbors.append((vp_dist, node.vantage_point))
                neighbors.sort(key=lambda x: x[0])
                if len(neighbors) > k:
                    neighbors.pop()
                if len(neighbors) == k:
                    tau = neighbors[-1][0]
            
            # Determine search order
            if vp_dist < node.median_distance:
                # Query is closer to left subtree
                if vp_dist - tau <= node.median_distance:
                    search_recursive(node.left)
                if vp_dist + tau >= node.median_distance:
                    search_recursive(node.right)
            else:
                # Query is closer to right subtree
                if vp_dist + tau >= node.median_distance:
                    search_recursive(node.right)
                if vp_dist - tau <= node.median_distance:
                    search_recursive(node.left)
        
        search_recursive(self.root)
        
        return [(doc, dist) for dist, doc in neighbors]
    
    def search_range(
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
        if self.root is None:
            return []
        
        results: List[Tuple[Dict[str, Any], float]] = []
        
        def search_recursive(node: Optional[VPNode]):
            if node is None:
                return
            
            if node.is_leaf:
                for doc in node.documents:
                    d = self._distance(query, doc)
                    if d <= radius:
                        results.append((doc, d))
                return
            
            # Check vantage point
            vp_dist = self._distance(query, node.vantage_point)
            if vp_dist <= radius:
                results.append((node.vantage_point, vp_dist))
            
            # Search subtrees that may contain results
            if vp_dist - radius <= node.median_distance:
                search_recursive(node.left)
            if vp_dist + radius >= node.median_distance:
                search_recursive(node.right)
        
        search_recursive(self.root)
        results.sort(key=lambda x: x[1])
        
        return results
    
    def find_partition(self, query: Dict[str, Any]) -> Optional[str]:
        """
        Find the partition (leaf node) where query belongs.
        
        Args:
            query: Query document with vectors
            
        Returns:
            Node ID of the partition, or None if tree empty
        """
        if self.root is None:
            return None
        
        node = self.root
        
        while not node.is_leaf:
            vp_dist = self._distance(query, node.vantage_point)
            
            if vp_dist <= node.median_distance:
                if node.left:
                    node = node.left
                else:
                    break
            else:
                if node.right:
                    node = node.right
                else:
                    break
        
        return node.node_id
    
    def get_partition_node(
        self,
        query: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Find partition and assigned cluster node for query.
        
        Args:
            query: Query document with vectors
            
        Returns:
            Tuple of (partition_id, assigned_node_id)
        """
        partition_id = self.find_partition(query)
        if partition_id and partition_id in self._all_nodes:
            node = self._all_nodes[partition_id]
            return partition_id, node.assigned_node
        return partition_id, None
    
    def assign_nodes_to_partitions(
        self,
        cluster_nodes: List[str],
        strategy: str = "round_robin"
    ) -> Dict[str, str]:
        """
        Assign cluster nodes to tree partitions.
        
        Args:
            cluster_nodes: List of cluster node IDs
            strategy: Assignment strategy ("round_robin", "balanced")
            
        Returns:
            Mapping of partition_id -> cluster_node_id
        """
        assignments = {}
        leaf_nodes = [
            n for n in self._all_nodes.values()
            if n.is_leaf
        ]
        
        if not cluster_nodes or not leaf_nodes:
            return assignments
        
        if strategy == "round_robin":
            for i, leaf in enumerate(leaf_nodes):
                node_idx = i % len(cluster_nodes)
                leaf.assigned_node = cluster_nodes[node_idx]
                assignments[leaf.node_id] = cluster_nodes[node_idx]
        
        elif strategy == "balanced":
            # Sort leaves by size, assign largest to least loaded nodes
            leaf_nodes.sort(key=lambda x: len(x.documents), reverse=True)
            node_loads = {n: 0 for n in cluster_nodes}
            
            for leaf in leaf_nodes:
                # Find least loaded node
                min_node = min(node_loads, key=node_loads.get)
                leaf.assigned_node = min_node
                assignments[leaf.node_id] = min_node
                node_loads[min_node] += len(leaf.documents)
        
        return assignments
    
    def get_all_partitions(self) -> List[Dict[str, Any]]:
        """
        Get information about all partitions.
        
        Returns:
            List of partition info dictionaries
        """
        return [
            node.to_dict()
            for node in self._all_nodes.values()
        ]
    
    def get_leaf_partitions(self) -> List[VPNode]:
        """
        Get all leaf partitions.
        
        Returns:
            List of leaf VPNode objects
        """
        return [
            node for node in self._all_nodes.values()
            if node.is_leaf
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get tree statistics.
        
        Returns:
            Dictionary with tree statistics
        """
        if not self._all_nodes:
            return {"empty": True}
        
        leaf_nodes = self.get_leaf_partitions()
        leaf_sizes = [len(n.documents) for n in leaf_nodes]
        depths = [n.depth for n in self._all_nodes.values()]
        
        return {
            "total_nodes": len(self._all_nodes),
            "leaf_nodes": len(leaf_nodes),
            "internal_nodes": len(self._all_nodes) - len(leaf_nodes),
            "max_depth": max(depths) if depths else 0,
            "avg_leaf_size": np.mean(leaf_sizes) if leaf_sizes else 0,
            "min_leaf_size": min(leaf_sizes) if leaf_sizes else 0,
            "max_leaf_size": max(leaf_sizes) if leaf_sizes else 0,
            "total_documents": sum(leaf_sizes),
        }
