"""
Raft State Management.

Manages persistent and volatile state for Raft consensus protocol.
Handles state transitions, term updates, and vote tracking.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """Raft node roles."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class PersistentState:
    """
    Persistent state - must be persisted to stable storage
    before responding to RPCs.
    
    Attributes:
        current_term: Latest term server has seen
        voted_for: CandidateId that received vote in current term
        log: Log entries (index starts at 1)
    """
    current_term: int = 0
    voted_for: Optional[str] = None
    # Log entries stored separately in LogStore
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "current_term": self.current_term,
            "voted_for": self.voted_for,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistentState":
        """Create from dictionary."""
        return cls(
            current_term=data.get("current_term", 0),
            voted_for=data.get("voted_for"),
        )


@dataclass
class VolatileState:
    """
    Volatile state on all servers.
    
    Attributes:
        commit_index: Index of highest log entry known to be committed
        last_applied: Index of highest log entry applied to state machine
    """
    commit_index: int = 0
    last_applied: int = 0


@dataclass
class LeaderVolatileState:
    """
    Volatile state on leaders (reinitialized after election).
    
    Attributes:
        next_index: For each server, index of next log entry to send
        match_index: For each server, index of highest log entry known to be replicated
    """
    next_index: Dict[str, int] = field(default_factory=dict)
    match_index: Dict[str, int] = field(default_factory=dict)
    
    def initialize_for_followers(self, follower_ids: list[str], last_log_index: int):
        """Initialize leader state for followers after election."""
        for follower_id in follower_ids:
            self.next_index[follower_id] = last_log_index + 1
            self.match_index[follower_id] = 0


