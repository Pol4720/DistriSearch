"""
Nodo del buscador distribuido con API HTTP.

Este módulo orquesta todos los componentes del nodo usando mixins:
- NodeCore: Inicialización y componentes básicos
- NodeMessaging: Ruteo y manejo de mensajes
- NodeReplication: Replicación de documentos
- NodeSearch: Búsqueda distribuida
- NodeHTTP: Servidor HTTP y API REST
"""
import logging
from network.network_interface import NetworkInterface

# Importar módulos separados
from node.node_core import NodeCore
from node.node_messaging import NodeMessaging
from node.node_replication import NodeReplication
from node.node_search import NodeSearch
from node.node_http import NodeHTTP

logger = logging.getLogger(__name__)


class DistributedNode(
    NodeCore,
    NodeMessaging,
    NodeReplication,
    NodeSearch,
    NodeHTTP
):
    """
    Nodo del buscador distribuido - Clase orquestadora.
    
    Combina funcionalidad de múltiples mixins:
    - NodeCore: Inicialización, componentes básicos, shutdown
    - NodeMessaging: Ruteo de mensajes por hipercubo, despacho
    - NodeReplication: Replicación de documentos con quorum
    - NodeSearch: Búsqueda distribuida con tolerancia a fallos
    - NodeHTTP: Servidor HTTP y API REST
    
    Esta clase actúa como fachada y orquestador, delegando
    funcionalidad especializada a los mixins correspondientes.
    
    Ejemplo de uso:
        node = DistributedNode(node_id=5, dimensions=20, port=8005)
        await node.initialize(bootstrap_nodes=[0, 1, 2, 3, 4])
        await node.start_http_server()
        
        # Añadir documento
        result = await node.add_document("doc1", "Python programming")
        
        # Buscar
        results = await node.search("Python")
        
        # Apagar
        await node.shutdown()
    """
    
    def __init__(
        self, 
        node_id: int, 
        dimensions: int = 20, 
        host: str = "localhost", 
        port: int = 8000,
        network: NetworkInterface = None,
        enable_tls: bool = False
    ):
        """
        Inicializa el nodo distribuido.
        
        Args:
            node_id: ID único del nodo (0 a 2^dimensions - 1)
            dimensions: Dimensiones del hipercubo (default 20)
            host: Host para servidor HTTP
            port: Puerto para servidor HTTP
            network: Interfaz de red (None = simulada)
            enable_tls: Habilitar TLS/SSL en servidor HTTP
        """
        # Inicializar NodeCore (componentes básicos)
        NodeCore.__init__(
            self, 
            node_id, 
            dimensions, 
            host, 
            port, 
            network, 
            enable_tls
        )
        
        # Inicializar NodeHTTP (servidor web)
        NodeHTTP.__init__(self)
        
        # Los otros mixins no requieren __init__ explícito
        # (usan métodos de la clase base)
        
        logger.info(
            f"DistributedNode {node_id} creado completamente "
            f"(dims={dimensions}, {host}:{port}, TLS={enable_tls})"
        )
    
    async def shutdown(self):
        """
        Apaga el nodo limpiamente.
        Detiene todos los componentes en orden apropiado.
        """
        logger.info(f"Iniciando shutdown del nodo {self.node_id}...")
        
        # Detener servidor HTTP primero
        await self.stop_http_server()
        
        # Luego componentes internos (delegado a NodeCore)
        await NodeCore.shutdown(self)
        
        logger.info(f"Nodo {self.node_id} completamente apagado")
