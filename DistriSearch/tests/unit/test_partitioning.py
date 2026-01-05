# -*- coding: utf-8 -*-
"""
Unit Tests for Partitioning Module

Tests VP-Tree partitioning, node assignment, and partition management.
"""

import pytest
import numpy as np
from typing import List, Dict, Any, Set
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.core.partitioning.vp_tree import VPTree, VPNode, VantagePointSelection
from app.core.partitioning.node_assignment import (
    NodeAssigner,
    NodeStats,
    AssignmentStrategy,
    AssignmentResult,
)
from app.core.partitioning.partition_manager import (
    PartitionManager,
    PartitionInfo,
    RoutingResult,
)
from app.core.partitioning.distance_metrics import DistanceCalculator, DistanceWeights


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def node_ids() -> List[str]:
    """Sample node IDs."""
    return ["node-1", "node-2", "node-3", "node-4", "node-5"]


@pytest.fixture
def sample_documents() -> List[Dict[str, Any]]:
    """Sample documents with vector representations."""
    np.random.seed(42)
    return [
        {
            "id": f"doc-{i}",
            "title": f"Document {i}",
            "content": f"Content for document {i}",
            # Expected keys for DistanceCalculator.weighted_distance()
            "name_vector": np.random.rand(100).tolist(),
            "minhash_signature": list(np.random.randint(0, 1000, 100)),
            "topic_distribution": np.random.rand(10).tolist(),
            # Keep legacy keys for compatibility
            "tfidf_vector": np.random.rand(100).tolist(),
            "lda_topics": np.random.rand(10).tolist(),
        }
        for i in range(100)
    ]


@pytest.fixture
def distance_calculator() -> DistanceCalculator:
    """Create distance calculator."""
    return DistanceCalculator()


@pytest.fixture
def node_assigner(distance_calculator) -> NodeAssigner:
    """Create node assigner."""
    return NodeAssigner(
        distance_calculator=distance_calculator,
        replication_factor=2,
    )


@pytest.fixture
def vp_tree(distance_calculator) -> VPTree:
    """Create VP-Tree."""
    return VPTree(
        distance_calculator=distance_calculator,
        leaf_size=10,
        selection_strategy=VantagePointSelection.K_MEDOIDS
    )


@pytest.fixture
def partition_manager() -> PartitionManager:
    """Create partition manager."""
    return PartitionManager(
        leaf_size=10,
        replication_factor=2,
    )


# ============================================================================
# VPNode Tests
# ============================================================================

class TestVPNode:
    """Tests for VP-Tree node structure."""
    
    def test_leaf_node_creation(self):
        """Test creating a leaf node."""
        node = VPNode(
            node_id="leaf-1",
            depth=2,
            documents=[{"id": "doc-1"}, {"id": "doc-2"}]
        )
        
        assert node.is_leaf
        assert node.size == 2
        assert node.node_id == "leaf-1"
        assert node.depth == 2
    
    def test_internal_node_creation(self):
        """Test creating an internal node with children."""
        left = VPNode(node_id="left-1", documents=[{"id": "doc-1"}])
        right = VPNode(node_id="right-1", documents=[{"id": "doc-2"}])
        
        parent = VPNode(
            node_id="parent-1",
            vantage_point={"id": "vp-1"},
            vantage_id="vp-1",
            median_distance=0.5,
            left=left,
            right=right,
            depth=1
        )
        
        assert not parent.is_leaf
        assert parent.size == 3  # vp + left + right
    
    def test_node_serialization(self):
        """Test node serialization to dict."""
        node = VPNode(
            node_id="node-1",
            vantage_id="vp-1",
            median_distance=0.5,
            depth=0,
            assigned_node="cluster-node-1"
        )
        
        data = node.to_dict()
        
        assert data["node_id"] == "node-1"
        assert data["vantage_id"] == "vp-1"
        assert data["median_distance"] == 0.5
        assert data["assigned_node"] == "cluster-node-1"


# ============================================================================
# NodeStats Tests
# ============================================================================