class RaftState:
    """
    Complete Raft state management.
    
    Handles all state for a Raft node including:
    - Persistent state (saved to disk)
    - Volatile state (in memory)
    - Leader-specific state
    - Role transitions
    """
    
    def __init__(
        self,
        node_id: str,
        storage_path: Optional[Path] = None,
        election_timeout_min: float = 0.15,  # 150ms
        election_timeout_max: float = 0.30,  # 300ms
        heartbeat_interval: float = 0.05,    # 50ms
    ):
        """
        Initialize Raft state.
        
        Args:
            node_id: Unique identifier for this node
            storage_path: Path for persistent state storage
            election_timeout_min: Minimum election timeout in seconds
            election_timeout_max: Maximum election timeout in seconds
            heartbeat_interval: Heartbeat interval in seconds
        """
        self.node_id = node_id
        self.storage_path = storage_path or Path(f"/data/raft/{node_id}")
        
        # Timing configuration
        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval
        
        # State components
        self.persistent = PersistentState()
        self.volatile = VolatileState()
        self.leader_state: Optional[LeaderVolatileState] = None
        
        # Current role
        self._role = NodeRole.FOLLOWER
        self._leader_id: Optional[str] = None
        
        # Cluster membership
        self._cluster_nodes: Dict[str, str] = {}  # node_id -> address
        
        # State lock
        self._lock = asyncio.Lock()
        
        # Last heartbeat received
        self._last_heartbeat = datetime.now()
        
        logger.info(f"RaftState initialized for node {node_id}")
    
    @property
    def role(self) -> NodeRole:
        """Get current role."""
        return self._role
    
    @property
    def current_term(self) -> int:
        """Get current term."""
        return self.persistent.current_term
    
    @property
    def leader_id(self) -> Optional[str]:
        """Get current leader ID."""
        return self._leader_id
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._role == NodeRole.LEADER
    
    @property
    def cluster_nodes(self) -> Dict[str, str]:
        """Get cluster node addresses."""
        return self._cluster_nodes.copy()
    
    async def initialize(self):
        """Initialize state, loading from storage if available."""
        try:
            await self._load_persistent_state()
            logger.info(
                f"Raft state initialized: term={self.persistent.current_term}, "
                f"voted_for={self.persistent.voted_for}"
            )
        except Exception as e:
            logger.warning(f"Could not load persistent state: {e}")
    
    async def _load_persistent_state(self):
        """Load persistent state from storage."""
        state_file = self.storage_path / "state.json"
        if state_file.exists():
            async with self._lock:
                data = json.loads(state_file.read_text())
                self.persistent = PersistentState.from_dict(data)
    
    async def _save_persistent_state(self):
        """Save persistent state to storage."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        state_file = self.storage_path / "state.json"
        state_file.write_text(json.dumps(self.persistent.to_dict()))
    
    async def update_term(self, new_term: int) -> bool:
        """
        Update current term if new term is greater.
        
        If the new term is greater, also reset voted_for
        and convert to follower.
        
        Args:
            new_term: The new term value
            
        Returns:
            True if term was updated
        """
        async with self._lock:
            if new_term > self.persistent.current_term:
                self.persistent.current_term = new_term
                self.persistent.voted_for = None
                await self._save_persistent_state()
                
                # Convert to follower if not already
                if self._role != NodeRole.FOLLOWER:
                    self._role = NodeRole.FOLLOWER
                    self.leader_state = None
                    logger.info(
                        f"Node {self.node_id} converted to follower "
                        f"for term {new_term}"
                    )
                
                return True
            return False
    
    async def increment_term(self) -> int:
        """
        Increment term for new election.
        
        Returns:
            The new term value
        """
        async with self._lock:
            self.persistent.current_term += 1
            self.persistent.voted_for = None
            await self._save_persistent_state()
            return self.persistent.current_term
    
    async def vote_for(self, candidate_id: str) -> bool:
        """
        Record vote for candidate in current term.
        
        Args:
            candidate_id: The candidate to vote for
            
        Returns:
            True if vote was recorded (haven't voted yet)
        """
        async with self._lock:
            if self.persistent.voted_for is None:
                self.persistent.voted_for = candidate_id
                await self._save_persistent_state()
                logger.info(
                    f"Node {self.node_id} voted for {candidate_id} "
                    f"in term {self.persistent.current_term}"
                )
                return True
            return self.persistent.voted_for == candidate_id
    
    async def become_candidate(self) -> int:
        """
        Transition to candidate role for election.
        
        Returns:
            The new term for the election
        """
        async with self._lock:
            self._role = NodeRole.CANDIDATE
            self.persistent.current_term += 1
            self.persistent.voted_for = self.node_id  # Vote for self
            self.leader_state = None
            self._leader_id = None
            await self._save_persistent_state()
            
            logger.info(
                f"Node {self.node_id} became candidate for term "
                f"{self.persistent.current_term}"
            )
            return self.persistent.current_term
    
    async def become_leader(self, last_log_index: int):
        """
        Transition to leader role after winning election.
        
        Args:
            last_log_index: Index of last log entry
        """
        async with self._lock:
            self._role = NodeRole.LEADER
            self._leader_id = self.node_id
            
            # Initialize leader volatile state
            self.leader_state = LeaderVolatileState()
            follower_ids = [
                nid for nid in self._cluster_nodes.keys()
                if nid != self.node_id
            ]
            self.leader_state.initialize_for_followers(
                follower_ids, last_log_index
            )
            
            logger.info(
                f"Node {self.node_id} became LEADER for term "
                f"{self.persistent.current_term}"
            )
    
    async def become_follower(self, leader_id: Optional[str] = None):
        """
        Transition to follower role.
        
        Args:
            leader_id: ID of the current leader (if known)
        """
        async with self._lock:
            self._role = NodeRole.FOLLOWER
            self._leader_id = leader_id
            self.leader_state = None
            self._last_heartbeat = datetime.now()
            
            logger.info(
                f"Node {self.node_id} became follower, "
                f"leader={leader_id}"
            )
    
    async def record_heartbeat(self, leader_id: str):
        """Record receipt of heartbeat from leader."""
        async with self._lock:
            self._leader_id = leader_id
            self._last_heartbeat = datetime.now()
    
    def time_since_last_heartbeat(self) -> float:
        """Get seconds since last heartbeat."""
        return (datetime.now() - self._last_heartbeat).total_seconds()
    
    async def update_commit_index(self, new_commit_index: int):
        """
        Update commit index if new value is higher.
        
        Args:
            new_commit_index: The new commit index
        """
        async with self._lock:
            if new_commit_index > self.volatile.commit_index:
                self.volatile.commit_index = new_commit_index
    
    async def update_last_applied(self, new_last_applied: int):
        """
        Update last applied index.
        
        Args:
            new_last_applied: The new last applied index
        """
        async with self._lock:
            self.volatile.last_applied = new_last_applied
    
    async def update_match_index(self, follower_id: str, match_index: int):
        """
        Update match index for a follower (leader only).
        
        Args:
            follower_id: The follower's node ID
            match_index: The new match index
        """
        if self.leader_state and follower_id in self.leader_state.match_index:
            self.leader_state.match_index[follower_id] = match_index
            self.leader_state.next_index[follower_id] = match_index + 1
    
    async def decrement_next_index(self, follower_id: str):
        """
        Decrement next index for a follower after rejection.
        
        Args:
            follower_id: The follower's node ID
        """
        if self.leader_state and follower_id in self.leader_state.next_index:
            self.leader_state.next_index[follower_id] = max(
                1, self.leader_state.next_index[follower_id] - 1
            )
    
    async def add_cluster_node(self, node_id: str, address: str):
        """
        Add a node to the cluster membership.
        
        Args:
            node_id: The node's unique ID
            address: The node's network address
        """
        async with self._lock:
            self._cluster_nodes[node_id] = address
            
            # Initialize leader state for new node if we're leader
            if self.leader_state:
                self.leader_state.next_index[node_id] = 1
                self.leader_state.match_index[node_id] = 0
    
    async def remove_cluster_node(self, node_id: str):
        """
        Remove a node from the cluster membership.
        
        Args:
            node_id: The node's unique ID
        """
        async with self._lock:
            self._cluster_nodes.pop(node_id, None)
            if self.leader_state:
                self.leader_state.next_index.pop(node_id, None)
                self.leader_state.match_index.pop(node_id, None)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current state status for debugging/monitoring."""
        return {
            "node_id": self.node_id,
            "role": self._role.value,
            "current_term": self.persistent.current_term,
            "voted_for": self.persistent.voted_for,
            "leader_id": self._leader_id,
            "commit_index": self.volatile.commit_index,
            "last_applied": self.volatile.last_applied,
            "cluster_size": len(self._cluster_nodes),
            "time_since_heartbeat": self.time_since_last_heartbeat(),
        }
