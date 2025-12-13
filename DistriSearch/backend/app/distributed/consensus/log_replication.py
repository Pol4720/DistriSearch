"""
Log Replication for Raft.

Implements the log replication mechanism:
- AppendEntries RPCs from leader to followers
- Consistency checks
- Commit index advancement
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, Callable, Awaitable, Any
from datetime import datetime

from .raft_state import RaftState, NodeRole
from .log_entry import LogStore, LogEntry

logger = logging.getLogger(__name__)


@dataclass
class AppendEntriesArgs:
    """Arguments for AppendEntries RPC."""
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[Dict[str, Any]]  # Serialized LogEntry objects
    leader_commit: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term": self.term,
            "leader_id": self.leader_id,
            "prev_log_index": self.prev_log_index,
            "prev_log_term": self.prev_log_term,
            "entries": self.entries,
            "leader_commit": self.leader_commit,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppendEntriesArgs":
        """Create from dictionary."""
        return cls(
            term=data["term"],
            leader_id=data["leader_id"],
            prev_log_index=data["prev_log_index"],
            prev_log_term=data["prev_log_term"],
            entries=data.get("entries", []),
            leader_commit=data["leader_commit"],
        )


@dataclass
class AppendEntriesReply:
    """Reply for AppendEntries RPC."""
    term: int
    success: bool
    match_index: int = 0  # Highest index replicated (for optimization)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term": self.term,
            "success": self.success,
            "match_index": self.match_index,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppendEntriesReply":
        """Create from dictionary."""
        return cls(
            term=data["term"],
            success=data["success"],
            match_index=data.get("match_index", 0),
        )


# Type for sending AppendEntries RPC
AppendEntriesSender = Callable[
    [str, AppendEntriesArgs],
    Awaitable[Optional[AppendEntriesReply]]
]


class LogReplicator:
    """
    Log replication mechanism for Raft.
    
    The leader uses this to replicate log entries to
    followers and maintain consistency.
    """
    
    def __init__(
        self,
        state: RaftState,
        log_store: LogStore,
        send_append_entries: AppendEntriesSender,
        max_entries_per_request: int = 100,
    ):
        """
        Initialize log replicator.
        
        Args:
            state: Raft state manager
            log_store: Log entry storage
            send_append_entries: Function to send AppendEntries RPC
            max_entries_per_request: Max entries per AppendEntries RPC
        """
        self.state = state
        self.log_store = log_store
        self.send_append_entries = send_append_entries
        self.max_entries_per_request = max_entries_per_request
        
        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Replication tasks per follower
        self._replication_tasks: Dict[str, asyncio.Task] = {}
        
        # Pending commit callbacks
        self._commit_callbacks: Dict[int, asyncio.Event] = {}
        
        logger.info(f"LogReplicator initialized for node {state.node_id}")
    
    async def start_heartbeats(self):
        """Start sending periodic heartbeats (leader only)."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return
        
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Started heartbeat loop")
    
    async def stop_heartbeats(self):
        """Stop sending heartbeats."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self._heartbeat_task = None
        
        # Cancel all replication tasks
        for task in self._replication_tasks.values():
            task.cancel()
        self._replication_tasks = {}
    
    async def _heartbeat_loop(self):
        """Periodically send heartbeats to all followers."""
        try:
            while self.state.is_leader:
                await self._send_heartbeats()
                await asyncio.sleep(self.state.heartbeat_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
    
    async def _send_heartbeats(self):
        """Send heartbeat (empty AppendEntries) to all followers."""
        if not self.state.is_leader:
            return
        
        cluster_nodes = self.state.cluster_nodes
        tasks = []
        
        for node_id in cluster_nodes.keys():
            if node_id == self.state.node_id:
                continue
            tasks.append(self._replicate_to_follower(node_id))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def replicate_entry(self, entry: LogEntry) -> bool:
        """
        Replicate a new entry to all followers.
        
        Waits until the entry is committed (replicated to majority).
        
        Args:
            entry: The entry to replicate
            
        Returns:
            True if entry was committed
        """
        if not self.state.is_leader:
            return False
        
        # Create event for commit notification
        commit_event = asyncio.Event()
        self._commit_callbacks[entry.index] = commit_event
        
        try:
            # Trigger immediate replication
            await self._send_heartbeats()
            
            # Wait for commit (with timeout)
            try:
                await asyncio.wait_for(commit_event.wait(), timeout=5.0)
                return True
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for commit of entry {entry.index}")
                return False
        finally:
            self._commit_callbacks.pop(entry.index, None)
    
    async def _replicate_to_follower(self, follower_id: str):
        """
        Replicate log entries to a single follower.
        
        Args:
            follower_id: Target follower node ID
        """
        if not self.state.is_leader or not self.state.leader_state:
            return
        
        # Get next index for this follower
        next_index = self.state.leader_state.next_index.get(
            follower_id,
            self.log_store.last_index + 1,
        )
        
        # Get previous log info
        prev_log_index = next_index - 1
        prev_log_term = await self.log_store.get_term_at_index(prev_log_index)
        
        # Get entries to send
        entries = await self.log_store.get_entries_from(
            next_index,
            self.max_entries_per_request,
        )
        
        # Prepare args
        args = AppendEntriesArgs(
            term=self.state.current_term,
            leader_id=self.state.node_id,
            prev_log_index=prev_log_index,
            prev_log_term=prev_log_term,
            entries=[e.to_dict() for e in entries],
            leader_commit=self.state.volatile.commit_index,
        )
        
        try:
            reply = await self.send_append_entries(follower_id, args)
            
            if reply is None:
                logger.debug(f"No response from {follower_id}")
                return
            
            await self._handle_append_entries_reply(follower_id, args, reply)
            
        except Exception as e:
            logger.warning(f"Error replicating to {follower_id}: {e}")
    
    async def _handle_append_entries_reply(
        self,
        follower_id: str,
        args: AppendEntriesArgs,
        reply: AppendEntriesReply,
    ):
        """
        Handle response from AppendEntries RPC.
        
        Args:
            follower_id: The responding follower
            args: Original request args
            reply: The response
        """
        # Check if we should step down
        if reply.term > self.state.current_term:
            await self.state.update_term(reply.term)
            await self.stop_heartbeats()
            return
        
        if not self.state.is_leader:
            return
        
        if reply.success:
            # Update match_index and next_index
            if args.entries:
                new_match_index = args.prev_log_index + len(args.entries)
            else:
                new_match_index = args.prev_log_index
            
            await self.state.update_match_index(follower_id, new_match_index)
            
            # Check if we can advance commit index
            await self._maybe_advance_commit_index()
        else:
            # Decrement next_index and retry
            await self.state.decrement_next_index(follower_id)
            logger.debug(
                f"AppendEntries rejected by {follower_id}, "
                f"decrementing next_index"
            )
    
    async def _maybe_advance_commit_index(self):
        """
        Advance commit index if majority have replicated.
        
        From Raft paper: If there exists an N such that N > commitIndex,
        a majority of matchIndex[i] >= N, and log[N].term == currentTerm:
        set commitIndex = N.
        """
        if not self.state.is_leader or not self.state.leader_state:
            return
        
        # Get all match indices (including leader's)
        match_indices = list(self.state.leader_state.match_index.values())
        match_indices.append(self.log_store.last_index)  # Leader's own
        
        # Sort to find median
        match_indices.sort(reverse=True)
        
        # Majority index
        majority_count = len(match_indices) // 2
        if majority_count < len(match_indices):
            potential_commit = match_indices[majority_count]
            
            # Only commit entries from current term
            term_at_index = await self.log_store.get_term_at_index(potential_commit)
            
            if (
                potential_commit > self.state.volatile.commit_index and
                term_at_index == self.state.current_term
            ):
                old_commit = self.state.volatile.commit_index
                await self.state.update_commit_index(potential_commit)
                
                logger.info(
                    f"Advanced commit index from {old_commit} to {potential_commit}"
                )
                
                # Notify waiting callers
                for index in range(old_commit + 1, potential_commit + 1):
                    event = self._commit_callbacks.get(index)
                    if event:
                        event.set()
    
    async def handle_append_entries(
        self,
        args: AppendEntriesArgs,
    ) -> AppendEntriesReply:
        """
        Handle incoming AppendEntries RPC (for followers).
        
        Args:
            args: AppendEntries arguments
            
        Returns:
            AppendEntries reply
        """
        # Update term if necessary
        if args.term > self.state.current_term:
            await self.state.update_term(args.term)
        
        # Reject if term is old
        if args.term < self.state.current_term:
            return AppendEntriesReply(
                term=self.state.current_term,
                success=False,
            )
        
        # Valid leader, become follower if needed
        if self.state.role != NodeRole.FOLLOWER:
            await self.state.become_follower(args.leader_id)
        
        # Record heartbeat
        await self.state.record_heartbeat(args.leader_id)
        
        # Check log consistency
        if args.prev_log_index > 0:
            matches = await self.log_store.match_term_at_index(
                args.prev_log_index,
                args.prev_log_term,
            )
            if not matches:
                return AppendEntriesReply(
                    term=self.state.current_term,
                    success=False,
                )
        
        # Append entries
        if args.entries:
            entries = [LogEntry.from_dict(e) for e in args.entries]
            success = await self.log_store.append_entries(
                entries,
                args.prev_log_index,
                args.prev_log_term,
            )
            if not success:
                return AppendEntriesReply(
                    term=self.state.current_term,
                    success=False,
                )
        
        # Update commit index
        if args.leader_commit > self.state.volatile.commit_index:
            new_commit = min(args.leader_commit, self.log_store.last_index)
            await self.state.update_commit_index(new_commit)
        
        return AppendEntriesReply(
            term=self.state.current_term,
            success=True,
            match_index=self.log_store.last_index,
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get replicator status for monitoring."""
        return {
            "heartbeat_active": (
                self._heartbeat_task is not None and
                not self._heartbeat_task.done()
            ),
            "pending_commits": len(self._commit_callbacks),
            "last_log_index": self.log_store.last_index,
            "commit_index": self.state.volatile.commit_index,
        }
