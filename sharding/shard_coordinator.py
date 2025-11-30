"""
Coordinador de shard - DataBalancer por shard.
"""
import logging
from typing import Set, List
from balancer import DataBalancer

logger = logging.getLogger(__name__)


class ShardCoordinator:
    """
    Coordinador para un shard específico.
    Envuelve un DataBalancer y añade funcionalidad de shard.
    """
    
    def __init__(self, shard_id: int, node_id: int = None):
        """
        Inicializa coordinador de shard.
        
        Args:
            shard_id: ID del shard
            node_id: ID del nodo coordinador (opcional)
        """
        self.shard_id = shard_id
        self.balancer = DataBalancer(node_id=node_id)
        
        logger.info(
            f"ShardCoordinator: Shard {shard_id} inicializado "
            f"(nodo {node_id})"
        )
    
    def locate_terms(self, terms: List[str]) -> Set[int]:
        """
        Localiza términos en este shard.
        
        Args:
            terms: Términos a buscar
            
        Returns:
            Conjunto de node_ids
        """
        return self.balancer.locate_terms(terms)
    
    def update_node_index(self, node_id: int, terms: List[str]):
        """
        Actualiza índice de nodo para este shard.
        
        Args:
            node_id: ID del nodo
            terms: Términos del nodo
        """
        self.balancer.update_node_index(node_id, terms)
    
    def register_node(self, node_id: int, address: str = None, port: int = None):
        """Registra un nodo en este shard."""
        self.balancer.register_node(node_id, address, port)
    
    def heartbeat(self, node_id: int, doc_count: int = None, term_count: int = None):
        """Procesa heartbeat de un nodo."""
        self.balancer.heartbeat(node_id, doc_count, term_count)
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del shard."""
        stats = self.balancer.get_stats()
        stats["shard_id"] = self.shard_id
        return stats
    
    def to_dict(self) -> dict:
        """Serializa el estado del shard."""
        return {
            "shard_id": self.shard_id,
            "balancer": self.balancer.to_dict()
        }
    
    def from_dict(self, data: dict):
        """Carga estado desde diccionario."""
        if "balancer" in data:
            self.balancer.from_dict(data["balancer"])
