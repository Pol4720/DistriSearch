"""
Raft Node Implementation.

Complete Raft node that combines all components:
- State management
- Leader election
- Log replication
- State machine
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Awaitable

from .raft_state import RaftState, NodeRole
from .log_entry import LogStore, LogEntry
from .leader_election import (
    LeaderElection,
    RequestVoteArgs,
    RequestVoteReply,
)
from .log_replication import (
    LogReplicator,
    AppendEntriesArgs,
    AppendEntriesReply,
)
from .state_machine import StateMachine, Command

logger = logging.getLogger(__name__)


# RPC sender types
RPCSender = Callable[[str, Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]]


class RaftNode:
    """
    Complete Raft consensus node.
    
    Integrates all Raft components for a fully functional
    consensus participant.
    """
    
    def __init__(
        self,
        node_id: str,
        storage_path: Optional[Path] = None,
        rpc_sender: Optional[RPCSender] = None,
        election_timeout_min: float = 0.15,
        election_timeout_max: float = 0.30,
        heartbeat_interval: float = 0.05,
    ):
        """
        Initialize Raft node.
        
        Args:
            node_id: Unique identifier for this node
            storage_path: Path for persistent storage
            rpc_sender: Function to send RPCs to other nodes
            election_timeout_min: Minimum election timeout (seconds)
            election_timeout_max: Maximum election timeout (seconds)
            heartbeat_interval: Heartbeat interval (seconds)
        """
        self.node_id = node_id
        self._rpc_sender = rpc_sender
        
        # Storage path
        self.storage_path = storage_path or Path(f"/data/raft/{node_id}")
        
        # Initialize state
        self.state = RaftState(
            node_id=node_id,
            storage_path=self.storage_path,
            election_timeout_min=election_timeout_min,
            election_timeout_max=election_timeout_max,
            heartbeat_interval=heartbeat_interval,
        )
        
        # Initialize log store
        self.log_store = LogStore(storage_path=self.storage_path)
        
        # Initialize components
        self.election = LeaderElection(
            state=self.state,
            log_store=self.log_store,
            send_request_vote=self._send_request_vote,
        )
        
        self.replicator = LogReplicator(
            state=self.state,
            log_store=self.log_store,
            send_append_entries=self._send_append_entries,
        )
        
        self.state_machine = StateMachine(
            state=self.state,
            log_store=self.log_store,
        )
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        
        logger.info(f"RaftNode {node_id} initialized")
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self.state.is_leader
    
    @property
    def current_term(self) -> int:
        """Get current term."""
        return self.state.current_term
    
    @property
    def leader_id(self) -> Optional[str]:
        """Get current leader ID."""
        return self.state.leader_id
    
    @property
    def role(self) -> NodeRole:
        """Get current role."""
        return self.state.role
    
    def set_rpc_sender(self, sender: RPCSender):
        """Set the RPC sender function."""
        self._rpc_sender = sender
    
    async def start(self):
        """Start the Raft node."""
        async with self._lock:
            if self._running:
                return
            
            self._running = True
            
            # Initialize state
            await self.state.initialize()
            await self.log_store.initialize()
            
            # Start state machine
            await self.state_machine.start()
            
            # Start election timer
            await self.election.start_election_timer()
            
            logger.info(f"RaftNode {self.node_id} started")
    
    async def stop(self):
        """Stop the Raft node."""
        async with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Stop components
            await self.election.stop_election_timer()
            await self.replicator.stop_heartbeats()
            await self.state_machine.stop()
            
            logger.info(f"RaftNode {self.node_id} stopped")
    
    async def add_peer(self, peer_id: str, address: str):
        """
        Add a peer node to the cluster.
        
        Args:
            peer_id: Peer's unique ID
            address: Peer's network address
        """
        await self.state.add_cluster_node(peer_id, address)
        logger.info(f"Added peer {peer_id} at {address}")
    
    async def remove_peer(self, peer_id: str):
        """
        Remove a peer node from the cluster.
        
        Args:
            peer_id: Peer's unique ID
        """
        await self.state.remove_cluster_node(peer_id)
        logger.info(f"Removed peer {peer_id}")
    
    async def submit_command(self, command: Command) -> bool:
        """
        Submit a command to be replicated.
        
        Only works on the leader. Waits for commitment.
        
        Args:
            command: Command to submit
            
        Returns:
            True if command was committed
        """
        if not self.is_leader:
            logger.warning("Cannot submit command: not the leader")
            return False
        
        # Append to log
        entry = await self.log_store.append(
            command=command.to_dict(),
            term=self.state.current_term,
        )
        
        logger.debug(f"Submitted command {command.type.value} as entry {entry.index}")
        
        # Replicate to followers and wait for commit
        committed = await self.replicator.replicate_entry(entry)
        
        if committed:
            # Trigger state machine apply
            self.state_machine.trigger_apply()
        
        return committed
    
    # RPC handlers
    
    async def handle_request_vote(
        self,
        args: RequestVoteArgs,
    ) -> RequestVoteReply:
        """
        Handle incoming RequestVote RPC.
        
        Args:
            args: RequestVote arguments
            
        Returns:
            RequestVote reply
        """
        return await self.election.handle_request_vote(args)
    
    async def handle_append_entries(
        self,
        args: AppendEntriesArgs,
    ) -> AppendEntriesReply:
        """
        Handle incoming AppendEntries RPC.
        
        Args:
            args: AppendEntries arguments
            
        Returns:
            AppendEntries reply
        """
        # Reset election timer on valid AppendEntries
        await self.election.start_election_timer()
        
        reply = await self.replicator.handle_append_entries(args)
        
        # Trigger state machine apply if commit index advanced
        if reply.success:
            self.state_machine.trigger_apply()
        
        return reply
    
    async def handle_rpc(
        self,
        rpc_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle incoming RPC of any type.
        
        Args:
            rpc_type: Type of RPC ("request_vote" or "append_entries")
            data: RPC data
            
        Returns:
            RPC response
        """
        if rpc_type == "request_vote":
            args = RequestVoteArgs.from_dict(data)
            reply = await self.handle_request_vote(args)
            return reply.to_dict()
        
        elif rpc_type == "append_entries":
            args = AppendEntriesArgs.from_dict(data)
            reply = await self.handle_append_entries(args)
            return reply.to_dict()
        
        else:
            logger.warning(f"Unknown RPC type: {rpc_type}")
            return {"error": f"Unknown RPC type: {rpc_type}"}
    
    # Internal RPC sending
    
    async def _send_request_vote(
        self,
        target_id: str,
        args: RequestVoteArgs,
    ) -> Optional[RequestVoteReply]:
        """Send RequestVote RPC to target node."""
        if not self._rpc_sender:
            logger.warning("No RPC sender configured")
            return None
        
        try:
            response = await self._rpc_sender(target_id, {
                "type": "request_vote",
                "data": args.to_dict(),
            })
            
            if response:
                return RequestVoteReply.from_dict(response)
            return None
            
        except Exception as e:
            logger.warning(f"Error sending RequestVote to {target_id}: {e}")
            return None
    
    async def _send_append_entries(
        self,
        target_id: str,
        args: AppendEntriesArgs,
    ) -> Optional[AppendEntriesReply]:
        """Send AppendEntries RPC to target node."""
        if not self._rpc_sender:
            logger.warning("No RPC sender configured")
            return None
        
        try:
            response = await self._rpc_sender(target_id, {
                "type": "append_entries",
                "data": args.to_dict(),
            })
            
            if response:
                return AppendEntriesReply.from_dict(response)
            return None
            
        except Exception as e:
            logger.warning(f"Error sending AppendEntries to {target_id}: {e}")
            return None
    
    # Leader-specific operations
    
    async def _become_leader_callback(self):
        """Called when this node becomes leader."""
        # Submit no-op to commit entries from previous term
        noop = Command(
            type=CommandType.NOOP,
            data={"term": self.state.current_term},
        )
        
        # Start heartbeats
        await self.replicator.start_heartbeats()
        
        # Submit no-op
        await self.submit_command(noop)
    
    # Status and monitoring
    
    def get_status(self) -> Dict[str, Any]:
        """Get complete node status for monitoring."""
        return {
            "node_id": self.node_id,
            "running": self._running,
            "state": self.state.get_status(),
            "log": self.log_store.get_status(),
            "election": self.election.get_status(),
            "replication": self.replicator.get_status(),
            "state_machine": self.state_machine.get_status(),
        }
    
    def get_cluster_state(self) -> Dict[str, Any]:
        """Get current cluster state from state machine."""
        return self.state_machine.get_full_state()


# Import CommandType for convenience
from .state_machine import CommandType