class TestNodeStats:
    """Tests for node statistics."""
    
    def test_node_stats_creation(self):
        """Test creating node stats."""
        stats = NodeStats(
            node_id="node-1",
            document_count=5000,
            capacity=10000,
            is_healthy=True
        )
        
        assert stats.node_id == "node-1"
        assert stats.document_count == 5000
        assert stats.capacity == 10000
    
    def test_load_factor_calculation(self):
        """Test load factor calculation."""
        stats = NodeStats(
            node_id="node-1",
            document_count=5000,
            capacity=10000
        )
        
        assert stats.load_factor == 0.5
    
    def test_available_capacity(self):
        """Test available capacity calculation."""
        stats = NodeStats(
            node_id="node-1",
            document_count=7000,
            capacity=10000
        )
        
        assert stats.available_capacity == 3000
    
    def test_full_node_load_factor(self):
        """Test load factor for full node."""
        stats = NodeStats(
            node_id="node-1",
            document_count=10000,
            capacity=10000
        )
        
        assert stats.load_factor == 1.0
        assert stats.available_capacity == 0


# ============================================================================
# NodeAssigner Tests
# ============================================================================

class TestNodeAssigner:
    """Tests for node assignment."""
    
    def test_register_node(self, node_assigner, node_ids):
        """Test registering nodes."""
        for node_id in node_ids:
            node_assigner.register_node(node_id, capacity=10000)
        
        healthy = node_assigner.get_healthy_nodes()
        assert len(healthy) == 5
    
    def test_unregister_node(self, node_assigner, node_ids):
        """Test unregistering a node."""
        for node_id in node_ids:
            node_assigner.register_node(node_id, capacity=10000)
        
        node_assigner.unregister_node("node-1")
        
        healthy = node_assigner.get_healthy_nodes()
        assert len(healthy) == 4
        assert not any(n.node_id == "node-1" for n in healthy)
    
    def test_get_node_stats(self, node_assigner):
        """Test getting node stats."""
        node_assigner.register_node("node-1", capacity=10000)
        
        stats = node_assigner.get_node_stats("node-1")
        
        assert stats is not None
        assert stats.node_id == "node-1"
        assert stats.capacity == 10000


# ============================================================================
# DistanceCalculator Tests
# ============================================================================

class TestDistanceCalculator:
    """Tests for distance calculation."""
    
    def test_distance_calculation(self, distance_calculator, sample_documents):
        """Test calculating distance between documents."""
        doc1 = sample_documents[0]
        doc2 = sample_documents[1]
        
        distance = distance_calculator.weighted_distance(doc1, doc2)
        
        assert isinstance(distance, float)
        assert 0 <= distance <= 1  # Normalized distance
    
    def test_same_document_zero_distance(self, distance_calculator, sample_documents):
        """Test that same document has zero distance."""
        doc = sample_documents[0]
        
        distance = distance_calculator.weighted_distance(doc, doc)
        
        assert distance < 0.001  # Essentially zero


# ============================================================================
# VPTree Tests
# ============================================================================

class TestVPTree:
    """Tests for VP-Tree construction and operations."""
    
    def test_vp_tree_initialization(self, vp_tree):
        """Test VP-Tree initialization."""
        assert vp_tree is not None
        assert vp_tree.leaf_size == 10
    
    def test_build_tree(self, vp_tree, sample_documents):
        """Test building VP-Tree from documents."""
        vp_tree.build(sample_documents)
        
        assert vp_tree.root is not None
        stats = vp_tree.get_statistics()
        assert stats["total_documents"] == len(sample_documents)
    
    def test_nearest_neighbors(self, vp_tree, sample_documents):
        """Test finding nearest neighbors."""
        vp_tree.build(sample_documents)
        
        query_doc = sample_documents[0]
        neighbors = vp_tree.search_knn(query_doc, k=5)
        
        assert len(neighbors) <= 5
        # First result should be the query document itself
        assert neighbors[0][0]["id"] == query_doc["id"]
    
    def test_get_leaf_partitions(self, vp_tree, sample_documents):
        """Test getting all leaf partitions."""
        vp_tree.build(sample_documents)
        
        leaves = vp_tree.get_leaf_partitions()
        
        assert len(leaves) > 0
        total_docs = sum(len(leaf.documents) for leaf in leaves)
        assert total_docs == len(sample_documents)


# ============================================================================
# PartitionManager Tests
# ============================================================================

