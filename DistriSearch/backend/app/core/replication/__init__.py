# -*- coding: utf-8 -*-
"""
Replication Module - Semantic affinity-based document replication.

Implements replication with:
- Replication factor 2 (configurable)
- Semantic affinity placement (replicas on nodes with similar documents)
- Similarity graph for neighbor tracking
"""

from .affinity_replicator import AffinityReplicator, ReplicationConfig
from .similarity_graph import SimilarityGraph, DocumentNode, SimilarityEdge
from .replica_tracker import ReplicaTracker, ReplicaInfo, ReplicaStatus

__all__ = [
    "AffinityReplicator",
    "ReplicationConfig",
    "SimilarityGraph",
    "DocumentNode",
    "SimilarityEdge",
    "ReplicaTracker",
    "ReplicaInfo",
    "ReplicaStatus",
]
