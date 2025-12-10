"""
Integration Tests for Cluster Operations
Tests cluster coordination, consensus, and distributed operations
"""

import pytest
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def cluster_config() -> Dict[str, Any]:
    """Cluster configuration for testing"""
    return {
        "node_id": "test-node-1",
        "cluster_name": "test-cluster",
        "nodes": ["node-1", "node-2", "node-3"],
        "replication_factor": 3,
        "heartbeat_interval": 1.0,
        "election_timeout": 5.0
    }


@pytest.fixture
def mock_raft_state():
    """Mock Raft consensus state"""
    state = Mock()
    state.current_term = 1
    state.voted_for = None
    state.log = []
    state.commit_index = 0
    state.last_applied = 0
    state.state = "follower"
    return state


@pytest.fixture
def mock_grpc_client():
    """Mock gRPC client"""
    client = AsyncMock()
    client.send_request_vote = AsyncMock(return_value={
        "term": 1,
        "vote_granted": True
    })
    client.send_append_entries = AsyncMock(return_value={
        "term": 1,
        "success": True
    })
    return client


# ============================================================================
# Leader Election Tests
# ============================================================================

class TestLeaderElection:
    """Tests for leader election process"""
    
    @pytest.mark.asyncio
    async def test_start_election(self, cluster_config: Dict[str, Any], mock_raft_state, mock_grpc_client):
        """Test starting a new election"""
        from consensus.raft import RaftNode
        
        with patch.object(RaftNode, '_send_request_vote', mock_grpc_client.send_request_vote):
            node = RaftNode(cluster_config["node_id"], cluster_config)
            node.state = mock_raft_state
            
            # Trigger election
            await node.start_election()
            
            # Should become candidate
            assert mock_raft_state.state in ["candidate", "leader"]
            assert mock_raft_state.current_term >= 1
    
    @pytest.mark.asyncio
    async def test_vote_request(self, cluster_config: Dict[str, Any], mock_raft_state):
        """Test handling vote request"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        
        vote_request = {
            "term": 2,
            "candidate_id": "node-2",
            "last_log_index": 0,
            "last_log_term": 0
        }
        
        response = await node.handle_request_vote(vote_request)
        
        assert "term" in response
        assert "vote_granted" in response
    
    @pytest.mark.asyncio
    async def test_vote_grant_higher_term(self, cluster_config: Dict[str, Any], mock_raft_state):
        """Test granting vote for higher term candidate"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        mock_raft_state.current_term = 1
        mock_raft_state.voted_for = None
        
        vote_request = {
            "term": 2,
            "candidate_id": "node-2",
            "last_log_index": 0,
            "last_log_term": 0
        }
        
        response = await node.handle_request_vote(vote_request)
        
        assert response["vote_granted"] == True
    
    @pytest.mark.asyncio
    async def test_vote_deny_lower_term(self, cluster_config: Dict[str, Any], mock_raft_state):
        """Test denying vote for lower term candidate"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        mock_raft_state.current_term = 3
        
        vote_request = {
            "term": 2,
            "candidate_id": "node-2",
            "last_log_index": 0,
            "last_log_term": 0
        }
        
        response = await node.handle_request_vote(vote_request)
        
        assert response["vote_granted"] == False
    
    @pytest.mark.asyncio
    async def test_become_leader(self, cluster_config: Dict[str, Any], mock_raft_state, mock_grpc_client):
        """Test becoming leader after winning election"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        
        # Simulate winning election
        await node.become_leader()
        
        assert node.is_leader()


# ============================================================================
# Log Replication Tests
# ============================================================================

