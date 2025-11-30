"""
Estrategia de hashing para sharding.
"""
import hashlib
from typing import List, Optional


def hash_term(term: str, num_shards: int = 16) -> int:
    """
    Calcula el shard para un término usando consistent hashing.
    
    Args:
        term: Término a hashear
        num_shards: Número total de shards
        
    Returns:
        Índice de shard (0 a num_shards-1)
    """
    # SHA-256 hash del término
    hash_bytes = hashlib.sha256(term.encode('utf-8')).digest()
    
    # Convertir a entero
    hash_int = int.from_bytes(hash_bytes[:4], byteorder='big')
    
    # Módulo para obtener shard
    return hash_int % num_shards


class ConsistentHash:
    """
    Consistent hashing para distribución de shards.
    Permite añadir/remover shards con mínima redistribución.
    """
    
    def __init__(self, num_shards: int = 16, virtual_nodes: int = 150):
        """
        Inicializa consistent hashing.
        
        Args:
            num_shards: Número de shards
            virtual_nodes: Nodos virtuales por shard (para balanceo)
        """
        self.num_shards = num_shards
        self.virtual_nodes = virtual_nodes
        
        # Ring de hash: hash_value -> shard_id
        self.ring: List[tuple] = []
        
        # Construir ring
        self._build_ring()
    
    def _build_ring(self):
        """Construye el ring de consistent hashing."""
        self.ring = []
        
        for shard_id in range(self.num_shards):
            for vnode in range(self.virtual_nodes):
                # Hash del shard + vnode
                key = f"shard_{shard_id}_vnode_{vnode}"
                hash_value = self._hash(key)
                
                self.ring.append((hash_value, shard_id))
        
        # Ordenar por hash_value
        self.ring.sort(key=lambda x: x[0])
    
    def _hash(self, key: str) -> int:
        """Calcula hash de una clave."""
        hash_bytes = hashlib.sha256(key.encode('utf-8')).digest()
        return int.from_bytes(hash_bytes[:8], byteorder='big')
    
    def get_shard(self, key: str) -> int:
        """
        Obtiene el shard para una clave.
        
        Args:
            key: Clave (término, doc_id, etc.)
            
        Returns:
            ID del shard
        """
        if not self.ring:
            return 0
        
        # Hash de la clave
        key_hash = self._hash(key)
        
        # Búsqueda binaria del primer nodo >= key_hash
        left, right = 0, len(self.ring) - 1
        result_idx = 0
        
        while left <= right:
            mid = (left + right) // 2
            
            if self.ring[mid][0] >= key_hash:
                result_idx = mid
                right = mid - 1
            else:
                left = mid + 1
        
        # Si no encontramos, wrapeamos al primer nodo
        if self.ring[result_idx][0] < key_hash:
            result_idx = 0
        
        return self.ring[result_idx][1]
    
    def get_shards_for_range(
        self,
        start_key: str,
        end_key: str
    ) -> List[int]:
        """
        Obtiene shards para un rango de claves.
        
        Args:
            start_key: Clave inicial
            end_key: Clave final
            
        Returns:
            Lista de shard_ids en el rango
        """
        start_hash = self._hash(start_key)
        end_hash = self._hash(end_key)
        
        shards = set()
        
        for hash_value, shard_id in self.ring:
            if start_hash <= hash_value <= end_hash:
                shards.add(shard_id)
        
        return sorted(list(shards))
    
    def add_shard(self, shard_id: int):
        """
        Añade un nuevo shard al ring.
        
        Args:
            shard_id: ID del nuevo shard
        """
        for vnode in range(self.virtual_nodes):
            key = f"shard_{shard_id}_vnode_{vnode}"
            hash_value = self._hash(key)
            self.ring.append((hash_value, shard_id))
        
        # Re-ordenar
        self.ring.sort(key=lambda x: x[0])
        self.num_shards += 1
    
    def remove_shard(self, shard_id: int):
        """
        Remueve un shard del ring.
        
        Args:
            shard_id: ID del shard a remover
        """
        self.ring = [
            (h, s) for h, s in self.ring
            if s != shard_id
        ]
        self.num_shards -= 1
    
    def get_shard_distribution(self) -> dict:
        """
        Calcula la distribución de vnodes por shard.
        
        Returns:
            Diccionario {shard_id: número_de_vnodes}
        """
        distribution = {}
        
        for _, shard_id in self.ring:
            distribution[shard_id] = distribution.get(shard_id, 0) + 1
        
        return distribution
