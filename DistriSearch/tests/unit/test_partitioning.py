"""
Unit Tests for Partitioning Module
Tests consistent hashing and partition management
"""

import pytest
import hashlib
from typing import List, Dict, Set
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from partitioning.consistent_hash import ConsistentHashRing, VirtualNode
from partitioning.partition_manager import PartitionManager


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def node_ids() -> List[str]:
    """Sample node IDs"""
    return ["node-1", "node-2", "node-3", "node-4", "node-5"]


@pytest.fixture
def hash_ring(node_ids: List[str]) -> ConsistentHashRing:
    """Create consistent hash ring with sample nodes"""
    ring = ConsistentHashRing(virtual_nodes=150)
    for node_id in node_ids:
        ring.add_node(node_id)
    return ring


@pytest.fixture
def partition_manager(node_ids: List[str]) -> PartitionManager:
    """Create partition manager with sample nodes"""
    manager = PartitionManager(
        num_partitions=64,
        replication_factor=3
    )
    for node_id in node_ids:
        manager.add_node(node_id)
    return manager


# ============================================================================
# Consistent Hash Ring Tests
# ============================================================================

class TestConsistentHashRing:
    """Tests for consistent hash ring implementation"""
    
    def test_initialization(self):
        """Test ring initialization"""
        ring = ConsistentHashRing(virtual_nodes=100)
        assert ring is not None
        assert ring.virtual_nodes == 100
        assert ring.node_count == 0
    
    def test_add_node(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test adding nodes to ring"""
        assert hash_ring.node_count == len(node_ids)
    
    def test_add_duplicate_node(self, hash_ring: ConsistentHashRing):
        """Test adding duplicate node"""
        initial_count = hash_ring.node_count
        hash_ring.add_node("node-1")  # Already exists
        
        # Should not increase count
        assert hash_ring.node_count == initial_count
    
    def test_remove_node(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test removing nodes from ring"""
        hash_ring.remove_node("node-1")
        
        assert hash_ring.node_count == len(node_ids) - 1
        assert "node-1" not in hash_ring.get_all_nodes()
    
    def test_remove_nonexistent_node(self, hash_ring: ConsistentHashRing):
        """Test removing non-existent node"""
        initial_count = hash_ring.node_count
        hash_ring.remove_node("nonexistent-node")
        
        assert hash_ring.node_count == initial_count
    
    def test_get_node(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test getting node for a key"""
        node = hash_ring.get_node("test-key")
        
        assert node is not None
        assert node in node_ids
    
    def test_get_node_consistency(self, hash_ring: ConsistentHashRing):
        """Test that same key always maps to same node"""
        key = "consistent-key"
        
        node1 = hash_ring.get_node(key)
        node2 = hash_ring.get_node(key)
        node3 = hash_ring.get_node(key)
        
        assert node1 == node2 == node3
    
    def test_distribution(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test key distribution across nodes"""
        distribution: Dict[str, int] = {node_id: 0 for node_id in node_ids}
        
        # Assign many keys
        for i in range(10000):
            key = f"key-{i}"
            node = hash_ring.get_node(key)
            distribution[node] += 1
        
        # Check distribution is reasonably balanced
        avg = 10000 / len(node_ids)
        for node_id, count in distribution.items():
            # Allow 50% deviation (generous due to hash randomness)
            assert count > avg * 0.5, f"Node {node_id} has too few keys: {count}"
            assert count < avg * 1.5, f"Node {node_id} has too many keys: {count}"
    
    def test_get_nodes_for_key(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test getting multiple nodes for replication"""
        nodes = hash_ring.get_nodes_for_key("test-key", count=3)
        
        assert len(nodes) == 3
        assert len(set(nodes)) == 3  # All unique
        for node in nodes:
            assert node in node_ids
    
    def test_minimal_remapping_on_add(self, node_ids: List[str]):
        """Test minimal key remapping when adding node"""
        ring = ConsistentHashRing(virtual_nodes=150)
        for node_id in node_ids[:4]:
            ring.add_node(node_id)
        
        # Map keys before adding new node
        key_mapping_before = {}
        for i in range(1000):
            key = f"key-{i}"
            key_mapping_before[key] = ring.get_node(key)
        
        # Add new node
        ring.add_node("node-5")
        
        # Check remapping
        remapped = 0
        for i in range(1000):
            key = f"key-{i}"
            if ring.get_node(key) != key_mapping_before[key]:
                remapped += 1
        
        # Only about 1/N keys should remap
        expected_remap = 1000 / 5
        assert remapped < expected_remap * 2
    
    def test_minimal_remapping_on_remove(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test minimal key remapping when removing node"""
        # Map keys before removing node
        key_mapping_before = {}
        for i in range(1000):
            key = f"key-{i}"
            key_mapping_before[key] = hash_ring.get_node(key)
        
        # Remove a node
        hash_ring.remove_node("node-3")
        
        # Check remapping
        remapped = 0
        for i in range(1000):
            key = f"key-{i}"
            if hash_ring.get_node(key) != key_mapping_before[key]:
                remapped += 1
        
        # Only keys that were on removed node should remap
        keys_on_removed = sum(
            1 for k, v in key_mapping_before.items() if v == "node-3"
        )
        assert remapped == keys_on_removed
    
    def test_virtual_nodes(self):
        """Test virtual node creation"""
        ring = ConsistentHashRing(virtual_nodes=100)
        ring.add_node("node-1")
        
        # Should have created virtual nodes
        assert ring.get_ring_size() == 100
    
    def test_empty_ring(self):
        """Test operations on empty ring"""
        ring = ConsistentHashRing()
        
        assert ring.node_count == 0
        assert ring.get_node("test-key") is None
        assert ring.get_nodes_for_key("test-key", count=3) == []


# ============================================================================
# Virtual Node Tests
# ============================================================================

class TestVirtualNode:
    """Tests for virtual node implementation"""
    
    def test_creation(self):
        """Test virtual node creation"""
        vnode = VirtualNode("node-1", 0)
        
        assert vnode.physical_node == "node-1"
        assert vnode.index == 0
        assert vnode.hash_value is not None
    
    def test_hash_uniqueness(self):
        """Test that virtual nodes have unique hashes"""
        vnodes = [VirtualNode("node-1", i) for i in range(100)]
        hashes = [v.hash_value for v in vnodes]
        
        assert len(set(hashes)) == len(hashes)
    
    def test_hash_determinism(self):
        """Test that hash values are deterministic"""
        vnode1 = VirtualNode("node-1", 5)
        vnode2 = VirtualNode("node-1", 5)
        
        assert vnode1.hash_value == vnode2.hash_value


# ============================================================================
# Partition Manager Tests
# ============================================================================

class TestPartitionManager:
    """Tests for partition manager"""
    
    def test_initialization(self):
        """Test partition manager initialization"""
        manager = PartitionManager(num_partitions=64, replication_factor=3)
        
        assert manager.num_partitions == 64
        assert manager.replication_factor == 3
    
    def test_add_node(self, partition_manager: PartitionManager, node_ids: List[str]):
        """Test adding nodes"""
        assert partition_manager.node_count == len(node_ids)
    
    def test_remove_node(self, partition_manager: PartitionManager):
        """Test removing nodes"""
        partition_manager.remove_node("node-1")
        
        assert "node-1" not in partition_manager.get_all_nodes()
    
    def test_get_partition(self, partition_manager: PartitionManager):
        """Test getting partition for document"""
        partition = partition_manager.get_partition("doc-123")
        
        assert 0 <= partition < partition_manager.num_partitions
    
    def test_partition_consistency(self, partition_manager: PartitionManager):
        """Test partition assignment consistency"""
        doc_id = "consistent-doc"
        
        p1 = partition_manager.get_partition(doc_id)
        p2 = partition_manager.get_partition(doc_id)
        p3 = partition_manager.get_partition(doc_id)
        
        assert p1 == p2 == p3
    
    def test_get_nodes_for_partition(self, partition_manager: PartitionManager):
        """Test getting nodes responsible for partition"""
        nodes = partition_manager.get_nodes_for_partition(0)
        
        assert len(nodes) == partition_manager.replication_factor
        assert len(set(nodes)) == len(nodes)  # All unique
    
    def test_get_partitions_for_node(self, partition_manager: PartitionManager, node_ids: List[str]):
        """Test getting partitions assigned to a node"""
        for node_id in node_ids:
            partitions = partition_manager.get_partitions_for_node(node_id)
            
            assert len(partitions) > 0
            for p in partitions:
                assert 0 <= p < partition_manager.num_partitions
    
    def test_partition_distribution(self, partition_manager: PartitionManager, node_ids: List[str]):
        """Test partition distribution across nodes"""
        partition_counts = {node_id: 0 for node_id in node_ids}
        
        for partition_id in range(partition_manager.num_partitions):
            nodes = partition_manager.get_nodes_for_partition(partition_id)
            for node in nodes:
                partition_counts[node] += 1
        
        # Each node should have roughly equal partitions
        total_assignments = partition_manager.num_partitions * partition_manager.replication_factor
        avg = total_assignments / len(node_ids)
        
        for node_id, count in partition_counts.items():
            # Allow 50% deviation
            assert count > avg * 0.5, f"Node {node_id} has too few partitions"
            assert count < avg * 1.5, f"Node {node_id} has too many partitions"
    
    def test_get_document_nodes(self, partition_manager: PartitionManager, node_ids: List[str]):
        """Test getting nodes responsible for a document"""
        nodes = partition_manager.get_document_nodes("doc-123")
        
        assert len(nodes) == partition_manager.replication_factor
        for node in nodes:
            assert node in node_ids
    
    def test_rebalance_on_add(self, node_ids: List[str]):
        """Test rebalancing when adding a node"""
        manager = PartitionManager(num_partitions=64, replication_factor=3)
        
        # Add initial nodes
        for node_id in node_ids[:3]:
            manager.add_node(node_id)
        
        # Get initial assignments
        initial_assignments = {}
        for p in range(manager.num_partitions):
            initial_assignments[p] = set(manager.get_nodes_for_partition(p))
        
        # Add new node
        manager.add_node("node-4")
        
        # Check that new node has partitions
        new_node_partitions = manager.get_partitions_for_node("node-4")
        assert len(new_node_partitions) > 0
    
    def test_rebalance_on_remove(self, partition_manager: PartitionManager):
        """Test rebalancing when removing a node"""
        # Get partitions of node to be removed
        partitions_before = partition_manager.get_partitions_for_node("node-1")
        
        # Remove node
        partition_manager.remove_node("node-1")
        
        # All partitions should still have enough replicas
        for p in partitions_before:
            nodes = partition_manager.get_nodes_for_partition(p)
            assert len(nodes) == partition_manager.replication_factor
    
    def test_primary_node(self, partition_manager: PartitionManager):
        """Test getting primary node for partition"""
        primary = partition_manager.get_primary_node(0)
        
        assert primary is not None
        assert primary in partition_manager.get_all_nodes()
    
    def test_is_primary(self, partition_manager: PartitionManager, node_ids: List[str]):
        """Test checking if node is primary for partition"""
        for partition_id in range(partition_manager.num_partitions):
            primary_count = sum(
                1 for node_id in node_ids
                if partition_manager.is_primary(node_id, partition_id)
            )
            assert primary_count == 1  # Exactly one primary per partition


# ============================================================================
# Replication Tests
# ============================================================================

class TestReplication:
    """Tests for replication handling"""
    
    def test_replication_factor(self, partition_manager: PartitionManager):
        """Test that replication factor is maintained"""
        for p in range(partition_manager.num_partitions):
            nodes = partition_manager.get_nodes_for_partition(p)
            assert len(nodes) == partition_manager.replication_factor
    
    def test_replication_with_few_nodes(self):
        """Test replication when fewer nodes than replication factor"""
        manager = PartitionManager(num_partitions=8, replication_factor=3)
        manager.add_node("node-1")
        manager.add_node("node-2")  # Only 2 nodes
        
        # Should use all available nodes
        nodes = manager.get_nodes_for_partition(0)
        assert len(nodes) == 2  # Can't have more replicas than nodes
    
    def test_replica_nodes_different(self, partition_manager: PartitionManager):
        """Test that replicas are on different nodes"""
        for p in range(partition_manager.num_partitions):
            nodes = partition_manager.get_nodes_for_partition(p)
            assert len(nodes) == len(set(nodes))  # All unique


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_single_node(self):
        """Test with single node"""
        manager = PartitionManager(num_partitions=8, replication_factor=3)
        manager.add_node("node-1")
        
        # Should still work with single node
        nodes = manager.get_document_nodes("test-doc")
        assert nodes == ["node-1"]
    
    def test_no_nodes(self):
        """Test with no nodes"""
        manager = PartitionManager(num_partitions=8, replication_factor=3)
        
        nodes = manager.get_document_nodes("test-doc")
        assert nodes == []
    
    def test_high_replication_factor(self):
        """Test with replication factor equal to nodes"""
        manager = PartitionManager(num_partitions=8, replication_factor=5)
        for i in range(5):
            manager.add_node(f"node-{i}")
        
        nodes = manager.get_nodes_for_partition(0)
        assert len(nodes) == 5
    
    def test_many_partitions(self):
        """Test with many partitions"""
        manager = PartitionManager(num_partitions=1024, replication_factor=3)
        for i in range(10):
            manager.add_node(f"node-{i}")
        
        # Should handle large number of partitions
        for p in range(1024):
            nodes = manager.get_nodes_for_partition(p)
            assert len(nodes) == 3
    
    def test_partition_id_range(self, partition_manager: PartitionManager):
        """Test that partition IDs are always in valid range"""
        for i in range(10000):
            p = partition_manager.get_partition(f"doc-{i}")
            assert 0 <= p < partition_manager.num_partitions


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSerialization:
    """Test serialization and persistence"""
    
    def test_hash_ring_serialization(self, hash_ring: ConsistentHashRing, node_ids: List[str]):
        """Test hash ring serialization"""
        # Serialize
        state = hash_ring.to_dict()
        
        assert "nodes" in state
        assert "virtual_nodes" in state
        
        # Deserialize
        new_ring = ConsistentHashRing.from_dict(state)
        
        # Check consistency
        assert new_ring.node_count == hash_ring.node_count
        
        for i in range(100):
            key = f"test-key-{i}"
            assert new_ring.get_node(key) == hash_ring.get_node(key)
    
    def test_partition_manager_serialization(self, partition_manager: PartitionManager):
        """Test partition manager serialization"""
        # Serialize
        state = partition_manager.to_dict()
        
        assert "num_partitions" in state
        assert "replication_factor" in state
        assert "nodes" in state
        
        # Deserialize
        new_manager = PartitionManager.from_dict(state)
        
        # Check consistency
        assert new_manager.num_partitions == partition_manager.num_partitions
        assert new_manager.replication_factor == partition_manager.replication_factor
        
        for p in range(partition_manager.num_partitions):
            assert (
                new_manager.get_nodes_for_partition(p) ==
                partition_manager.get_nodes_for_partition(p)
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
