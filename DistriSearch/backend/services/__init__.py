"""
DistriSearch Backend - Servicios

Módulos de servicios del backend:
- node_service: Gestión de nodos
- replication_service: Replicación de archivos
- dynamic_replication: Replicación semántica dinámica
- index_service: Servicio de índice
- cluster_init: Inicialización del cluster
- checkpoint_service: Checkpoints y recuperación
- reliability_metrics: Métricas de fiabilidad
"""

from .node_service import (
    get_node,
    register_node,
    update_node_status,
    get_all_nodes,
    get_available_nodes,
)

from .replication_service import (
    replicate_file,
    get_file_replicas,
)

from .cluster_init import (
    initialize_cluster,
    shutdown_cluster,
)

from .reliability_metrics import (
    get_reliability_metrics,
)

__all__ = [
    # Node service
    'get_node',
    'register_node', 
    'update_node_status',
    'get_all_nodes',
    'get_available_nodes',
    
    # Replication
    'replicate_file',
    'get_file_replicas',
    
    # Cluster
    'initialize_cluster',
    'shutdown_cluster',
    
    # Metrics
    'get_reliability_metrics',
]
