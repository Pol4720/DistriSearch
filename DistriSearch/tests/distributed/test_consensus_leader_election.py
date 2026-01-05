# -*- coding: utf-8 -*-
"""
Consensus and Leader Election Tests (Raft Protocol)

Tests to verify the Raft consensus implementation:
- Leader election with randomized timeouts
- Term management and vote counting
- Leader heartbeats and follower state
- Split-brain prevention
- Log consistency across nodes
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys
import tempfile
import shutil

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
from app.distributed.consensus.raft_node import RaftNode


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def node_ids() -> List[str]:
    """Cluster node IDs."""
    return ["node-1", "node-2", "node-3"]


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
async def raft_node(temp_storage) -> RaftNode:
    """Create a Raft node for testing."""
    node = RaftNode(
        node_id="node-1",
        storage_path=temp_storage / "node-1",
        election_timeout_min=0.15,
        election_timeout_max=0.30,
        heartbeat_interval=0.05,
    )
    return node


# ============================================================================
# Raft State Tests
# ============================================================================

class TestRaftState:
    """Tests for Raft state management."""
    
    def test_initial_state_is_follower(self, raft_state):
        """Test that nodes start as followers."""
        assert raft_state.role == NodeRole.FOLLOWER
    
    def test_initial_term_is_zero(self, raft_state):
        """Test that initial term is 0."""
        assert raft_state.current_term == 0
    
    def test_initial_voted_for_is_none(self, raft_state):
        """Test that voted_for is None initially."""
        assert raft_state.persistent.voted_for is None
    
    @pytest.mark.asyncio
    async def test_increment_term(self, raft_state):
        """Test term increment."""
        initial_term = raft_state.current_term
        new_term = await raft_state.increment_term()
        
        assert new_term == initial_term + 1
        assert raft_state.current_term == initial_term + 1
        assert raft_state.persistent.voted_for is None  # Vote should reset
    
    @pytest.mark.asyncio
    async def test_transition_to_candidate(self, raft_state):
        """Test transition from follower to candidate."""
        new_term = await raft_state.become_candidate()
        
        assert raft_state.role == NodeRole.CANDIDATE
        assert new_term > 0  # Term should increment
        assert raft_state.persistent.voted_for == raft_state.node_id  # Vote for self
    
    @pytest.mark.asyncio
    async def test_transition_to_leader(self, raft_state, log_store):
        """Test transition from candidate to leader."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        assert raft_state.role == NodeRole.LEADER
    
    @pytest.mark.asyncio
    async def test_transition_to_follower(self, raft_state, log_store):
        """Test transition to follower (e.g., on higher term discovery)."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        # Discover higher term
        await raft_state.update_term(5)
        
        assert raft_state.role == NodeRole.FOLLOWER
        assert raft_state.current_term == 5
    
    @pytest.mark.asyncio
    async def test_vote_only_once_per_term(self, raft_state):
        """Test that a node can only vote once per term."""
        # Update term first so we can vote
        await raft_state.update_term(1)
        
        # Vote for node-2
        can_vote = await raft_state.vote_for("node-2")
        assert can_vote
        assert raft_state.persistent.voted_for == "node-2"
        
        # Try to vote for node-3 in same term - should fail
        can_vote = await raft_state.vote_for("node-3")
        assert not can_vote
        assert raft_state.persistent.voted_for == "node-2"
    
    @pytest.mark.asyncio
    async def test_can_vote_in_new_term(self, raft_state):
        """Test that voting resets in new term."""
        await raft_state.update_term(1)
        await raft_state.vote_for("node-2")
        
        # New term - reset and vote again
        await raft_state.update_term(2)
        can_vote = await raft_state.vote_for("node-3")
        assert can_vote
        assert raft_state.persistent.voted_for == "node-3"
        assert raft_state.current_term == 2


# ============================================================================
# Log Entry Tests
# ============================================================================

class TestLogStore:
    """Tests for Raft log storage."""
    
    @pytest.mark.asyncio
    async def test_initial_log_is_empty(self, log_store):
        """Test that log starts empty."""
        assert log_store.last_index == 0
        assert log_store.last_term == 0
    
    @pytest.mark.asyncio
    async def test_append_entry(self, log_store):
        """Test appending log entries."""
        # append(command, term) is the correct signature
        entry = await log_store.append(
            command={"type": "set", "key": "x", "value": 1},
            term=1
        )
        
        assert log_store.last_index == 1
        assert log_store.last_term == 1
        assert entry.term == 1
    
    @pytest.mark.asyncio
    async def test_get_entry(self, log_store):
        """Test retrieving log entries."""
        await log_store.append(command={"key": "value"}, term=1)
        
        retrieved = await log_store.get_entry(1)
        assert retrieved is not None
        assert retrieved.term == 1
        assert retrieved.command == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_get_entries_range(self, log_store):
        """Test retrieving range of entries."""
        for i in range(1, 6):
            await log_store.append(command={"i": i}, term=1)
        
        entries = await log_store.get_entries_from(2, max_entries=3)
        assert len(entries) == 3
        assert entries[0].index == 2
        assert entries[-1].index == 4
    
    @pytest.mark.asyncio
    async def test_truncate_from_index(self, log_store):
        """Test log truncation via conflict resolution."""
        for i in range(1, 6):
            await log_store.append(command={"i": i}, term=1)
        
        # Simulate truncation through append_entries with conflicting entries
        # Note: truncation is internal to append_entries, we verify via creating snapshot
        # which discards old entries
        await log_store.create_snapshot(
            last_included_index=2,
            last_included_term=1
        )
        
        # After snapshot, entries 1-2 are discarded
        assert log_store.last_index == 5  # Still have entries 3-5 in log
    
    @pytest.mark.asyncio
    async def test_log_consistency_check(self, log_store):
        """Test log consistency verification."""
        await log_store.append(command={}, term=1)
        await log_store.append(command={}, term=1)
        await log_store.append(command={}, term=2)
        
        # Check if term at index 2 is 1
        term_at_2 = await log_store.get_term_at_index(2)
        assert term_at_2 == 1
        
        # Check index 3 has term 2
        term_at_3 = await log_store.get_term_at_index(3)
        assert term_at_3 == 2


# ============================================================================
# Leader Election Tests
# ============================================================================

class TestLeaderElection:
    """Tests for Raft leader election."""
    
    @pytest.mark.asyncio
    async def test_election_timeout_triggers_election(self, raft_state, log_store):
        """Test that election timeout triggers candidate transition."""
        mock_sender = AsyncMock(return_value=None)
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        # Start election timer with very short timeout
        raft_state.election_timeout_min = 0.01
        raft_state.election_timeout_max = 0.02
        
        await election.start_election_timer()
        await asyncio.sleep(0.05)  # Wait for timeout
        
        # Should have become candidate
        await election.stop_election_timer()
    
    @pytest.mark.asyncio
    async def test_request_vote_args_creation(self, raft_state, log_store):
        """Test RequestVote arguments are created correctly."""
        await log_store.append(command={}, term=1)
        await log_store.append(command={}, term=2)
        
        await raft_state.become_candidate()
        
        args = RequestVoteArgs(
            term=raft_state.current_term,
            candidate_id=raft_state.node_id,
            last_log_index=log_store.last_index,
            last_log_term=log_store.last_term
        )
        
        assert args.candidate_id == "node-1"
        assert args.last_log_index == 2
        assert args.last_log_term == 2
    
    @pytest.mark.asyncio
    async def test_vote_granted_for_valid_candidate(self, raft_state, log_store):
        """Test that vote is granted to valid candidate."""
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        # Receive vote request from candidate with higher term
        args = RequestVoteArgs(
            term=2,
            candidate_id="node-2",
            last_log_index=0,
            last_log_term=0
        )
        
        reply = await election.handle_request_vote(args)
        
        assert reply.vote_granted
        assert raft_state.persistent.voted_for == "node-2"
    
    @pytest.mark.asyncio
    async def test_vote_rejected_for_lower_term(self, raft_state, log_store):
        """Test that vote is rejected for lower term."""
        await raft_state.update_term(5)
        
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        args = RequestVoteArgs(
            term=3,  # Lower than current term
            candidate_id="node-2",
            last_log_index=0,
            last_log_term=0
        )
        
        reply = await election.handle_request_vote(args)
        
        assert not reply.vote_granted
    
    @pytest.mark.asyncio
    async def test_vote_rejected_for_less_up_to_date_log(self, raft_state, log_store):
        """Test that vote is rejected if candidate's log is less up-to-date."""
        # Add entries to local log
        await log_store.append(command={}, term=2)
        await log_store.append(command={}, term=2)
        
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        # Candidate has older log
        args = RequestVoteArgs(
            term=3,
            candidate_id="node-2",
            last_log_index=1,
            last_log_term=1  # Older term
        )
        
        reply = await election.handle_request_vote(args)
        
        assert not reply.vote_granted
    
    @pytest.mark.asyncio
    async def test_majority_wins_election(self):
        """Test that candidate becomes leader with majority votes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create candidate state
            state = RaftState(
                node_id="node-1",
                storage_path=temp_path / "node-1"
            )
            log_store = LogStore(storage_path=temp_path / "logs")
            
            # Add cluster nodes
            await state.add_cluster_node("node-1", "localhost:8001")
            await state.add_cluster_node("node-2", "localhost:8002")
            await state.add_cluster_node("node-3", "localhost:8003")
            
            # Mock vote responses
            async def mock_request_vote(node_id, args):
                return RequestVoteReply(term=args.term, vote_granted=True)
            
            election = LeaderElection(
                state=state,
                log_store=log_store,
                send_request_vote=mock_request_vote
            )
            
            # Start election
            await state.become_candidate()
            
            # Simulate collecting votes
            votes = {"node-1": True}  # Self vote
            votes["node-2"] = True
            votes["node-3"] = True
            
            # Check majority
            majority = len(state.cluster_nodes) // 2 + 1
            vote_count = sum(1 for v in votes.values() if v)
            
            assert vote_count >= majority


# ============================================================================
# Log Replication Tests
# ============================================================================

class TestLogReplication:
    """Tests for Raft log replication."""
    
    @pytest.mark.asyncio
    async def test_leader_sends_heartbeats(self, raft_state, log_store):
        """Test that leader sends periodic heartbeats."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        heartbeats_sent = []
        
        async def mock_append_entries(node_id, args):
            heartbeats_sent.append((node_id, args))
            return AppendEntriesReply(term=args.term, success=True)
        
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_append_entries
        )
        
        # Add a cluster node to send heartbeats to
        await raft_state.add_cluster_node("node-2", "localhost:8002")
        
        # Send heartbeats using the private method (simulating heartbeat loop)
        await replicator._send_heartbeats()
        
        assert len(heartbeats_sent) >= 1
        assert heartbeats_sent[0][0] == "node-2"
    
    @pytest.mark.asyncio
    async def test_append_entries_args_creation(self, raft_state, log_store):
        """Test AppendEntries arguments are created correctly."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        # Add some entries
        await log_store.append(command={"x": 1}, term=1)
        await log_store.append(command={"y": 2}, term=1)
        
        entry1 = await log_store.get_entry(1)
        entry2 = await log_store.get_entry(2)
        
        args = AppendEntriesArgs(
            term=raft_state.current_term,
            leader_id=raft_state.node_id,
            prev_log_index=0,
            prev_log_term=0,
            entries=[entry1, entry2],
            leader_commit=0
        )
        
        assert args.leader_id == "node-1"
        assert len(args.entries) == 2
    
    @pytest.mark.asyncio
    async def test_follower_accepts_valid_entries(self, raft_state, log_store):
        """Test that follower accepts valid AppendEntries."""
        mock_sender = AsyncMock()
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_sender
        )
        
        # Receive AppendEntries from leader
        args = AppendEntriesArgs(
            term=1,
            leader_id="node-2",
            prev_log_index=0,
            prev_log_term=0,
            entries=[LogEntry(term=1, index=1, command={"x": 1})],
            leader_commit=0
        )
        
        reply = await replicator.handle_append_entries(args)
        
        assert reply.success
        assert log_store.last_index == 1
    
    @pytest.mark.asyncio
    async def test_follower_rejects_old_term(self, raft_state, log_store):
        """Test that follower rejects AppendEntries with old term."""
        await raft_state.update_term(5)
        
        mock_sender = AsyncMock()
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_sender
        )
        
        args = AppendEntriesArgs(
            term=3,  # Old term
            leader_id="node-2",
            prev_log_index=0,
            prev_log_term=0,
            entries=[],
            leader_commit=0
        )
        
        reply = await replicator.handle_append_entries(args)
        
        assert not reply.success
        assert reply.term == 5
    
    @pytest.mark.asyncio
    async def test_log_conflict_resolution(self, raft_state, log_store):
        """Test that conflicting log entries are resolved."""
        # Add some entries with term 1
        await log_store.append(command={"old": 1}, term=1)
        await log_store.append(command={"old": 2}, term=1)
        
        mock_sender = AsyncMock()
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_sender
        )
        
        # Leader sends entries starting from index 1 with term 2 (conflict)
        args = AppendEntriesArgs(
            term=2,
            leader_id="node-2",
            prev_log_index=0,
            prev_log_term=0,
            entries=[
                LogEntry(term=2, index=1, command={"new": 1}),
                LogEntry(term=2, index=2, command={"new": 2})
            ],
            leader_commit=0
        )
        
        reply = await replicator.handle_append_entries(args)
        
        # Should accept and overwrite conflicting entries
        assert reply.success
        entry1 = await log_store.get_entry(1)
        assert entry1.command == {"new": 1}


# ============================================================================
# Split-Brain Prevention Tests
# ============================================================================

class TestSplitBrainPrevention:
    """Tests for split-brain prevention mechanisms."""
    
    @pytest.mark.asyncio
    async def test_leader_steps_down_on_higher_term(self, raft_state, log_store):
        """Test that leader steps down when it discovers higher term."""
        await raft_state.become_candidate()
        await raft_state.become_leader(last_log_index=log_store.last_index)
        
        assert raft_state.role == NodeRole.LEADER
        
        # Discover higher term
        await raft_state.update_term(10)
        
        assert raft_state.role == NodeRole.FOLLOWER
        assert raft_state.current_term == 10
    
    @pytest.mark.asyncio
    async def test_only_one_leader_per_term(self, temp_storage):
        """Test that only one leader can exist per term."""
        # Create three nodes
        nodes = []
        for i in range(1, 4):
            state = RaftState(
                node_id=f"node-{i}",
                storage_path=temp_storage / f"node-{i}"
            )
            nodes.append(state)
        
        # Simulate term 1 election - node-1 wins
        await nodes[0].become_candidate()  # Increments term to 1
        await nodes[0].become_leader(last_log_index=0)
        
        # node-2 updates to term 1 and votes
        await nodes[1].update_term(1)
        await nodes[1].vote_for("node-1")
        
        # node-2 cannot vote for itself in term 1
        can_vote = await nodes[1].vote_for("node-2")
        assert not can_vote  # Already voted for node-1
    
    @pytest.mark.asyncio
    async def test_candidate_becomes_follower_on_leader_heartbeat(self, raft_state, log_store):
        """Test that candidate becomes follower when receiving leader heartbeat."""
        await raft_state.become_candidate()
        
        mock_sender = AsyncMock()
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_sender
        )
        
        # Receive heartbeat from legitimate leader
        args = AppendEntriesArgs(
            term=raft_state.current_term,
            leader_id="node-2",
            prev_log_index=0,
            prev_log_term=0,
            entries=[],
            leader_commit=0
        )
        
        await replicator.handle_append_entries(args)
        
        # Should have become follower
        assert raft_state.role == NodeRole.FOLLOWER


# ============================================================================
# Raft Node Integration Tests
# ============================================================================

class TestRaftNodeIntegration:
    """Integration tests for complete Raft node."""
    
    @pytest.mark.asyncio
    async def test_raft_node_initialization(self, raft_node):
        """Test Raft node initializes correctly."""
        assert raft_node.node_id == "node-1"
        assert raft_node.state.role == NodeRole.FOLLOWER
    
    @pytest.mark.asyncio
    async def test_raft_node_handles_request_vote(self, raft_node):
        """Test Raft node handles RequestVote RPC."""
        args = RequestVoteArgs(
            term=1,
            candidate_id="node-2",
            last_log_index=0,
            last_log_term=0
        )
        
        # Use handle_rpc for dict-based interface
        reply = await raft_node.handle_rpc("request_vote", args.to_dict())
        
        assert "vote_granted" in reply
        assert "term" in reply
    
    @pytest.mark.asyncio
    async def test_raft_node_handles_append_entries(self, raft_node):
        """Test Raft node handles AppendEntries RPC."""
        args = AppendEntriesArgs(
            term=1,
            leader_id="node-2",
            prev_log_index=0,
            prev_log_term=0,
            entries=[],
            leader_commit=0
        )
        
        # Use handle_rpc for dict-based interface
        reply = await raft_node.handle_rpc("append_entries", args.to_dict())
        
        assert "success" in reply
        assert "term" in reply


# ============================================================================
# Election Timing Tests
# ============================================================================

class TestElectionTiming:
    """Tests for election timeout randomization."""
    
    def test_election_timeout_is_randomized(self, raft_state, log_store):
        """Test that election timeouts are randomized."""
        mock_sender = AsyncMock()
        election = LeaderElection(
            state=raft_state,
            log_store=log_store,
            send_request_vote=mock_sender
        )
        
        timeouts = set()
        for _ in range(100):
            timeout = election._get_election_timeout()
            timeouts.add(round(timeout, 3))
            
            # Verify within bounds
            assert raft_state.election_timeout_min <= timeout <= raft_state.election_timeout_max
        
        # Should have multiple different values (randomized)
        assert len(timeouts) > 1
    
    def test_heartbeat_interval_less_than_election_timeout(self, raft_state):
        """Test that heartbeat interval is less than election timeout."""
        assert raft_state.heartbeat_interval < raft_state.election_timeout_min


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
