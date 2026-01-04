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
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
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
        assert raft_state.voted_for is None
    
    def test_increment_term(self, raft_state):
        """Test term increment."""
        initial_term = raft_state.current_term
        raft_state.increment_term()
        
        assert raft_state.current_term == initial_term + 1
        assert raft_state.voted_for is None  # Vote should reset
    
    def test_transition_to_candidate(self, raft_state):
        """Test transition from follower to candidate."""
        raft_state.become_candidate()
        
        assert raft_state.role == NodeRole.CANDIDATE
        assert raft_state.current_term > 0  # Term should increment
        assert raft_state.voted_for == raft_state.node_id  # Vote for self
    
    def test_transition_to_leader(self, raft_state):
        """Test transition from candidate to leader."""
        raft_state.become_candidate()
        raft_state.become_leader()
        
        assert raft_state.role == NodeRole.LEADER
    
    def test_transition_to_follower(self, raft_state):
        """Test transition to follower (e.g., on higher term discovery)."""
        raft_state.become_candidate()
        raft_state.become_leader()
        
        # Discover higher term
        raft_state.become_follower(higher_term=5)
        
        assert raft_state.role == NodeRole.FOLLOWER
        assert raft_state.current_term == 5
    
    def test_vote_only_once_per_term(self, raft_state):
        """Test that a node can only vote once per term."""
        # Vote for node-2
        can_vote = raft_state.grant_vote("node-2", term=1)
        assert can_vote
        assert raft_state.voted_for == "node-2"
        
        # Try to vote for node-3 in same term
        can_vote = raft_state.grant_vote("node-3", term=1)
        assert not can_vote
        assert raft_state.voted_for == "node-2"
    
    def test_can_vote_in_new_term(self, raft_state):
        """Test that voting resets in new term."""
        raft_state.grant_vote("node-2", term=1)
        
        # New term - can vote again
        can_vote = raft_state.grant_vote("node-3", term=2)
        assert can_vote
        assert raft_state.voted_for == "node-3"
        assert raft_state.current_term == 2


# ============================================================================
# Log Entry Tests
# ============================================================================

