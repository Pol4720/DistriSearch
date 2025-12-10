# -*- coding: utf-8 -*-
"""
Similarity Graph - Tracks document similarity relationships.

Used for semantic affinity replication:
"similarity graph, place replicas on nodes with neighboring documents"
"""

import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import logging
import heapq

logger = logging.getLogger(__name__)


@dataclass
class DocumentNode:
    """Node in the similarity graph representing a document."""
    document_id: str
    primary_node: str
    replica_nodes: List[str] = field(default_factory=list)
    neighbors: Dict[str, float] = field(default_factory=dict)  # doc_id -> similarity
    created_at: datetime = field(default_factory=datetime.utcnow)
    vector_hash: Optional[str] = None  # For detecting document updates
    
    @property
    def all_nodes(self) -> List[str]:
        """All nodes storing this document."""
        return [self.primary_node] + self.replica_nodes


@dataclass
class SimilarityEdge:
    """Edge in similarity graph between two documents."""
    doc_a: str
    doc_b: str
    similarity: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __hash__(self):
        return hash(tuple(sorted([self.doc_a, self.doc_b])))
    
    def __eq__(self, other):
        if not isinstance(other, SimilarityEdge):
            return False
        return set([self.doc_a, self.doc_b]) == set([other.doc_a, other.doc_b])


