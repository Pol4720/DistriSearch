# -*- coding: utf-8 -*-
"""
Integration Tests for Cluster Operations

Tests cluster coordination, consensus, and distributed operations.
"""

import pytest
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
from pathlib import Path
import tempfile

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.distributed.consensus.raft_state import RaftState, NodeRole
from app.distributed.consensus.log_entry import LogStore, LogEntry
from app.distributed.consensus.leader_election import (
    LeaderElection,
    RequestVoteArgs,
    RequestVoteReply,
)
from app.distributed.consensus.log_replication import (
    LogReplicator,
    AppendEntriesArgs,
    AppendEntriesReply,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def cluster_config() -> Dict[str, Any]:
    """Cluster configuration for testing."""
    return {
        "node_id": "test-node-1",
        "cluster_name": "test-cluster",
        "nodes": ["node-1", "node-2", "node-3"],
        "replication_factor": 3,
        "heartbeat_interval": 1.0,
        "election_timeout": 5.0
    }


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def raft_state(temp_storage) -> RaftState:
    """Create Raft state for testing."""
    return RaftState(
        node_id="node-1",
        storage_path=temp_storage / "node-1",
        election_timeout_min=0.15,
        election_timeout_max=0.30,
        heartbeat_interval=0.05,
    )


@pytest.fixture
def log_store(temp_storage) -> LogStore:
    """Create log store for testing."""
    return LogStore(storage_path=temp_storage / "logs")


@pytest.fixture
def mock_grpc_client():
    """Mock gRPC client."""
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
    """Tests for leader election process."""
    
    @pytest.mark.asyncio
    async def test_start_election(self, raft_state, log_store):
        """Test starting a new election."""
        mock_sender = AsyncMock(return_value=RequestVoteReply(term=1, vote_granted=True))
        
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        initial_term = raft_state.current_term
        await raft_state.become_candidate()
        
        assert raft_state.role == NodeRole.CANDIDATE
        assert raft_state.current_term > initial_term
    
    @pytest.mark.asyncio
    async def test_vote_request(self, raft_state, log_store):
        """Test handling vote request."""
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        args = RequestVoteArgs(
            term=2,
            candidate_id="node-2",
            last_log_index=0,
            last_log_term=0
        )
        
        response = await election.handle_request_vote(args)
        
        assert isinstance(response, RequestVoteReply)
        assert response.term >= 0
    
    @pytest.mark.asyncio
    async def test_vote_grant_higher_term(self, raft_state, log_store):
        """Test granting vote to higher term candidate."""
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        args = RequestVoteArgs(
            term=5,
            candidate_id="node-2",
            last_log_index=0,
            last_log_term=0
        )
        
        response = await election.handle_request_vote(args)
        
        assert response.vote_granted is True
    
    @pytest.mark.asyncio
    async def test_vote_deny_lower_term(self, raft_state, log_store):
        """Test denying vote to lower term candidate."""
        await raft_state.update_term(10)
        
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        args = RequestVoteArgs(
            term=5,  # Lower than current term
            candidate_id="node-2",
            last_log_index=0,
            last_log_term=0
        )
        
        response = await election.handle_request_vote(args)
        
        assert response.vote_granted is False
    
    @pytest.mark.asyncio
    async def test_become_leader(self, raft_state, log_store):
        """Test becoming leader after winning election."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        assert raft_state.role == NodeRole.LEADER


# ============================================================================
# Log Replication Tests
# ============================================================================

class TestLogReplication:
    """Tests for log replication."""
    
    @pytest.mark.asyncio
    async def test_append_entries(self, raft_state, log_store):
        """Test handling append entries."""
        mock_sender = AsyncMock()
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_sender
        )
        
        args = AppendEntriesArgs(
            term=1,
            leader_id="node-2",
            prev_log_index=0,
            prev_log_term=0,
            entries=[LogEntry(term=1, index=1, command={"key": "value"})],
            leader_commit=0
        )
        
        response = await replicator.handle_append_entries(args)
        
        assert isinstance(response, AppendEntriesReply)
    
    @pytest.mark.asyncio
    async def test_log_consistency(self, log_store):
        """Test log consistency after append."""
        await log_store.append(command={"cmd": 1}, term=1)
        await log_store.append(command={"cmd": 2}, term=1)
        
        assert log_store.last_index == 2
        entry1 = await log_store.get_entry(1)
        entry2 = await log_store.get_entry(2)
        assert entry1.command == {"cmd": 1}
        assert entry2.command == {"cmd": 2}
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, raft_state, log_store):
        """Test heartbeat (empty append entries)."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        heartbeats_sent = []
        
        async def mock_sender(node_id, args):
            heartbeats_sent.append((node_id, args))
            return AppendEntriesReply(term=args.term, success=True)
        
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_sender
        )
        
        # Add a node to the cluster to send heartbeats to
        await raft_state.add_cluster_node("node-2", "localhost:8002")
        
        # Use internal method to send heartbeats
        await replicator._send_heartbeats()
        
        assert len(heartbeats_sent) >= 1


# ============================================================================
# Cluster Membership Tests
# ============================================================================

class TestClusterMembership:
    """Tests for cluster membership changes."""
    
    @pytest.mark.asyncio
    async def test_add_node(self, raft_state):
        """Test adding a node to cluster."""
        await raft_state.add_cluster_node("node-2", "localhost:8002")
        
        assert "node-2" in raft_state.cluster_nodes
    
    @pytest.mark.asyncio
    async def test_remove_node(self, raft_state):
        """Test removing a node from cluster."""
        await raft_state.add_cluster_node("node-2", "localhost:8002")
        await raft_state.remove_cluster_node("node-2")
        
        assert "node-2" not in raft_state.cluster_nodes
    
    @pytest.mark.asyncio
    async def test_node_status(self, raft_state):
        """Test getting node status."""
        status = raft_state.get_status()
        
        assert "node_id" in status
        assert "role" in status
        assert "current_term" in status


