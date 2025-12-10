"""
Leader Election for Raft.

Implements the leader election mechanism including:
- Election timeouts
- RequestVote RPCs
- Vote counting and election victory
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Optional, Dict, Callable, Awaitable, Any, List
from datetime import datetime

from app.distributed.consensus.raft_state import RaftState, NodeRole
from app.distributed.consensus.log_entry import LogStore

logger = logging.getLogger(__name__)


@dataclass
class RequestVoteArgs:
    """Arguments for RequestVote RPC."""
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term": self.term,
            "candidate_id": self.candidate_id,
            "last_log_index": self.last_log_index,
            "last_log_term": self.last_log_term,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequestVoteArgs":
        """Create from dictionary."""
        return cls(
            term=data["term"],
            candidate_id=data["candidate_id"],
            last_log_index=data["last_log_index"],
            last_log_term=data["last_log_term"],
        )


@dataclass
class RequestVoteReply:
    """Reply for RequestVote RPC."""
    term: int
    vote_granted: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term": self.term,
            "vote_granted": self.vote_granted,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequestVoteReply":
        """Create from dictionary."""
        return cls(
            term=data["term"],
            vote_granted=data["vote_granted"],
        )


# Type for sending RequestVote RPC
RequestVoteSender = Callable[
    [str, RequestVoteArgs],
    Awaitable[Optional[RequestVoteReply]]
]


class LeaderElection:
    """
    Leader election mechanism for Raft.
    
    Handles election timeouts, vote requesting, and
    transitioning between candidate and leader states.
    """
    
    def __init__(
        self,
        state: RaftState,
        log_store: LogStore,
        send_request_vote: RequestVoteSender,
    ):
        """
        Initialize leader election.
        
        Args:
            state: Raft state manager
            log_store: Log entry storage
            send_request_vote: Function to send RequestVote RPC to a node
        """
        self.state = state
        self.log_store = log_store
        self.send_request_vote = send_request_vote
        
        # Election state
        self._election_timer: Optional[asyncio.Task] = None
        self._election_in_progress = False
        self._votes_received: Dict[str, bool] = {}
        
        # Lock for election operations
        self._lock = asyncio.Lock()
        
        logger.info(f"LeaderElection initialized for node {state.node_id}")
    
    def _get_election_timeout(self) -> float:
        """Get randomized election timeout."""
        return random.uniform(
            self.state.election_timeout_min,
            self.state.election_timeout_max,
        )
    
    async def start_election_timer(self):
        """Start or reset the election timeout timer."""
        await self.stop_election_timer()
        
        timeout = self._get_election_timeout()
        self._election_timer = asyncio.create_task(
            self._election_timer_task(timeout)
        )
        logger.debug(f"Election timer started with timeout {timeout:.3f}s")
    
    async def stop_election_timer(self):
        """Stop the election timeout timer."""
        if self._election_timer and not self._election_timer.done():
            self._election_timer.cancel()
            try:
                await self._election_timer
            except asyncio.CancelledError:
                pass
        self._election_timer = None
    
    async def _election_timer_task(self, timeout: float):
        """
        Election timeout task.
        
        If we don't hear from leader before timeout,
        start an election.
        """
        try:
            await asyncio.sleep(timeout)
            
            # Check if we should start election
            if self.state.role != NodeRole.LEADER:
                logger.info(
                    f"Election timeout expired for node {self.state.node_id}, "
                    f"starting election"
                )
                await self.start_election()
        except asyncio.CancelledError:
            pass
    
    async def start_election(self):
        """
        Start a new election.
        
        1. Increment current term
        2. Vote for self
        3. Reset election timer
        4. Send RequestVote to all other servers
        """
        async with self._lock:
            if self._election_in_progress:
                return
            self._election_in_progress = True
        
        try:
            # Become candidate
            new_term = await self.state.become_candidate()
            
            # Reset votes (we vote for ourselves)
            self._votes_received = {self.state.node_id: True}
            
            # Get last log info for log comparison
            last_log_index = self.log_store.last_index
            last_log_term = self.log_store.last_term
            
            # Prepare RequestVote args
            args = RequestVoteArgs(
                term=new_term,
                candidate_id=self.state.node_id,
                last_log_index=last_log_index,
                last_log_term=last_log_term,
            )
            
            # Send RequestVote to all other nodes in parallel
            cluster_nodes = self.state.cluster_nodes
            other_nodes = [
                node_id for node_id in cluster_nodes.keys()
                if node_id != self.state.node_id
            ]
            
            if not other_nodes:
                # Single node cluster, we win immediately
                logger.info("Single node cluster, becoming leader")
                await self._win_election()
                return
            
            # Send requests in parallel
            tasks = [
                self._request_vote_from(node_id, args)
                for node_id in other_nodes
            ]
            
            # Restart election timer
            await self.start_election_timer()
            
            # Wait for responses
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check if we won
            await self._check_election_victory()
            
        finally:
            async with self._lock:
                self._election_in_progress = False
    
    async def _request_vote_from(
        self,
        node_id: str,
        args: RequestVoteArgs,
    ):
        """
        Send RequestVote to a single node and process response.
        
        Args:
            node_id: Target node ID
            args: RequestVote arguments
        """
        try:
            reply = await self.send_request_vote(node_id, args)
            
            if reply is None:
                logger.debug(f"No response from {node_id} for RequestVote")
                return
            
            # Check if we should step down
            if reply.term > self.state.current_term:
                await self.state.update_term(reply.term)
                await self.state.become_follower()
                await self.start_election_timer()
                return
            
            # Record vote
            if reply.vote_granted:
                self._votes_received[node_id] = True
                logger.info(
                    f"Received vote from {node_id} for term {args.term}"
                )
            
        except Exception as e:
            logger.warning(f"Error requesting vote from {node_id}: {e}")
    
    async def _check_election_victory(self):
        """Check if we've received enough votes to become leader."""
        if self.state.role != NodeRole.CANDIDATE:
            return
        
        total_nodes = len(self.state.cluster_nodes)
        if total_nodes == 0:
            total_nodes = 1  # At least ourselves
            
        votes = sum(1 for granted in self._votes_received.values() if granted)
        majority = (total_nodes // 2) + 1
        
        logger.debug(
            f"Election votes: {votes}/{total_nodes} (need {majority})"
        )
        
        if votes >= majority:
            await self._win_election()
    
    async def _win_election(self):
        """Handle winning the election."""
        if self.state.role != NodeRole.CANDIDATE:
            return
        
        logger.info(
            f"Node {self.state.node_id} won election for term "
            f"{self.state.current_term}"
        )
        
        # Stop election timer
        await self.stop_election_timer()
        
        # Become leader
        await self.state.become_leader(self.log_store.last_index)
        
        # Clear votes
        self._votes_received = {}
    
    async def handle_request_vote(
        self,
        args: RequestVoteArgs,
    ) -> RequestVoteReply:
        """
        Handle incoming RequestVote RPC.
        
        Grant vote if:
        1. Term >= currentTerm
        2. Haven't voted in this term, or voted for this candidate
        3. Candidate's log is at least as up-to-date as ours
        
        Args:
            args: RequestVote arguments
            
        Returns:
            RequestVote reply
        """
        # Update term if necessary
        if args.term > self.state.current_term:
            await self.state.update_term(args.term)
            await self.state.become_follower()
        
        # Reject if term is old
        if args.term < self.state.current_term:
            return RequestVoteReply(
                term=self.state.current_term,
                vote_granted=False,
            )
        
        # Check if we can vote for this candidate
        can_vote = (
            self.state.persistent.voted_for is None or
            self.state.persistent.voted_for == args.candidate_id
        )
        
        if not can_vote:
            return RequestVoteReply(
                term=self.state.current_term,
                vote_granted=False,
            )
        
        # Check if candidate's log is at least as up-to-date
        if not self._is_log_up_to_date(args.last_log_index, args.last_log_term):
            return RequestVoteReply(
                term=self.state.current_term,
                vote_granted=False,
            )
        
        # Grant vote
        await self.state.vote_for(args.candidate_id)
        
        # Reset election timer (we just heard from a candidate)
        await self.start_election_timer()
        
        return RequestVoteReply(
            term=self.state.current_term,
            vote_granted=True,
        )
    
    def _is_log_up_to_date(
        self,
        candidate_last_index: int,
        candidate_last_term: int,
    ) -> bool:
        """
        Check if candidate's log is at least as up-to-date as ours.
        
        Raft determines which of two logs is more up-to-date
        by comparing the index and term of the last entries.
        
        Args:
            candidate_last_index: Candidate's last log index
            candidate_last_term: Candidate's last log term
            
        Returns:
            True if candidate's log is at least as up-to-date
        """
        my_last_term = self.log_store.last_term
        my_last_index = self.log_store.last_index
        
        # If the logs have last entries with different terms,
        # the log with the later term is more up-to-date
        if candidate_last_term != my_last_term:
            return candidate_last_term > my_last_term
        
        # If the logs end with the same term,
        # the longer log is more up-to-date
        return candidate_last_index >= my_last_index
    
    def reset_votes(self):
        """Reset vote tracking for new term."""
        self._votes_received = {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get election status for monitoring."""
        return {
            "election_in_progress": self._election_in_progress,
            "votes_received": len(self._votes_received),
            "timer_active": (
                self._election_timer is not None and
                not self._election_timer.done()
            ),
        }