class SimilarityGraph:
    """
    Graph structure tracking document similarities.
    
    Used to:
    - Find semantically similar documents
    - Determine optimal replica placement
    - Support nearest-neighbor queries
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.3,
        max_neighbors: int = 20,
        distance_func: Optional[callable] = None
    ):
        """
        Initialize similarity graph.
        
        Args:
            similarity_threshold: Minimum similarity to create edge
            max_neighbors: Maximum neighbors per document
            distance_func: Function to compute distance between docs
        """
        self.similarity_threshold = similarity_threshold
        self.max_neighbors = max_neighbors
        self._distance_func = distance_func
        
        # Graph storage
        self._nodes: Dict[str, DocumentNode] = {}
        self._edges: Dict[str, Set[str]] = defaultdict(set)  # doc_id -> set of neighbor ids
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        
        # Index for fast lookups
        self._node_to_docs: Dict[str, Set[str]] = defaultdict(set)  # cluster_node -> doc_ids
    
    def set_distance_function(self, func: callable) -> None:
        """Set the distance calculation function."""
        self._distance_func = func
    
    def add_document(
        self,
        document_id: str,
        primary_node: str,
        document_vectors: Optional[Dict[str, Any]] = None,
        replica_nodes: Optional[List[str]] = None
    ) -> DocumentNode:
        """
        Add a document to the graph.
        
        Args:
            document_id: Document identifier
            primary_node: Primary storage node
            document_vectors: Document vector representations
            replica_nodes: Nodes storing replicas
            
        Returns:
            Created document node
        """
        node = DocumentNode(
            document_id=document_id,
            primary_node=primary_node,
            replica_nodes=replica_nodes or []
        )
        
        self._nodes[document_id] = node
        self._node_to_docs[primary_node].add(document_id)
        
        for replica in node.replica_nodes:
            self._node_to_docs[replica].add(document_id)
        
        # Calculate similarities if vectors provided
        if document_vectors and self._distance_func:
            self._update_similarities(document_id, document_vectors)
        
        return node
    
    def _update_similarities(
        self,
        document_id: str,
        document_vectors: Dict[str, Any]
    ) -> None:
        """Update similarity edges for a document."""
        # Would calculate similarities with existing documents
        # and update edges. Simplified for now.
        pass
    
    def add_similarity(
        self,
        doc_a: str,
        doc_b: str,
        similarity: float
    ) -> bool:
        """
        Add or update similarity between two documents.
        
        Args:
            doc_a: First document ID
            doc_b: Second document ID
            similarity: Similarity score (0-1)
            
        Returns:
            True if edge was added
        """
        if similarity < self.similarity_threshold:
            return False
        
        if doc_a not in self._nodes or doc_b not in self._nodes:
            return False
        
        # Store edge
        self._edges[doc_a].add(doc_b)
        self._edges[doc_b].add(doc_a)
        
        # Cache similarity
        key = tuple(sorted([doc_a, doc_b]))
        self._similarity_cache[key] = similarity
        
        # Update neighbor lists
        self._nodes[doc_a].neighbors[doc_b] = similarity
        self._nodes[doc_b].neighbors[doc_a] = similarity
        
        # Prune if too many neighbors
        self._prune_neighbors(doc_a)
        self._prune_neighbors(doc_b)
        
        return True
    
    def _prune_neighbors(self, document_id: str) -> None:
        """Keep only top-k neighbors."""
        node = self._nodes.get(document_id)
        if not node or len(node.neighbors) <= self.max_neighbors:
            return
        
        # Keep highest similarity neighbors
        sorted_neighbors = sorted(
            node.neighbors.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        keep = dict(sorted_neighbors[:self.max_neighbors])
        removed = set(node.neighbors.keys()) - set(keep.keys())
        
        node.neighbors = keep
        
        for doc_id in removed:
            self._edges[document_id].discard(doc_id)
            key = tuple(sorted([document_id, doc_id]))
            self._similarity_cache.pop(key, None)
    
    def remove_document(self, document_id: str) -> None:
        """Remove a document from the graph."""
        node = self._nodes.get(document_id)
        if not node:
            return
        
        # Remove from node index
        self._node_to_docs[node.primary_node].discard(document_id)
        for replica in node.replica_nodes:
            self._node_to_docs[replica].discard(document_id)
        
        # Remove edges
        for neighbor_id in list(self._edges[document_id]):
            self._edges[neighbor_id].discard(document_id)
            if neighbor_id in self._nodes:
                self._nodes[neighbor_id].neighbors.pop(document_id, None)
            key = tuple(sorted([document_id, neighbor_id]))
            self._similarity_cache.pop(key, None)
        
        del self._edges[document_id]
        del self._nodes[document_id]
    
    def get_document(self, document_id: str) -> Optional[DocumentNode]:
        """Get a document node."""
        return self._nodes.get(document_id)
    
    def get_similarity(self, doc_a: str, doc_b: str) -> float:
        """Get similarity between two documents."""
        key = tuple(sorted([doc_a, doc_b]))
        return self._similarity_cache.get(key, 0.0)
    
    def get_neighbors(
        self,
        document_id: str,
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Get most similar neighbors of a document.
        
        Args:
            document_id: Document to query
            limit: Maximum neighbors to return
            
        Returns:
            List of (doc_id, similarity) tuples
        """
        node = self._nodes.get(document_id)
        if not node:
            return []
        
        sorted_neighbors = sorted(
            node.neighbors.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_neighbors[:limit]
    
    def get_documents_on_node(self, cluster_node: str) -> Set[str]:
        """Get all document IDs on a cluster node."""
        return self._node_to_docs.get(cluster_node, set())
    
    def update_document_location(
        self,
        document_id: str,
        primary_node: Optional[str] = None,
        replica_nodes: Optional[List[str]] = None
    ) -> None:
        """Update the storage location of a document."""
        node = self._nodes.get(document_id)
        if not node:
            return
        
        # Update node index
        if primary_node and primary_node != node.primary_node:
            self._node_to_docs[node.primary_node].discard(document_id)
            self._node_to_docs[primary_node].add(document_id)
            node.primary_node = primary_node
        
        if replica_nodes is not None:
            # Remove from old replicas
            for old_replica in node.replica_nodes:
                if old_replica not in replica_nodes:
                    self._node_to_docs[old_replica].discard(document_id)
            
            # Add to new replicas
            for new_replica in replica_nodes:
                self._node_to_docs[new_replica].add(document_id)
            
            node.replica_nodes = replica_nodes
    
    def find_best_replica_nodes(
        self,
        document_id: str,
        candidate_nodes: List[str],
        num_replicas: int = 1,
        exclude_primary: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Find best nodes for replicas based on semantic affinity.
        
        Args:
            document_id: Document to replicate
            candidate_nodes: Available cluster nodes
            num_replicas: Number of replicas needed
            exclude_primary: Exclude primary node from candidates
            
        Returns:
            List of (node_id, affinity_score) tuples
        """
        node = self._nodes.get(document_id)
        if not node:
            return []
        
        # Get document's neighbors
        neighbors = self.get_neighbors(document_id, limit=50)
        
        # Score each candidate node
        node_scores: Dict[str, float] = {}
        
        for candidate in candidate_nodes:
            if exclude_primary and candidate == node.primary_node:
                continue
            if candidate in node.replica_nodes:
                continue
            
            # Calculate affinity: how many similar documents are on this node
            node_docs = self.get_documents_on_node(candidate)
            
            affinity = 0.0
            for neighbor_id, similarity in neighbors:
                if neighbor_id in node_docs:
                    affinity += similarity
            
            node_scores[candidate] = affinity
        
        # Sort by affinity (descending)
        sorted_nodes = sorted(
            node_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_nodes[:num_replicas]
    
    def get_cluster_affinity_matrix(
        self,
        cluster_nodes: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate affinity matrix between cluster nodes.
        
        Shows how semantically related documents on different nodes are.
        
        Args:
            cluster_nodes: List of cluster node IDs
            
        Returns:
            Matrix as nested dict: node_a -> node_b -> affinity
        """
        matrix = {n: {m: 0.0 for m in cluster_nodes} for n in cluster_nodes}
        
        # For each edge, if endpoints are on different nodes, add to affinity
        for doc_a, neighbors in self._edges.items():
            node_a_info = self._nodes.get(doc_a)
            if not node_a_info:
                continue
            
            nodes_a = set(node_a_info.all_nodes)
            
            for doc_b in neighbors:
                node_b_info = self._nodes.get(doc_b)
                if not node_b_info:
                    continue
                
                nodes_b = set(node_b_info.all_nodes)
                similarity = self.get_similarity(doc_a, doc_b)
                
                for na in nodes_a:
                    for nb in nodes_b:
                        if na in matrix and nb in matrix[na]:
                            matrix[na][nb] += similarity
        
        return matrix
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        total_edges = sum(len(neighbors) for neighbors in self._edges.values()) // 2
        
        neighbor_counts = [len(n.neighbors) for n in self._nodes.values()]
        
        return {
            "total_documents": len(self._nodes),
            "total_edges": total_edges,
            "avg_neighbors": np.mean(neighbor_counts) if neighbor_counts else 0,
            "max_neighbors": max(neighbor_counts) if neighbor_counts else 0,
            "min_neighbors": min(neighbor_counts) if neighbor_counts else 0,
            "nodes_with_documents": len(self._node_to_docs),
            "similarity_threshold": self.similarity_threshold
        }
