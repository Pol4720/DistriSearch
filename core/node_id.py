"""
Gestión de IDs de nodos en el hipercubo.
Validación, generación y utilidades.
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NodeID:
    """Representa un ID de nodo en el hipercubo."""
    
    def __init__(self, node_id: int, dimensions: int = 20):
        """
        Crea un NodeID validado.
        
        Args:
            node_id: ID numérico del nodo
            dimensions: Dimensiones del hipercubo
            
        Raises:
            ValueError: Si node_id está fuera de rango
        """
        self.dimensions = dimensions
        self.max_value = (1 << dimensions) - 1  # 2^dimensions - 1
        
        if not 0 <= node_id <= self.max_value:
            raise ValueError(
                f"node_id {node_id} fuera de rango [0, {self.max_value}]"
            )
        
        self._id = node_id
    
    @property
    def value(self) -> int:
        """Retorna el ID numérico."""
        return self._id
    
    @property
    def binary(self) -> str:
        """Retorna representación binaria del ID."""
        return format(self._id, f'0{self.dimensions}b')
    
    def distance_to(self, other: 'NodeID') -> int:
        """
        Calcula distancia XOR a otro nodo.
        
        Args:
            other: Otro NodeID
            
        Returns:
            Distancia XOR (número de bits diferentes)
        """
        xor = self._id ^ other.value
        return bin(xor).count('1')
    
    def __eq__(self, other):
        if isinstance(other, NodeID):
            return self._id == other.value
        elif isinstance(other, int):
            return self._id == other
        return False
    
    def __hash__(self):
        return hash(self._id)
    
    def __repr__(self):
        return f"NodeID({self._id}, dims={self.dimensions})"
    
    def __str__(self):
        return f"Node{self._id} ({self.binary})"


def generate_node_id(seed: str, dimensions: int = 20) -> int:
    """
    Genera un ID de nodo desde una semilla (string).
    
    Args:
        seed: String semilla (hostname, UUID, etc.)
        dimensions: Dimensiones del hipercubo
        
    Returns:
        ID de nodo válido [0, 2^dimensions - 1]
        
    Example:
        >>> generate_node_id("server1.example.com", 20)
        524231
    """
    hash_obj = hashlib.sha256(seed.encode())
    hash_int = int.from_bytes(hash_obj.digest(), byteorder='big')
    
    max_value = (1 << dimensions) - 1
    node_id = hash_int % (max_value + 1)
    
    logger.debug(f"Generado node_id {node_id} desde seed '{seed}'")
    return node_id


def validate_node_id(node_id: int, dimensions: int = 20) -> bool:
    """
    Valida que un ID esté en el rango correcto.
    
    Args:
        node_id: ID a validar
        dimensions: Dimensiones del hipercubo
        
    Returns:
        True si es válido, False si no
    """
    max_value = (1 << dimensions) - 1
    return 0 <= node_id <= max_value