class TestPartitionManager:
    """Tests for partition management."""
    
    def test_partition_manager_initialization(self, partition_manager):
        """Test partition manager initialization."""
        assert partition_manager is not None
        assert partition_manager.leaf_size == 10
        assert partition_manager.replication_factor == 2
    
    def test_register_node(self, partition_manager, node_ids):
        """Test registering nodes with partition manager."""
        for node_id in node_ids:
            partition_manager.register_node(node_id, capacity=10000)
        
        # Nodes should be registered
        healthy = partition_manager.node_assigner.get_healthy_nodes()
        assert len(healthy) == 5
    
    def test_build_partitions(self, partition_manager, sample_documents, node_ids):
        """Test building partitions from documents."""
        # Register nodes first
        for node_id in node_ids:
            partition_manager.register_node(node_id, capacity=10000)
        
        # Build partitions
        stats = partition_manager.build_partitions(sample_documents, node_ids)
        
        assert "total_documents" in stats or partition_manager._initialized
    
    def test_route_document(self, partition_manager, sample_documents, node_ids):
        """Test routing a document to a node."""
        # Setup
        for node_id in node_ids:
            partition_manager.register_node(node_id, capacity=10000)
        partition_manager.build_partitions(sample_documents, node_ids)
        
        # Route a new document
        new_doc = {
            "id": "new-doc",
            "tfidf_vector": np.random.rand(100).tolist(),
            "minhash_signature": list(np.random.randint(0, 1000, 100)),
            "lda_topics": np.random.rand(10).tolist(),
        }
        
        result = partition_manager.route_document(new_doc)
        
        assert isinstance(result, RoutingResult)
        assert result.primary_node in node_ids


# ============================================================================
# Assignment Strategy Tests
# ============================================================================

class TestAssignmentStrategies:
    """Tests for different assignment strategies."""
    
    def test_round_robin_assignment(self, node_assigner, node_ids, sample_documents):
        """Test round-robin assignment distributes evenly."""
        for node_id in node_ids:
            node_assigner.register_node(node_id, capacity=10000)
        
        # Assign documents using round robin
        assignments: Dict[str, int] = {node_id: 0 for node_id in node_ids}
        
        for i, doc in enumerate(sample_documents):
            result = node_assigner.assign_document(
                doc,
                strategy=AssignmentStrategy.ROUND_ROBIN
            )
            assignments[result.assigned_node] += 1
        
        # Should be roughly evenly distributed
        expected = len(sample_documents) / len(node_ids)
        for count in assignments.values():
            assert abs(count - expected) <= 2
    
    def test_least_loaded_assignment(self, node_assigner, node_ids):
        """Test least-loaded assignment."""
        # Register nodes with different loads
        node_assigner.register_node("node-1", capacity=10000)
        node_assigner.register_node("node-2", capacity=10000)
        
        # Add documents to node-1 to make it more loaded
        for i in range(50):
            node_assigner._node_documents["node-1"].append({"id": f"doc-{i}"})
        node_assigner._nodes["node-1"].document_count = 50
        
        # New document should go to node-2 (least loaded)
        result = node_assigner.assign_document(
            {"id": "new-doc"},
            strategy=AssignmentStrategy.LEAST_LOADED
        )
        
        assert result.assigned_node == "node-2"


# ============================================================================
# Integration Tests
# ============================================================================

class TestPartitioningIntegration:
    """Integration tests for partitioning system."""
    
    def test_full_partitioning_workflow(self, sample_documents, node_ids):
        """Test complete partitioning workflow."""
        # Create partition manager
        manager = PartitionManager(
            leaf_size=10,
            replication_factor=2
        )
        
        # Register nodes
        for node_id in node_ids:
            manager.register_node(node_id, capacity=10000)
        
        # Build partitions
        manager.build_partitions(sample_documents, node_ids)
        
        # Route new documents
        new_docs = [
            {
                "id": f"new-{i}",
                "tfidf_vector": np.random.rand(100).tolist(),
                "minhash_signature": list(np.random.randint(0, 1000, 100)),
                "lda_topics": np.random.rand(10).tolist(),
            }
            for i in range(10)
        ]
        
        for doc in new_docs:
            result = manager.route_document(doc)
            assert result.primary_node in node_ids
            assert len(result.replica_nodes) <= manager.replication_factor


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
