"""
Estados y tipos de datos para Raft.
Definiciones compartidas por todos los módulos de consenso.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


class NodeState(Enum):
    """Estados posibles de un nodo Raft."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class RaftMessage:
    """Mensaje Raft genérico."""
    type: str  # "request_vote", "vote_response", "append_entries", "append_response"
    term: int
    sender_id: int
    
    # Para RequestVote
    last_log_index: Optional[int] = None
    last_log_term: Optional[int] = None
    
    # Para RequestVote Response
    vote_granted: Optional[bool] = None
    
    # Para AppendEntries (heartbeat)
    leader_id: Optional[int] = None
    prev_log_index: Optional[int] = None
    prev_log_term: Optional[int] = None
    entries: Optional[List] = None
    leader_commit: Optional[int] = None
    
    # Para AppendEntries Response
    success: Optional[bool] = None
    match_index: Optional[int] = None


@dataclass
class LogEntry:
    """Entrada del log de Raft."""
    term: int
    command: Dict[str, Any]  # {type: "index_update", node_id: X, terms: [...]}
    index: int = 0


@dataclass
class RaftState:
    """
    Estado completo de un nodo Raft.
    Contiene tanto estado persistente como volátil.
    """
    # Estado persistente (debe sobrevivir a reinicios)
    current_term: int = 0
    voted_for: Optional[int] = None
    log: List[LogEntry] = field(default_factory=list)
    
    # Estado volátil (todos los servidores)
    commit_index: int = 0
    last_applied: int = 0
    
    # Estado volátil (solo líderes)
    next_index: Dict[int, int] = field(default_factory=dict)
    match_index: Dict[int, int] = field(default_factory=dict)
    
    # Estado de elección
    state: NodeState = NodeState.FOLLOWER
    current_leader: Optional[int] = None
    votes_received: set = field(default_factory=set)
    
    def reset_election_state(self):
        """Resetea estado de elección."""
        self.voted_for = None
        self.votes_received = set()
    
    def become_follower(self, term: int, leader_id: Optional[int] = None):
        """Transición a follower."""
        self.state = NodeState.FOLLOWER
        self.current_term = term
        self.current_leader = leader_id
        self.voted_for = None
    
    def become_candidate(self, node_id: int):
        """Transición a candidato."""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = node_id
        self.votes_received = {node_id}
        self.current_leader = None
    
    def become_leader(self, node_id: int, num_nodes: int):
        """Transición a líder."""
        self.state = NodeState.LEADER
        self.current_leader = node_id
        
        # Inicializar índices de réplicas
        last_log_index = len(self.log)
        self.next_index = {i: last_log_index for i in range(num_nodes)}
        self.match_index = {i: 0 for i in range(num_nodes)}


class RaftConfig:
    """Configuración de Raft."""
    # Timeouts en segundos
    ELECTION_TIMEOUT_MIN = 1.5
    ELECTION_TIMEOUT_MAX = 3.0
    HEARTBEAT_INTERVAL = 0.5
    
    # Replicación
    MAX_ENTRIES_PER_APPEND = 100
    SNAPSHOT_INTERVAL = 100  # Cada cuántas entradas hacer snapshot