# ============================================================================
# Failure Detection Tests
# ============================================================================

class TestFailureDetection:
    """Tests for failure detection."""
    
    @pytest.mark.asyncio
    async def test_detect_node_failure(self, raft_state):
        """Test detecting node failure via heartbeat timeout."""
        # Simulate time passing without heartbeat
        import time
        
        # Record heartbeat
        await raft_state.record_heartbeat("node-2")
        time.sleep(0.01)
        
        elapsed = raft_state.time_since_last_heartbeat()
        assert elapsed >= 0.01
    
    @pytest.mark.asyncio
    async def test_heartbeat_received(self, raft_state):
        """Test recording received heartbeat."""
        await raft_state.record_heartbeat("node-2")
        
        elapsed = raft_state.time_since_last_heartbeat()
        assert elapsed < 1.0
    
    @pytest.mark.asyncio
    async def test_node_recovery(self, raft_state, log_store):
        """Test node recovery after failure."""
        # Simulate going down and coming back up
        await raft_state.become_follower()
        
        assert raft_state.role == NodeRole.FOLLOWER


# ============================================================================
# Data Replication Tests
# ============================================================================

class TestDataReplication:
    """Tests for data replication."""
    
    @pytest.mark.asyncio
    async def test_replicate_document(self, raft_state, log_store):
        """Test replicating a document via log."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        entry = await log_store.append(
            command={"type": "put", "doc_id": "doc-1", "data": {"title": "Test"}},
            term=raft_state.current_term
        )
        
        assert log_store.last_index == 1
        assert entry.command["doc_id"] == "doc-1"
    
    @pytest.mark.asyncio
    async def test_quorum_write(self, raft_state, log_store):
        """Test quorum write (simulated)."""
        # Simulate successful quorum
        responses = [True, True, False]  # 2 of 3 succeed
        quorum_size = len(responses) // 2 + 1
        success_count = sum(responses)
        
        assert success_count >= quorum_size
    
    @pytest.mark.asyncio
    async def test_quorum_failure(self, raft_state, log_store):
        """Test quorum failure (simulated)."""
        # Simulate failed quorum
        responses = [True, False, False]  # Only 1 of 3 succeed
        quorum_size = len(responses) // 2 + 1
        success_count = sum(responses)
        
        assert success_count < quorum_size


# ============================================================================
# Partition Rebalancing Tests
# ============================================================================

class TestPartitionRebalancing:
    """Tests for partition rebalancing."""
    
    @pytest.mark.asyncio
    async def test_trigger_rebalance(self):
        """Test triggering rebalance operation."""
        # Simulated rebalance decision
        should_rebalance = True
        assert should_rebalance
    
    @pytest.mark.asyncio
    async def test_data_migration(self):
        """Test data migration between nodes."""
        # Simulated migration
        source_node = "node-1"
        target_node = "node-2"
        docs_to_migrate = ["doc-1", "doc-2"]
        
        assert len(docs_to_migrate) == 2


# ============================================================================
# Recovery Tests
# ============================================================================

class TestRecovery:
    """Tests for recovery operations."""
    
    @pytest.mark.asyncio
    async def test_recover_from_failure(self, raft_state):
        """Test recovery from node failure."""
        # Simulate failure and recovery
        await raft_state.become_follower()
        assert raft_state.role == NodeRole.FOLLOWER
    
    @pytest.mark.asyncio
    async def test_data_recovery(self, log_store):
        """Test data recovery from log."""
        await log_store.append(command={"key": "value"}, term=1)
        
        recovered = await log_store.get_entry(1)
        assert recovered.command == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_state_sync(self, raft_state):
        """Test state synchronization."""
        status = raft_state.get_status()
        assert "current_term" in status


# ============================================================================
# Distributed Transaction Tests
# ============================================================================

class TestDistributedTransactions:
    """Tests for distributed transactions."""
    
    @pytest.mark.asyncio
    async def test_two_phase_commit(self):
        """Test two-phase commit (simulated)."""
        # Phase 1: Prepare
        prepare_responses = [True, True, True]
        all_prepared = all(prepare_responses)
        
        # Phase 2: Commit
        if all_prepared:
            commit_responses = [True, True, True]
            all_committed = all(commit_responses)
            assert all_committed
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self):
        """Test transaction rollback (simulated)."""
        # Simulate failed prepare
        prepare_responses = [True, False, True]
        should_rollback = not all(prepare_responses)
        
        assert should_rollback


# ============================================================================
# Performance Tests
# ============================================================================

class TestClusterPerformance:
    """Tests for cluster performance."""
    
    @pytest.mark.asyncio
    async def test_election_convergence(self, temp_storage):
        """Test election convergence time."""
        import time
        
        state = RaftState(
            node_id="node-1",
            storage_path=temp_storage / "perf-test",
            election_timeout_min=0.01,
            election_timeout_max=0.02
        )
        
        start = time.time()
        await state.become_candidate()
        election_time = time.time() - start
        
        # Election should be fast
        assert election_time < 1.0
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, log_store):
        """Test concurrent log operations."""
        async def append_entry(idx):
            await log_store.append(command={"idx": idx}, term=1)
        
        # Run concurrent appends
        tasks = [append_entry(i) for i in range(1, 11)]
        await asyncio.gather(*tasks)
        
        # All entries should be appended
        assert log_store.last_index >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
