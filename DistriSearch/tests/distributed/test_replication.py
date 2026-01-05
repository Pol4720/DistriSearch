# -*- coding: utf-8 -*-
"""
Replication Tests

Tests to verify document replication functionality:
- Adaptive replication factor based on cluster size
- Replica placement and tracking
- Replication priority (affinity-based)
- Failure handling during replication
- Replica consistency and repair
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.core.replication.adaptive_replicator import (
    AdaptiveReplicator,
    AdaptiveReplicationConfig,
)
from app.core.replication.affinity_replicator import (
    AffinityReplicator,
    ReplicationConfig,
    ReplicationPriority,
    ReplicationTask,
)
from app.core.replication.replica_tracker import (
    ReplicaTracker,
    DocumentReplicas,
    ReplicaStatus,
    ReplicaInfo,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def replication_config() -> ReplicationConfig:
    """Create replication configuration."""
    return ReplicationConfig(
        replication_factor=2,
        max_concurrent_replications=5,
        replication_timeout_sec=30.0,
    )


@pytest.fixture
def adaptive_config() -> AdaptiveReplicationConfig:
    """Create adaptive replication configuration."""
    return AdaptiveReplicationConfig(
        target_replication_factor=2,
        min_replication_factor=1,
        max_concurrent_replications=5,
    )


@pytest.fixture
def replica_tracker() -> ReplicaTracker:
    """Create replica tracker."""
    return ReplicaTracker()


@pytest.fixture
async def adaptive_replicator(adaptive_config) -> AdaptiveReplicator:
    """Create adaptive replicator with mocked functions."""
    mock_replicate = AsyncMock(return_value=True)
    mock_get_vectors = AsyncMock(return_value={"tfidf": [0.1, 0.2], "minhash": [1, 2, 3]})
    
    replicator = AdaptiveReplicator(
        config=adaptive_config,
        replicate_func=mock_replicate,
        get_document_vectors=mock_get_vectors,
    )
    return replicator


# ============================================================================
# Adaptive Replication Factor Tests
# ============================================================================

class TestAdaptiveReplicationFactor:
    """Tests for adaptive replication factor adjustment."""
    
    def test_single_node_no_replication(self, adaptive_config):
        """Test that single node has no replication."""
        adaptive_config.update_for_nodes(1)
        
        assert adaptive_config.effective_replication_factor == 0
    
    def test_two_nodes_one_replica(self, adaptive_config):
        """Test that two nodes allows one replica."""
        adaptive_config.update_for_nodes(2)
        
        assert adaptive_config.effective_replication_factor == 1
    
    def test_three_nodes_target_replicas(self, adaptive_config):
        """Test that three+ nodes uses target replication factor."""
        adaptive_config.update_for_nodes(3)
        
        # With target=2 and 3 nodes, should have 2 replicas
        assert adaptive_config.effective_replication_factor == 2
    
    def test_many_nodes_capped_at_target(self, adaptive_config):
        """Test that replication factor doesn't exceed target."""
        adaptive_config.update_for_nodes(10)
        
        # Should not exceed target of 2
        assert adaptive_config.effective_replication_factor == 2
    
    def test_replication_factor_decreases_on_node_loss(self, adaptive_config):
        """Test that replication factor decreases when nodes leave."""
        # Start with 5 nodes
        adaptive_config.update_for_nodes(5)
        assert adaptive_config.effective_replication_factor == 2
        
        # Down to 2 nodes
        changes = adaptive_config.update_for_nodes(2)
        
        assert adaptive_config.effective_replication_factor == 1
        assert "replication_factor" in changes
    
    def test_replication_factor_increases_on_node_join(self, adaptive_config):
        """Test that replication factor increases when nodes join."""
        # Start with 2 nodes
        adaptive_config.update_for_nodes(2)
        assert adaptive_config.effective_replication_factor == 1
        
        # Up to 4 nodes
        changes = adaptive_config.update_for_nodes(4)
        
        assert adaptive_config.effective_replication_factor == 2
        assert "replication_factor" in changes


# ============================================================================
# Replica Tracker Tests
# ============================================================================

