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
- PartitionTolerantConsensus: AP-mode partition-tolerant consensus (CAP theorem)
"""

from .raft_state import (
    RaftState,
    NodeRole,
    PersistentState,
    VolatileState,
)
from .raft_node import RaftNode
from .log_entry import LogEntry, LogStore
from .log_replication import LogReplicator
from .leader_election import LeaderElection
from .state_machine import StateMachine, Command, CommandType
from .partition_tolerant import (
    PartitionTolerantConsensus,
    PartitionState,
    PartitionStatus,
    ConsistencyLevel,
    DataFreshness,
    VersionedData,
    APReadResult,
    APWriteResult,
)

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
    # AP-Mode Partition Tolerance (CAP)
    "PartitionTolerantConsensus",
    "PartitionState",
    "PartitionStatus",
    "ConsistencyLevel",
    "DataFreshness",
    "VersionedData",
    "APReadResult",
    "APWriteResult",
]