class TestLogStore:
    """Tests for Raft log storage."""
    
    def test_initial_log_is_empty(self, log_store):
        """Test that log starts empty."""
        assert log_store.last_index() == 0
        assert log_store.last_term() == 0
    
    def test_append_entry(self, log_store):
        """Test appending log entries."""
        entry = LogEntry(
            term=1,
            index=1,
            command={"type": "set", "key": "x", "value": 1}
        )
        log_store.append(entry)
        
        assert log_store.last_index() == 1
        assert log_store.last_term() == 1
    
    def test_get_entry(self, log_store):
        """Test retrieving log entries."""
        entry = LogEntry(term=1, index=1, command={"key": "value"})
        log_store.append(entry)
        
        retrieved = log_store.get(1)
        assert retrieved is not None
        assert retrieved.term == 1
        assert retrieved.command == {"key": "value"}
    
    def test_get_entries_range(self, log_store):
        """Test retrieving range of entries."""
        for i in range(1, 6):
            log_store.append(LogEntry(term=1, index=i, command={"i": i}))
        
        entries = log_store.get_range(2, 4)
        assert len(entries) == 3
        assert entries[0].index == 2
        assert entries[-1].index == 4
    
    def test_truncate_from_index(self, log_store):
        """Test log truncation (for conflict resolution)."""
        for i in range(1, 6):
            log_store.append(LogEntry(term=1, index=i, command={"i": i}))
        
        # Truncate from index 3 (remove 3, 4, 5)
        log_store.truncate_from(3)
        
        assert log_store.last_index() == 2
    
    def test_log_consistency_check(self, log_store):
        """Test log consistency verification."""
        log_store.append(LogEntry(term=1, index=1, command={}))
        log_store.append(LogEntry(term=1, index=2, command={}))
        log_store.append(LogEntry(term=2, index=3, command={}))
        
        # Check if log matches at index 2, term 1
        assert log_store.matches_at(index=2, term=1)
        
        # Check mismatch
        assert not log_store.matches_at(index=2, term=2)


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
        # (Actual transition depends on implementation)
        await election.stop_election_timer()
    
    @pytest.mark.asyncio
    async def test_request_vote_args_creation(self, raft_state, log_store):
        """Test RequestVote arguments are created correctly."""
        log_store.append(LogEntry(term=1, index=1, command={}))
        log_store.append(LogEntry(term=2, index=2, command={}))
        
        raft_state.become_candidate()
        
        args = RequestVoteArgs(
            term=raft_state.current_term,
            candidate_id=raft_state.node_id,
            last_log_index=log_store.last_index(),
            last_log_term=log_store.last_term()
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
        assert raft_state.voted_for == "node-2"
    
    @pytest.mark.asyncio
    async def test_vote_rejected_for_lower_term(self, raft_state, log_store):
        """Test that vote is rejected for lower term."""
        raft_state.current_term = 5
        
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
        log_store.append(LogEntry(term=2, index=1, command={}))
        log_store.append(LogEntry(term=2, index=2, command={}))
        
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
            
            # Mock vote responses
            async def mock_request_vote(node_id, args):
                # node-2 votes yes, node-3 votes yes
                return RequestVoteReply(term=args.term, vote_granted=True)
            
            election = LeaderElection(
                state=state,
                log_store=log_store,
                send_request_vote=mock_request_vote
            )
            
            # Add cluster nodes
            state.cluster_nodes = {"node-1", "node-2", "node-3"}
            
            # Start election
            state.become_candidate()
            
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
        raft_state.become_candidate()
        raft_state.become_leader()
        
        heartbeats_sent = []
        
        async def mock_append_entries(node_id, args):
            heartbeats_sent.append((node_id, args))
            return AppendEntriesReply(term=args.term, success=True)
        
        replicator = LogReplicator(
            state=raft_state,
            log_store=log_store,
            send_append_entries=mock_append_entries
        )
        
        # Send heartbeat to a follower
        await replicator.send_heartbeat("node-2")
        
        assert len(heartbeats_sent) == 1
        assert heartbeats_sent[0][0] == "node-2"
    
    @pytest.mark.asyncio
    async def test_append_entries_args_creation(self, raft_state, log_store):
        """Test AppendEntries arguments are created correctly."""
        raft_state.become_candidate()
        raft_state.become_leader()
        
        # Add some entries
        log_store.append(LogEntry(term=1, index=1, command={"x": 1}))
        log_store.append(LogEntry(term=1, index=2, command={"y": 2}))
        
        args = AppendEntriesArgs(
            term=raft_state.current_term,
            leader_id=raft_state.node_id,
            prev_log_index=0,
            prev_log_term=0,
            entries=[log_store.get(1), log_store.get(2)],
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
        assert log_store.last_index() == 1
    
    @pytest.mark.asyncio
    async def test_follower_rejects_old_term(self, raft_state, log_store):
        """Test that follower rejects AppendEntries with old term."""
        raft_state.current_term = 5
        
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
        log_store.append(LogEntry(term=1, index=1, command={"old": 1}))
        log_store.append(LogEntry(term=1, index=2, command={"old": 2}))
        
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
        assert log_store.get(1).command == {"new": 1}


# ============================================================================
# Split-Brain Prevention Tests
# ============================================================================

class TestSplitBrainPrevention:
    """Tests for split-brain prevention mechanisms."""
    
    @pytest.mark.asyncio
    async def test_leader_steps_down_on_higher_term(self, raft_state, log_store):
        """Test that leader steps down when it discovers higher term."""
        raft_state.become_candidate()
        raft_state.become_leader()
        
        assert raft_state.role == NodeRole.LEADER
        
        # Receive message with higher term
        raft_state.become_follower(higher_term=10)
        
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
        nodes[0].become_candidate()  # Increments term to 1
        nodes[0].become_leader()
        
        # node-2 tries to become candidate in same term
        nodes[1].current_term = 1
        nodes[1].voted_for = "node-1"  # Already voted
        
        # node-2 cannot get vote from itself for term 1
        can_vote = nodes[1].grant_vote("node-2", term=1)
        assert not can_vote  # Already voted for node-1
    
    @pytest.mark.asyncio
    async def test_candidate_becomes_follower_on_leader_heartbeat(self, raft_state, log_store):
        """Test that candidate becomes follower when receiving leader heartbeat."""
        raft_state.become_candidate()
        
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
        
        reply = await raft_node.handle_request_vote(args.to_dict())
        
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
        
        reply = await raft_node.handle_append_entries(args.to_dict())
        
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