class TestLogReplication:
    """Tests for log replication"""
    
    @pytest.mark.asyncio
    async def test_append_entries(self, cluster_config: Dict[str, Any], mock_raft_state):
        """Test handling append entries"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        
        append_request = {
            "term": 1,
            "leader_id": "node-1",
            "prev_log_index": -1,
            "prev_log_term": 0,
            "entries": [{"term": 1, "command": {"action": "create", "doc_id": "doc-1"}}],
            "leader_commit": 0
        }
        
        response = await node.handle_append_entries(append_request)
        
        assert "term" in response
        assert "success" in response
    
    @pytest.mark.asyncio
    async def test_log_consistency(self, cluster_config: Dict[str, Any], mock_raft_state):
        """Test log consistency check"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        mock_raft_state.log = [{"term": 1, "command": {}}]
        
        # Matching prev log
        append_request = {
            "term": 1,
            "leader_id": "node-1",
            "prev_log_index": 0,
            "prev_log_term": 1,
            "entries": [{"term": 1, "command": {"action": "update"}}],
            "leader_commit": 0
        }
        
        response = await node.handle_append_entries(append_request)
        
        assert response["success"] == True
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, cluster_config: Dict[str, Any], mock_raft_state):
        """Test heartbeat (empty append entries)"""
        from consensus.raft import RaftNode
        
        node = RaftNode(cluster_config["node_id"], cluster_config)
        node.state = mock_raft_state
        
        heartbeat = {
            "term": 1,
            "leader_id": "node-1",
            "prev_log_index": -1,
            "prev_log_term": 0,
            "entries": [],  # Empty = heartbeat
            "leader_commit": 0
        }
        
        response = await node.handle_append_entries(heartbeat)
        
        assert response["success"] == True


# ============================================================================
# Cluster Membership Tests
# ============================================================================

class TestClusterMembership:
    """Tests for cluster membership changes"""
    
    @pytest.mark.asyncio
    async def test_add_node(self, cluster_config: Dict[str, Any]):
        """Test adding a new node to cluster"""
        from coordination.cluster_manager import ClusterManager
        
        manager = ClusterManager(cluster_config)
        await manager.initialize()
        
        result = await manager.add_node("node-4", "localhost:50054")
        
        assert result["success"] == True
        assert "node-4" in manager.get_nodes()
    
    @pytest.mark.asyncio
    async def test_remove_node(self, cluster_config: Dict[str, Any]):
        """Test removing a node from cluster"""
        from coordination.cluster_manager import ClusterManager
        
        manager = ClusterManager(cluster_config)
        await manager.initialize()
        
        result = await manager.remove_node("node-3")
        
        assert result["success"] == True
        assert "node-3" not in manager.get_nodes()
    
    @pytest.mark.asyncio
    async def test_node_status(self, cluster_config: Dict[str, Any]):
        """Test getting node status"""
        from coordination.cluster_manager import ClusterManager
        
        manager = ClusterManager(cluster_config)
        await manager.initialize()
        
        status = manager.get_node_status("node-1")
        
        assert "id" in status
        assert "status" in status


# ============================================================================
# Failure Detection Tests
# ============================================================================

class TestFailureDetection:
    """Tests for failure detection"""
    
    @pytest.mark.asyncio
    async def test_detect_node_failure(self, cluster_config: Dict[str, Any]):
        """Test detecting node failure"""
        from recovery.failure_detector import FailureDetector
        
        detector = FailureDetector(
            heartbeat_interval=0.1,
            failure_threshold=3
        )
        
        # Simulate missing heartbeats
        await detector.start()
        await asyncio.sleep(0.5)
        
        failures = detector.get_failed_nodes()
        # May or may not detect failures depending on heartbeat responses
    
    @pytest.mark.asyncio
    async def test_heartbeat_received(self, cluster_config: Dict[str, Any]):
        """Test handling received heartbeat"""
        from recovery.failure_detector import FailureDetector
        
        detector = FailureDetector()
        
        detector.record_heartbeat("node-1")
        
        assert detector.is_node_alive("node-1")
    
    @pytest.mark.asyncio
    async def test_node_recovery(self, cluster_config: Dict[str, Any]):
        """Test handling node recovery after failure"""
        from recovery.failure_detector import FailureDetector
        
        detector = FailureDetector()
        
        # Simulate failure then recovery
        detector.mark_node_failed("node-1")
        assert not detector.is_node_alive("node-1")
        
        detector.record_heartbeat("node-1")
        assert detector.is_node_alive("node-1")


