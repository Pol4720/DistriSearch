"""
Registro de nodos activos en el sistema.
"""
from typing import Dict, Set, Optional
import time
import logging

logger = logging.getLogger(__name__)


class NodeMetadata:
    """Metadata de un nodo."""
    
    def __init__(
        self,
        node_id: int,
        address: str = None,
        port: int = None,
        last_heartbeat: float = None
    ):
        self.node_id = node_id
        self.address = address or "localhost"
        self.port = port or 8000
        self.last_heartbeat = last_heartbeat or time.time()
        self.document_count = 0
        self.term_count = 0
    
    def update_heartbeat(self):
        """Actualiza el timestamp del último heartbeat."""
        self.last_heartbeat = time.time()
    
    def is_alive(self, timeout: float = 30.0) -> bool:
        """
        Verifica si el nodo está activo.
        
        Args:
            timeout: Tiempo máximo sin heartbeat (segundos)
            
        Returns:
            True si está activo
        """
        elapsed = time.time() - self.last_heartbeat
        return elapsed < timeout
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "port": self.port,
            "last_heartbeat": self.last_heartbeat,
            "document_count": self.document_count,
            "term_count": self.term_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NodeMetadata":
        """Crea desde diccionario."""
        metadata = cls(
            node_id=data["node_id"],
            address=data.get("address"),
            port=data.get("port"),
            last_heartbeat=data.get("last_heartbeat")
        )
        metadata.document_count = data.get("document_count", 0)
        metadata.term_count = data.get("term_count", 0)
        return metadata


class NodeRegistry:
    """Registro de nodos activos en el sistema."""
    
    def __init__(self):
        self.nodes: Dict[int, NodeMetadata] = {}
    
    def register(
        self, 
        node_id: int, 
        address: str = None, 
        port: int = None
    ) -> NodeMetadata:
        """
        Registra un nodo.
        
        Args:
            node_id: ID del nodo
            address: Dirección IP/hostname
            port: Puerto
            
        Returns:
            Metadata del nodo registrado
        """
        if node_id in self.nodes:
            # Actualizar heartbeat si ya existe
            self.nodes[node_id].update_heartbeat()
        else:
            # Crear nuevo
            self.nodes[node_id] = NodeMetadata(node_id, address, port)
            logger.info(f"NodeRegistry: Nodo {node_id} registrado")
        
        return self.nodes[node_id]
    
    def unregister(self, node_id: int) -> bool:
        """
        Desregistra un nodo.
        
        Args:
            node_id: ID del nodo
            
        Returns:
            True si se eliminó, False si no existía
        """
        if node_id in self.nodes:
            del self.nodes[node_id]
            logger.info(f"NodeRegistry: Nodo {node_id} desregistrado")
            return True
        return False
    
    def heartbeat(self, node_id: int):
        """
        Actualiza el heartbeat de un nodo.
        
        Args:
            node_id: ID del nodo
        """
        if node_id in self.nodes:
            self.nodes[node_id].update_heartbeat()
    
    def get(self, node_id: int) -> Optional[NodeMetadata]:
        """Obtiene metadata de un nodo."""
        return self.nodes.get(node_id)
    
    def exists(self, node_id: int) -> bool:
        """Verifica si un nodo está registrado."""
        return node_id in self.nodes
    
    def get_all(self) -> Dict[int, NodeMetadata]:
        """Retorna todos los nodos registrados."""
        return self.nodes.copy()
    
    def get_active_nodes(self, timeout: float = 30.0) -> Set[int]:
        """
        Retorna IDs de nodos activos.
        
        Args:
            timeout: Tiempo máximo sin heartbeat (segundos)
            
        Returns:
            Conjunto de node_ids activos
        """
        active = set()
        
        for node_id, metadata in self.nodes.items():
            if metadata.is_alive(timeout):
                active.add(node_id)
        
        return active
    
    def clean_dead_nodes(self, timeout: float = 30.0) -> int:
        """
        Elimina nodos inactivos.
        
        Args:
            timeout: Tiempo máximo sin heartbeat (segundos)
            
        Returns:
            Número de nodos eliminados
        """
        dead_nodes = []
        
        for node_id, metadata in self.nodes.items():
            if not metadata.is_alive(timeout):
                dead_nodes.append(node_id)
        
        for node_id in dead_nodes:
            self.unregister(node_id)
        
        if dead_nodes:
            logger.info(
                f"NodeRegistry: Eliminados {len(dead_nodes)} nodos inactivos"
            )
        
        return len(dead_nodes)
    
    def count(self) -> int:
        """Retorna el número de nodos registrados."""
        return len(self.nodes)
    
    def update_stats(self, node_id: int, doc_count: int, term_count: int):
        """
        Actualiza estadísticas de un nodo.
        
        Args:
            node_id: ID del nodo
            doc_count: Número de documentos
            term_count: Número de términos únicos
        """
        if node_id in self.nodes:
            self.nodes[node_id].document_count = doc_count
            self.nodes[node_id].term_count = term_count
    
    def get_total_documents(self) -> int:
        """Retorna el total de documentos en el sistema."""
        return sum(m.document_count for m in self.nodes.values())
    
    def get_total_terms(self) -> int:
        """Retorna el total de términos únicos en el sistema."""
        # Nota: puede haber términos duplicados entre nodos
        return sum(m.term_count for m in self.nodes.values())
    
    def clear(self):
        """Elimina todos los nodos."""
        self.nodes.clear()
        logger.info("NodeRegistry: Registro limpiado")
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            str(node_id): metadata.to_dict()
            for node_id, metadata in self.nodes.items()
        }
    
    def from_dict(self, data: Dict):
        """Carga desde diccionario."""
        self.clear()
        
        for node_id_str, metadata_dict in data.items():
            node_id = int(node_id_str)
            self.nodes[node_id] = NodeMetadata.from_dict(metadata_dict)
        
        logger.info(
            f"NodeRegistry: Cargado ({self.count()} nodos)"
        )
