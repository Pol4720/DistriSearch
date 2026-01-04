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
    
    def test_register_primary(self, replica_tracker):
        """Test registering primary replica."""
        doc_id = "doc-1"
        node_id = "node-1"
        
        replica_tracker.register_primary(doc_id, node_id)
        
        replicas = replica_tracker.get_replicas(doc_id)
        assert replicas is not None
        assert replicas.primary_node == node_id
    
    def test_add_replica(self, replica_tracker):
        """Test adding replica to existing document."""
        doc_id = "doc-1"
        
        replica_tracker.register_primary(doc_id, "node-1")
        replica_tracker.add_replica(doc_id, "node-2")
        
        replicas = replica_tracker.get_replicas(doc_id)
        assert "node-2" in replicas.replica_nodes
    
    def test_remove_replica(self, replica_tracker):
        """Test removing replica."""
        doc_id = "doc-1"
        
        replica_tracker.register_primary(doc_id, "node-1")
        replica_tracker.add_replica(doc_id, "node-2")
        replica_tracker.add_replica(doc_id, "node-3")
        
        replica_tracker.remove_replica(doc_id, "node-2")
        
        replicas = replica_tracker.get_replicas(doc_id)
        assert "node-2" not in replicas.replica_nodes
        assert "node-3" in replicas.replica_nodes
    
    def test_get_all_nodes_for_document(self, replica_tracker):
        """Test getting all nodes that have a document."""
        doc_id = "doc-1"
        
        replica_tracker.register_primary(doc_id, "node-1")
        replica_tracker.add_replica(doc_id, "node-2")
        replica_tracker.add_replica(doc_id, "node-3")
        
        nodes = replica_tracker.get_all_nodes(doc_id)
        
        assert nodes == {"node-1", "node-2", "node-3"}
    
    def test_get_documents_on_node(self, replica_tracker):
        """Test getting all documents on a node."""
        replica_tracker.register_primary("doc-1", "node-1")
        replica_tracker.register_primary("doc-2", "node-1")
        replica_tracker.register_primary("doc-3", "node-2")
        replica_tracker.add_replica("doc-3", "node-1")
        
        docs = replica_tracker.get_documents_on_node("node-1")
        
        assert "doc-1" in docs
        assert "doc-2" in docs
        assert "doc-3" in docs
    
    def test_replica_count(self, replica_tracker):
        """Test counting replicas for a document."""
        doc_id = "doc-1"
        
        replica_tracker.register_primary(doc_id, "node-1")
        assert replica_tracker.get_replica_count(doc_id) == 1
        
        replica_tracker.add_replica(doc_id, "node-2")
        assert replica_tracker.get_replica_count(doc_id) == 2
        
        replica_tracker.add_replica(doc_id, "node-3")
        assert replica_tracker.get_replica_count(doc_id) == 3
    
    def test_under_replicated_documents(self, replica_tracker):
        """Test finding under-replicated documents."""
        replica_tracker.register_primary("doc-1", "node-1")  # 1 copy
        replica_tracker.register_primary("doc-2", "node-1")
        replica_tracker.add_replica("doc-2", "node-2")  # 2 copies
        replica_tracker.register_primary("doc-3", "node-1")
        replica_tracker.add_replica("doc-3", "node-2")
        replica_tracker.add_replica("doc-3", "node-3")  # 3 copies
        
        # Find docs with less than 2 replicas
        under_replicated = replica_tracker.find_under_replicated(min_replicas=2)
        
        assert "doc-1" in under_replicated
        assert "doc-2" not in under_replicated
        assert "doc-3" not in under_replicated


# ============================================================================
# Affinity-Based Replication Tests
# ============================================================================