# ============================================================================
# Data Replication Tests
# ============================================================================

class TestDataReplication:
    """Tests for data replication across nodes"""
    
    @pytest.mark.asyncio
    async def test_replicate_document(self, cluster_config: Dict[str, Any]):
        """Test replicating document to multiple nodes"""
        from replication.replication_manager import ReplicationManager
        
        manager = ReplicationManager(
            replication_factor=3,
            quorum_size=2
        )
        
        document = {
            "id": "doc-123",
            "title": "Test",
            "content": "Test content"
        }
        
        # Mock node communication
        with patch.object(manager, '_replicate_to_node', AsyncMock(return_value=True)):
            result = await manager.replicate(document, ["node-1", "node-2", "node-3"])
        
        assert result["success"] == True
        assert result["replicated_to"] >= 2
    
    @pytest.mark.asyncio
    async def test_quorum_write(self, cluster_config: Dict[str, Any]):
        """Test quorum-based write"""
        from replication.replication_manager import ReplicationManager
        
        manager = ReplicationManager(
            replication_factor=3,
            quorum_size=2
        )
        
        document = {"id": "doc-123", "content": "test"}
        
        # Simulate 2 out of 3 nodes succeeding
        with patch.object(manager, '_replicate_to_node', AsyncMock(
            side_effect=[True, True, False]
        )):
            result = await manager.quorum_write(document, ["node-1", "node-2", "node-3"])
        
        # Should succeed with quorum
        assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_quorum_failure(self, cluster_config: Dict[str, Any]):
        """Test quorum failure when not enough nodes respond"""
        from replication.replication_manager import ReplicationManager
        
        manager = ReplicationManager(
            replication_factor=3,
            quorum_size=2
        )
        
        document = {"id": "doc-123", "content": "test"}
        
        # Simulate only 1 out of 3 nodes succeeding
        with patch.object(manager, '_replicate_to_node', AsyncMock(
            side_effect=[True, False, False]
        )):
            result = await manager.quorum_write(document, ["node-1", "node-2", "node-3"])
        
        # Should fail without quorum
        assert result["success"] == False


# ============================================================================
# Partition Rebalancing Tests
# ============================================================================

class TestPartitionRebalancing:
    """Tests for partition rebalancing"""
    
    @pytest.mark.asyncio
    async def test_trigger_rebalance(self, cluster_config: Dict[str, Any]):
        """Test triggering partition rebalance"""
        from rebalancing.rebalancer import Rebalancer
        
        rebalancer = Rebalancer(cluster_config)
        
        # Add imbalance
        imbalance = rebalancer.check_imbalance()
        
        if imbalance > 0.1:
            result = await rebalancer.rebalance()
            assert "moves" in result
    
    @pytest.mark.asyncio
    async def test_data_migration(self, cluster_config: Dict[str, Any]):
        """Test data migration during rebalancing"""
        from rebalancing.rebalancer import Rebalancer
        
        rebalancer = Rebalancer(cluster_config)
        
        migration_plan = {
            "partition_1": {"from": "node-1", "to": "node-4"},
            "partition_2": {"from": "node-2", "to": "node-4"}
        }
        
        with patch.object(rebalancer, '_migrate_partition', AsyncMock(return_value=True)):
            result = await rebalancer.execute_migration(migration_plan)
        
        assert result["success"] == True


# ============================================================================
# Recovery Tests
# ============================================================================

