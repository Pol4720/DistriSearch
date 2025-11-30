"""
Módulo de replicación de documentos.
Gestiona réplicas, quorum y rollback.
"""
from replication.replica_manager import ReplicaManager
from replication.quorum import QuorumConfig, verify_quorum
from replication.rollback import RollbackManager

__all__ = [
    "ReplicaManager",
    "QuorumConfig",
    "verify_quorum",
    "RollbackManager",
]
