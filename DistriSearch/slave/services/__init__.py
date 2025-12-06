"""
DistriSearch Slave - Services Module
=====================================
Re-exporta servicios desde backend/services para compatibilidad.
"""

import sys
import os

# Asegurar que backend esté en el path  
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from backend.services import (
    replication_service,
    node_service,
)

from backend.services.dynamic_replication import get_replication_service
from backend.services.cluster_init import initialize_cluster, shutdown_cluster
from backend.services.reliability_metrics import get_reliability_metrics
from backend.services.index_service import IndexService
from backend.services.checkpoint_service import CheckpointService

__all__ = [
    "replication_service",
    "node_service",
    "get_replication_service",
    "initialize_cluster",
    "shutdown_cluster",
    "get_reliability_metrics",
    "IndexService",
    "CheckpointService",
]