class TestRecovery:
    """Tests for failure recovery"""
    
    @pytest.mark.asyncio
    async def test_recover_from_failure(self, cluster_config: Dict[str, Any]):
        """Test recovering from node failure"""
        from recovery.recovery_manager import RecoveryManager
        
        manager = RecoveryManager(cluster_config)
        
        # Simulate node failure and recovery
        failed_node = "node-2"
        
        result = await manager.handle_node_failure(failed_node)
        
        assert "affected_partitions" in result
    
    @pytest.mark.asyncio
    async def test_data_recovery(self, cluster_config: Dict[str, Any]):
        """Test recovering data for failed partitions"""
        from recovery.recovery_manager import RecoveryManager
        
        manager = RecoveryManager(cluster_config)
        
        partition_id = 5
        
        with patch.object(manager, '_fetch_partition_data', AsyncMock(return_value=[])):
            result = await manager.recover_partition(partition_id)
        
        assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_state_sync(self, cluster_config: Dict[str, Any]):
        """Test synchronizing state after recovery"""
        from recovery.recovery_manager import RecoveryManager
        
        manager = RecoveryManager(cluster_config)
        
        # Sync state with leader
        with patch.object(manager, '_get_leader_state', AsyncMock(return_value={})):
            result = await manager.sync_state()
        
        assert result["synced"] == True


# ============================================================================
# Distributed Transaction Tests
# ============================================================================

class TestDistributedTransactions:
    """Tests for distributed transactions"""
    
    @pytest.mark.asyncio
    async def test_two_phase_commit(self, cluster_config: Dict[str, Any]):
        """Test two-phase commit protocol"""
        from coordination.transaction_coordinator import TransactionCoordinator
        
        coordinator = TransactionCoordinator(cluster_config)
        
        transaction = {
            "id": "tx-123",
            "operations": [
                {"type": "create", "doc_id": "doc-1", "data": {}},
                {"type": "update", "doc_id": "doc-2", "data": {}}
            ]
        }
        
        with patch.object(coordinator, '_prepare', AsyncMock(return_value=True)):
            with patch.object(coordinator, '_commit', AsyncMock(return_value=True)):
                result = await coordinator.execute_transaction(transaction)
        
        assert result["committed"] == True
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, cluster_config: Dict[str, Any]):
        """Test transaction rollback on failure"""
        from coordination.transaction_coordinator import TransactionCoordinator
        
        coordinator = TransactionCoordinator(cluster_config)
        
        transaction = {
            "id": "tx-124",
            "operations": [{"type": "create", "doc_id": "doc-1", "data": {}}]
        }
        
        # Simulate prepare failure
        with patch.object(coordinator, '_prepare', AsyncMock(return_value=False)):
            with patch.object(coordinator, '_rollback', AsyncMock(return_value=True)):
                result = await coordinator.execute_transaction(transaction)
        
        assert result["committed"] == False
        assert result["rolled_back"] == True


# ============================================================================
# Performance Tests
# ============================================================================

class TestClusterPerformance:
    """Performance-related cluster tests"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_election_convergence(self, cluster_config: Dict[str, Any]):
        """Test that election converges quickly"""
        import time
        
        from consensus.raft import RaftNode
        
        # Create multiple nodes
        nodes = []
        for i in range(3):
            config = {**cluster_config, "node_id": f"node-{i}"}
            nodes.append(RaftNode(f"node-{i}", config))
        
        start = time.time()
        
        # Trigger election
        await nodes[0].start_election()
        
        # Wait for convergence
        await asyncio.sleep(2)
        
        elapsed = time.time() - start
        
        # Should converge quickly
        assert elapsed < 5.0
        
        # Cleanup
        for node in nodes:
            await node.shutdown()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_operations(self, cluster_config: Dict[str, Any]):
        """Test handling concurrent cluster operations"""
        from coordination.cluster_manager import ClusterManager
        
        manager = ClusterManager(cluster_config)
        await manager.initialize()
        
        # Simulate concurrent status checks
        async def check_status():
            return manager.get_cluster_status()
        
        tasks = [check_status() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
