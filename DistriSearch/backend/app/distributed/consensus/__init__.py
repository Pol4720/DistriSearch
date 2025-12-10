"""
Raft-Lite Consensus Protocol Implementation.

A simplified Raft consensus protocol optimized for DistriSearch's
distributed document search requirements.

Components:
- RaftState: Persistent and volatile Raft state management
- RaftNode: Core Raft node implementation
- LogEntry: Replicated log entries
- LogReplicator: Log replication between nodes
- LeaderElection: Leader election mechanism
- StateMachine: State machine for applying committed entries
"""

from app.distributed.consensus.raft_state import (
    RaftState,
    NodeRole,
    PersistentState,
    VolatileState,
)
from app.distributed.consensus.raft_node import RaftNode
from app.distributed.consensus.log_entry import LogEntry, LogStore
from app.distributed.consensus.log_replication import LogReplicator
from app.distributed.consensus.leader_election import LeaderElection
from app.distributed.consensus.state_machine import StateMachine, Command, CommandType

__all__ = [
    "RaftState",
    "NodeRole",
    "PersistentState",
    "VolatileState",
    "RaftNode",
    "LogEntry",
    "LogStore",
    "LogReplicator",
    "LeaderElection",
    "StateMachine",
    "Command",
    "CommandType",
]