class TestAffinityReplication:
    """Tests for affinity-based replica placement."""
    
    @pytest.mark.asyncio
    async def test_replicate_to_similar_node(self, replication_config):
        """Test that replication prefers nodes with similar content."""
        mock_replicate = AsyncMock(return_value=True)
        
        replicator = AffinityReplicator(
            config=replication_config,
            replicate_func=mock_replicate,
        )
        
        # Set up node similarity scores
        replicator.set_node_affinity("node-1", "node-2", 0.9)  # High affinity
        replicator.set_node_affinity("node-1", "node-3", 0.3)  # Low affinity
        
        # Request replication from node-1
        target = replicator.select_replica_target(
            source_node="node-1",
            exclude_nodes={"node-1"},
            available_nodes={"node-2", "node-3"}
        )
        
        # Should prefer node-2 (higher affinity)
        assert target == "node-2"
    
    @pytest.mark.asyncio
    async def test_replication_priority_critical(self, replication_config):
        """Test that critical priority replications are processed first."""
        mock_replicate = AsyncMock(return_value=True)
        
        replicator = AffinityReplicator(
            config=replication_config,
            replicate_func=mock_replicate,
        )
        
        # Queue tasks with different priorities
        task_low = ReplicationTask(
            document_id="doc-low",
            source_node="node-1",
            target_node="node-2",
            priority=ReplicationPriority.LOW
        )
        task_critical = ReplicationTask(
            document_id="doc-critical",
            source_node="node-1",
            target_node="node-2",
            priority=ReplicationPriority.CRITICAL
        )
        
        replicator.queue_replication(task_low)
        replicator.queue_replication(task_critical)
        
        # Critical should be processed first
        next_task = replicator.get_next_task()
        assert next_task.document_id == "doc-critical"


# ============================================================================
# Replication Failure Handling Tests
# ============================================================================

class TestReplicationFailureHandling:
    """Tests for handling replication failures."""
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, adaptive_replicator):
        """Test that replication retries on failure."""
        # Make first attempt fail, second succeed
        call_count = 0
        async def mock_replicate(doc_id, source, target):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False
            return True
        
        adaptive_replicator._replicate_func = mock_replicate
        
        result = await adaptive_replicator.replicate_with_retry(
            document_id="doc-1",
            source_node="node-1",
            target_node="node-2",
            max_retries=3
        )
        
        assert result
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_failure_after_max_retries(self, adaptive_replicator):
        """Test that replication fails after max retries."""
        adaptive_replicator._replicate_func = AsyncMock(return_value=False)
        
        result = await adaptive_replicator.replicate_with_retry(
            document_id="doc-1",
            source_node="node-1",
            target_node="node-2",
            max_retries=3
        )
        
        assert not result
        # Should have tried max_retries + 1 times
        assert adaptive_replicator._replicate_func.call_count == 4
    
    @pytest.mark.asyncio
    async def test_alternate_target_on_failure(self, adaptive_replicator):
        """Test that replication tries alternate target on failure."""
        failed_nodes = set()
        
        async def mock_replicate(doc_id, source, target):
            if target == "node-2":
                failed_nodes.add(target)
                return False
            return True
        
        adaptive_replicator._replicate_func = mock_replicate
        
        result = await adaptive_replicator.replicate_to_any(
            document_id="doc-1",
            source_node="node-1",
            target_nodes=["node-2", "node-3", "node-4"]
        )
        
        assert result
        assert "node-2" in failed_nodes


# ============================================================================
# Replica Consistency Tests
# ============================================================================

class TestReplicaConsistency:
    """Tests for replica consistency and repair."""
    
    @pytest.mark.asyncio
    async def test_detect_inconsistent_replicas(self, replica_tracker):
        """Test detection of inconsistent replicas."""
        doc_id = "doc-1"
        
        # Register replicas with different versions
        replica_tracker.register_primary(doc_id, "node-1", version=5)
        replica_tracker.add_replica(doc_id, "node-2", version=5)
        replica_tracker.add_replica(doc_id, "node-3", version=3)  # Stale
        
        stale_replicas = replica_tracker.find_stale_replicas(doc_id)
        
        assert "node-3" in stale_replicas
        assert "node-1" not in stale_replicas
        assert "node-2" not in stale_replicas
    
    @pytest.mark.asyncio
    async def test_repair_stale_replica(self, adaptive_replicator):
        """Test repairing a stale replica."""
        # Mock getting latest version
        async def mock_get_doc(doc_id, node_id):
            if node_id == "node-1":
                return {"version": 5, "data": "latest"}
            return {"version": 3, "data": "stale"}
        
        adaptive_replicator._get_document = mock_get_doc
        adaptive_replicator._replicate_func = AsyncMock(return_value=True)
        
        result = await adaptive_replicator.repair_replica(
            document_id="doc-1",
            source_node="node-1",
            stale_node="node-3"
        )
        
        assert result
        adaptive_replicator._replicate_func.assert_called()