class TestReplicaTracker:
    """Tests for replica tracking."""
    
    def test_register_document(self, replica_tracker):
        """Test registering a document with primary."""
        doc_id = "doc-1"
        node_id = "node-1"
        
        doc_replicas = replica_tracker.register_document(
            document_id=doc_id,
            primary_node=node_id,
        )
        
        assert doc_replicas is not None
        assert doc_replicas.primary is not None
        assert doc_replicas.primary.node_id == node_id
        assert doc_replicas.primary.is_primary
    
    def test_add_replica(self, replica_tracker):
        """Test adding replica to existing document."""
        doc_id = "doc-1"
        
        replica_tracker.register_document(doc_id, "node-1")
        replica = replica_tracker.add_replica(doc_id, "node-2")
        
        assert replica is not None
        assert replica.node_id == "node-2"
        assert not replica.is_primary
        
        doc = replica_tracker.get_document_replicas(doc_id)
        assert len(doc.replicas) == 1
    
    def test_remove_replica(self, replica_tracker):
        """Test removing replica."""
        doc_id = "doc-1"
        
        replica_tracker.register_document(doc_id, "node-1")
        replica_tracker.add_replica(doc_id, "node-2")
        replica_tracker.add_replica(doc_id, "node-3")
        
        removed = replica_tracker.remove_replica(doc_id, "node-2")
        
        assert removed
        doc = replica_tracker.get_document_replicas(doc_id)
        assert "node-2" not in doc.all_nodes
        assert "node-3" in doc.all_nodes
    
    def test_get_all_nodes_for_document(self, replica_tracker):
        """Test getting all nodes that have a document."""
        doc_id = "doc-1"
        
        replica_tracker.register_document(doc_id, "node-1")
        replica_tracker.add_replica(doc_id, "node-2")
        replica_tracker.add_replica(doc_id, "node-3")
        
        doc = replica_tracker.get_document_replicas(doc_id)
        nodes = doc.all_nodes
        
        assert "node-1" in nodes
        assert "node-2" in nodes
        assert "node-3" in nodes
    
    def test_get_replicas_on_node(self, replica_tracker):
        """Test getting all replicas on a node."""
        replica_tracker.register_document("doc-1", "node-1")
        replica_tracker.register_document("doc-2", "node-1")
        replica_tracker.register_document("doc-3", "node-2")
        replica_tracker.add_replica("doc-3", "node-1")
        
        replicas = replica_tracker.get_replicas_on_node("node-1")
        doc_ids = [r.document_id for r in replicas]
        
        assert "doc-1" in doc_ids
        assert "doc-2" in doc_ids
        assert "doc-3" in doc_ids
    
    def test_replica_count(self, replica_tracker):
        """Test counting replicas for a document."""
        doc_id = "doc-1"
        
        replica_tracker.register_document(doc_id, "node-1")
        doc = replica_tracker.get_document_replicas(doc_id)
        assert doc.healthy_count == 1  # Just primary
        
        replica_tracker.add_replica(doc_id, "node-2")
        doc = replica_tracker.get_document_replicas(doc_id)
        assert doc.healthy_count == 2
        
        replica_tracker.add_replica(doc_id, "node-3")
        doc = replica_tracker.get_document_replicas(doc_id)
        assert doc.healthy_count == 3
    
    def test_under_replicated_documents(self, replica_tracker):
        """Test finding under-replicated documents."""
        # doc-1: 1 copy (primary only) - under-replicated
        replica_tracker.register_document("doc-1", "node-1", replication_factor=2)
        
        # doc-2: 2 copies - adequately replicated
        replica_tracker.register_document("doc-2", "node-1", replication_factor=2)
        replica_tracker.add_replica("doc-2", "node-2")
        
        # doc-3: 3 copies - adequately replicated
        replica_tracker.register_document("doc-3", "node-1", replication_factor=2)
        replica_tracker.add_replica("doc-3", "node-2")
        replica_tracker.add_replica("doc-3", "node-3")
        
        # Check under-replication
        doc1 = replica_tracker.get_document_replicas("doc-1")
        doc2 = replica_tracker.get_document_replicas("doc-2")
        doc3 = replica_tracker.get_document_replicas("doc-3")
        
        assert doc1.is_under_replicated
        assert not doc2.is_under_replicated
        assert not doc3.is_under_replicated


# ============================================================================
# Affinity-Based Replication Tests
# ============================================================================

class TestAffinityReplication:
    """Tests for affinity-based replica placement."""
    
    def test_replication_config(self, replication_config):
        """Test replication configuration."""
        assert replication_config.replication_factor == 2
        assert replication_config.max_concurrent_replications == 5
        assert replication_config.replication_timeout_sec == 30.0
    
    def test_replication_task_creation(self):
        """Test creating a replication task."""
        import uuid
        task = ReplicationTask(
            task_id=str(uuid.uuid4()),
            document_id="doc-1",
            source_node="node-1",
            target_node="node-2",
            priority=ReplicationPriority.NORMAL,
        )
        
        assert task.document_id == "doc-1"
        assert task.source_node == "node-1"
        assert task.target_node == "node-2"
        assert task.priority == ReplicationPriority.NORMAL
        assert task.status == "pending"
    
    def test_replication_priority_ordering(self):
        """Test that replication priorities are correctly ordered."""
        assert ReplicationPriority.CRITICAL.value > ReplicationPriority.HIGH.value
        assert ReplicationPriority.HIGH.value > ReplicationPriority.NORMAL.value
        assert ReplicationPriority.NORMAL.value > ReplicationPriority.LOW.value


# ============================================================================
# Replica Info Tests
# ============================================================================

