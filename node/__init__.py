"""
Paquete node - Nodo distribuido del sistema DistriSearch.

Exporta la clase principal DistributedNode que combina todos
los componentes mediante herencia múltiple de mixins.

Módulos internos:
- node_core: Componentes básicos y configuración
- node_messaging: Ruteo y manejo de mensajes
- node_replication: Replicación de documentos con quorum
- node_search: Búsqueda distribuida con tolerancia a fallos
- node_http: Servidor HTTP y API REST
"""

from node.node import DistributedNode

__all__ = ['DistributedNode']
