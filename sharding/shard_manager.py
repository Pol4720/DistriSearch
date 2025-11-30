"""
Gestor de shards del sistema.
"""
import logging
from typing import Dict, List, Set
from sharding.hash_strategy import ConsistentHash, hash_term

logger = logging.getLogger(__name__)


class ShardManager:
    """
    Gestiona los shards del sistema distribuido.
    Distribuye términos entre múltiples DataBalancers.
    """
    
    def __init__(self, num_shards: int = 16):
        """
        Inicializa el gestor de shards.
        
        Args:
            num_shards: Número de shards
        """
        self.num_shards = num_shards
        self.consistent_hash = ConsistentHash(num_shards)
        
        # Mapeo: shard_id -> DataBalancer instance
        self.balancers: Dict[int, any] = {}
        
        logger.info(f"ShardManager: Inicializado con {num_shards} shards")
    
    def register_balancer(self, shard_id: int, balancer):
        """
        Registra un DataBalancer para un shard.
        
        Args:
            shard_id: ID del shard
            balancer: Instancia de DataBalancer
        """
        self.balancers[shard_id] = balancer
        logger.debug(f"ShardManager: Balancer registrado para shard {shard_id}")
    
    def get_shard_for_term(self, term: str) -> int:
        """
        Determina el shard para un término.
        
        Args:
            term: Término a shardear
            
        Returns:
            ID del shard
        """
        return self.consistent_hash.get_shard(term)
    
    def get_shard_for_terms(self, terms: List[str]) -> Dict[int, List[str]]:
        """
        Agrupa términos por shard.
        
        Args:
            terms: Lista de términos
            
        Returns:
            Diccionario {shard_id: [términos]}
        """
        shard_terms = {}
        
        for term in terms:
            shard_id = self.get_shard_for_term(term)
            
            if shard_id not in shard_terms:
                shard_terms[shard_id] = []
            
            shard_terms[shard_id].append(term)
        
        return shard_terms
    
    def get_balancer(self, shard_id: int):
        """
        Obtiene el DataBalancer para un shard.
        
        Args:
            shard_id: ID del shard
            
        Returns:
            Instancia de DataBalancer o None
        """
        return self.balancers.get(shard_id)
    
    def locate_terms(self, terms: List[str]) -> Set[int]:
        """
        Localiza nodos que contienen los términos.
        
        Distribuye la consulta entre shards apropiados.
        
        Args:
            terms: Lista de términos a buscar
            
        Returns:
            Conjunto de node_ids que contienen algún término
        """
        # Agrupar términos por shard
        shard_terms = self.get_shard_for_terms(terms)
        
        all_nodes = set()
        
        # Consultar cada shard
        for shard_id, shard_term_list in shard_terms.items():
            balancer = self.get_balancer(shard_id)
            
            if balancer:
                nodes = balancer.locate_terms(shard_term_list)
                all_nodes |= nodes
            else:
                logger.warning(
                    f"ShardManager: No hay balancer para shard {shard_id}"
                )
        
        return all_nodes
    
    def update_node_index(
        self,
        node_id: int,
        terms: List[str]
    ):
        """
        Actualiza el índice de un nodo distribuyendo entre shards.
        
        Args:
            node_id: ID del nodo
            terms: Lista de términos del nodo
        """
        # Agrupar términos por shard
        shard_terms = self.get_shard_for_terms(terms)
        
        # Actualizar cada shard
        for shard_id, shard_term_list in shard_terms.items():
            balancer = self.get_balancer(shard_id)
            
            if balancer:
                balancer.update_node_index(node_id, shard_term_list)
            else:
                logger.warning(
                    f"ShardManager: No hay balancer para shard {shard_id}"
                )
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de sharding."""
        stats = {
            "num_shards": self.num_shards,
            "active_balancers": len(self.balancers),
            "shards": {}
        }
        
        for shard_id, balancer in self.balancers.items():
            shard_stats = balancer.get_stats()
            stats["shards"][shard_id] = shard_stats
        
        return stats
    
    def get_shard_distribution(self) -> Dict:
        """Obtiene distribución de vnodes por shard."""
        return self.consistent_hash.get_shard_distribution()
