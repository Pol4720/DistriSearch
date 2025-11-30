"""
Módulo de consenso Raft - Orquestador principal.
DEPRECADO: Usar consensus/raft_consensus.py en su lugar.

Este archivo se mantiene temporalmente para compatibilidad.
"""
import logging
from consensus.raft_consensus import RaftConsensus
from consensus.raft_state import NodeState, RaftMessage, LogEntry

logger = logging.getLogger(__name__)

# Re-exportar para compatibilidad con código existente
__all__ = ['RaftConsensus', 'NodeState', 'RaftMessage', 'LogEntry']

logger.warning(
    "consensus.py está deprecado. Usa 'from consensus.raft_consensus import RaftConsensus'"
)