class TestReplicaInfo:
    """Tests for replica information."""
    
    def test_replica_info_creation(self):
        """Test creating replica info."""
        replica = ReplicaInfo(
            document_id="doc-1",
            node_id="node-1",
            is_primary=True,
            status=ReplicaStatus.ACTIVE,
            version=1,
        )
        
        assert replica.document_id == "doc-1"
        assert replica.node_id == "node-1"
        assert replica.is_primary
        assert replica.is_healthy
    
    def test_replica_health_states(self):
        """Test replica health based on status."""
        active = ReplicaInfo(
            document_id="doc-1",
            node_id="node-1",
            is_primary=True,
            status=ReplicaStatus.ACTIVE,
        )
        syncing = ReplicaInfo(
            document_id="doc-1",
            node_id="node-2",
            is_primary=False,
            status=ReplicaStatus.SYNCING,
        )
        failed = ReplicaInfo(
            document_id="doc-1",
            node_id="node-3",
            is_primary=False,
            status=ReplicaStatus.FAILED,
        )
        stale = ReplicaInfo(
            document_id="doc-1",
            node_id="node-4",
            is_primary=False,
            status=ReplicaStatus.STALE,
        )
        
        assert active.is_healthy
        assert syncing.is_healthy
        assert not failed.is_healthy
        assert not stale.is_healthy


# ============================================================================
# Document Replicas Tests
# ============================================================================

class TestDocumentReplicas:
    """Tests for document replicas container."""
    
    def test_document_replicas_creation(self):
        """Test creating document replicas container."""
        primary = ReplicaInfo(
            document_id="doc-1",
            node_id="node-1",
            is_primary=True,
        )
        
        doc = DocumentReplicas(
            document_id="doc-1",
            primary=primary,
            replication_factor=2,
        )
        
        assert doc.document_id == "doc-1"
        assert doc.primary is not None
        assert doc.healthy_count == 1
    
    def test_all_replicas_property(self):
        """Test getting all replicas including primary."""
        primary = ReplicaInfo(document_id="doc-1", node_id="node-1", is_primary=True)
        replica1 = ReplicaInfo(document_id="doc-1", node_id="node-2", is_primary=False)
        replica2 = ReplicaInfo(document_id="doc-1", node_id="node-3", is_primary=False)
        
        doc = DocumentReplicas(
            document_id="doc-1",
            primary=primary,
            replicas=[replica1, replica2],
            replication_factor=2,
        )
        
        all_replicas = doc.all_replicas
        assert len(all_replicas) == 3
        assert primary in all_replicas
        assert replica1 in all_replicas
        assert replica2 in all_replicas


# ============================================================================
# Adaptive Replicator Tests
# ============================================================================

class TestAdaptiveReplicator:
    """Tests for adaptive replicator."""
    
    @pytest.mark.asyncio
    async def test_adaptive_replicator_creation(self, adaptive_replicator):
        """Test creating adaptive replicator."""
        assert adaptive_replicator is not None
        assert adaptive_replicator.config is not None
    
    @pytest.mark.asyncio
    async def test_config_update_for_nodes(self, adaptive_replicator):
        """Test configuration update when nodes change."""
        # Start with 2 nodes
        changes = adaptive_replicator.config.update_for_nodes(2)
        assert adaptive_replicator.config.effective_replication_factor == 1
        
        # Add nodes
        changes = adaptive_replicator.config.update_for_nodes(5)
        assert adaptive_replicator.config.effective_replication_factor == 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestReplicationIntegration:
    """Integration tests for replication system."""
    
    @pytest.mark.asyncio
    async def test_full_document_registration_cycle(self, replica_tracker):
        """Test complete document registration with replicas."""
        doc_id = "new-doc"
        
        # Register document with primary
        doc = replica_tracker.register_document(
            document_id=doc_id,
            primary_node="node-1",
            replica_nodes=["node-2"],
            replication_factor=2,
        )
        
        assert doc is not None
        assert doc.primary is not None
        assert len(doc.replicas) == 1
        assert not doc.is_under_replicated
    
    @pytest.mark.asyncio
    async def test_replica_tracker_node_operations(self, replica_tracker):
        """Test replica tracker operations across nodes."""
        # Register multiple documents
        replica_tracker.register_document("doc-1", "node-1")
        replica_tracker.register_document("doc-2", "node-1")
        replica_tracker.register_document("doc-3", "node-2")
        
        # Add replicas
        replica_tracker.add_replica("doc-1", "node-2")
        replica_tracker.add_replica("doc-2", "node-2")
        replica_tracker.add_replica("doc-3", "node-1")
        
        # Verify node-1 replicas
        node1_replicas = replica_tracker.get_replicas_on_node("node-1")
        assert len(node1_replicas) == 3
        
        # Verify node-2 replicas
        node2_replicas = replica_tracker.get_replicas_on_node("node-2")
        assert len(node2_replicas) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