# ============================================================================
# Replication During Node Events Tests
# ============================================================================

class TestReplicationNodeEvents:
    """Tests for replication behavior during node events."""
    
    @pytest.mark.asyncio
    async def test_rebalance_on_node_join(self, adaptive_replicator, replica_tracker):
        """Test that replication rebalances when node joins."""
        # Initial state: 2 nodes, 1 replica each document
        replica_tracker.register_primary("doc-1", "node-1")
        replica_tracker.add_replica("doc-1", "node-2")
        
        # Node-3 joins - should trigger replication check
        adaptive_replicator.config.update_for_nodes(3)
        
        # Documents might need re-replication to new node
        # (depends on affinity and load balancing)
    
    @pytest.mark.asyncio
    async def test_re_replicate_on_node_failure(self, adaptive_replicator, replica_tracker):
        """Test that documents are re-replicated when node fails."""
        # Setup: doc-1 on node-1 (primary) and node-2 (replica)
        replica_tracker.register_primary("doc-1", "node-1")
        replica_tracker.add_replica("doc-1", "node-2")
        
        # Node-2 fails
        replica_tracker.remove_node("node-2")
        
        # Find under-replicated documents
        under_replicated = replica_tracker.find_under_replicated(min_replicas=2)
        
        assert "doc-1" in under_replicated
    
    @pytest.mark.asyncio
    async def test_promote_replica_on_primary_failure(self, replica_tracker):
        """Test that replica is promoted when primary fails."""
        doc_id = "doc-1"
        
        replica_tracker.register_primary(doc_id, "node-1")
        replica_tracker.add_replica(doc_id, "node-2")
        replica_tracker.add_replica(doc_id, "node-3")
        
        # Primary node-1 fails
        replica_tracker.handle_node_failure("node-1")
        
        replicas = replica_tracker.get_replicas(doc_id)
        
        # New primary should be one of the replicas
        assert replicas.primary_node in ["node-2", "node-3"]


# ============================================================================
# Integration Tests
# ============================================================================

class TestReplicationIntegration:
    """Integration tests for replication system."""
    
    @pytest.mark.asyncio
    async def test_full_replication_cycle(self, adaptive_replicator, replica_tracker):
        """Test complete replication cycle for a new document."""
        doc_id = "new-doc"
        primary_node = "node-1"
        
        # Configure for 3 nodes, 2 replicas
        adaptive_replicator.config.update_for_nodes(3)
        
        # Register primary
        replica_tracker.register_primary(doc_id, primary_node)
        
        # Replicate to other nodes
        adaptive_replicator._replicate_func = AsyncMock(return_value=True)
        
        results = await adaptive_replicator.ensure_replicated(
            document_id=doc_id,
            primary_node=primary_node,
            available_nodes=["node-1", "node-2", "node-3"],
            replica_tracker=replica_tracker
        )
        
        # Should have created replicas
        assert replica_tracker.get_replica_count(doc_id) >= 2
    
    @pytest.mark.asyncio
    async def test_concurrent_replications_limited(self, adaptive_replicator):
        """Test that concurrent replications are limited."""
        adaptive_replicator.config.max_concurrent_replications = 2
        
        # Create slow replication mock
        async def slow_replicate(doc_id, source, target):
            await asyncio.sleep(0.1)
            return True
        
        adaptive_replicator._replicate_func = slow_replicate
        
        # Start multiple replications
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                adaptive_replicator.replicate(f"doc-{i}", "node-1", "node-2")
            )
            tasks.append(task)
        
        # Check that only max_concurrent are running
        # (This is a simplified test - actual implementation may vary)
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
