"""
Hipercubo lógico: direcciones binarias, cálculo de vecinos y ruteo.
"""
import logging
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class HypercubeNode:
    """Representa un nodo en la topología de hipercubo."""
    
    def __init__(self, node_id: int, dimensions: int = 20):
        """
        Inicializa un nodo del hipercubo.
        
        Args:
            node_id: ID único del nodo (0 a 2^dimensions - 1)
            dimensions: Número de dimensiones del hipercubo (bits)
        """
        self.node_id = node_id
        self.dimensions = dimensions
        self.max_id = (1 << dimensions) - 1
        
        if node_id < 0 or node_id > self.max_id:
            raise ValueError(f"Node ID debe estar entre 0 y {self.max_id}")
    
    @property
    def binary_address(self) -> str:
        """Retorna la dirección binaria del nodo."""
        return format(self.node_id, f'0{self.dimensions}b')
    
    def get_neighbors(self) -> List[int]:
        """
        Calcula los vecinos lógicos del nodo.
        Un vecino difiere en exactamente un bit.
        
        Returns:
            Lista de IDs de vecinos potenciales
        """
        neighbors = []
        for i in range(self.dimensions):
            neighbor_id = self.node_id ^ (1 << i)
            neighbors.append(neighbor_id)
        return neighbors
    
    def hamming_distance(self, other_id: int) -> int:
        """Calcula la distancia de Hamming (bits diferentes)."""
        xor = self.node_id ^ other_id
        return bin(xor).count('1')
    
    def xor_distance(self, other_id: int) -> int:
        """Calcula la distancia XOR."""
        return self.node_id ^ other_id


def route_next_hop(current_id: int, dest_id: int, available_neighbors: Set[int], 
                   dimensions: int = 20) -> Optional[int]:
    """
    Calcula el siguiente salto en el ruteo hacia el destino.
    
    Algoritmo:
    1. Si current == dest, retornar None (destino alcanzado)
    2. Calcular bits diferentes (XOR)
    3. Elegir bit más significativo diferente y verificar si ese vecino existe
    4. Si no existe, usar ruteo greedy: elegir vecino que minimice distancia XOR
    
    Args:
        current_id: ID del nodo actual
        dest_id: ID del nodo destino
        available_neighbors: Set de vecinos disponibles/conocidos
        dimensions: Dimensiones del hipercubo
    
    Returns:
        ID del siguiente salto, o None si ya estamos en destino
    """
    if current_id == dest_id:
        return None
    
    diff = current_id ^ dest_id
    
    if diff == 0:
        return None
    
    # Estrategia 1: Bitflip - elegir bit más significativo diferente
    for i in range(dimensions - 1, -1, -1):
        if diff & (1 << i):
            # Este bit es diferente
            candidate = current_id ^ (1 << i)
            if candidate in available_neighbors:
                logger.debug(f"Ruteo bitflip: {current_id} -> {candidate} (flip bit {i})")
                return candidate
    
    # Estrategia 2: Greedy - elegir vecino que minimice distancia XOR al destino
    if not available_neighbors:
        logger.warning(f"No hay vecinos disponibles desde {current_id}")
        return None
    
    best_neighbor = min(available_neighbors, key=lambda n: n ^ dest_id)
    current_distance = current_id ^ dest_id
    best_distance = best_neighbor ^ dest_id
    
    if best_distance < current_distance:
        logger.debug(f"Ruteo greedy: {current_id} -> {best_neighbor} (XOR dist: {best_distance})")
        return best_neighbor
    
    # Si ningún vecino mejora la distancia, elegir cualquiera (puede haber loop)
    logger.warning(f"Ruteo forzado desde {current_id}, sin mejora de distancia")
    return best_neighbor


def calculate_route_path(start_id: int, dest_id: int, active_nodes: Set[int], 
                         dimensions: int = 20, max_hops: int = None) -> List[int]:
    """
    Calcula la ruta completa desde start hasta dest.
    
    Args:
        start_id: Nodo origen
        dest_id: Nodo destino
        active_nodes: Set de todos los nodos activos en la red
        dimensions: Dimensiones del hipercubo
        max_hops: Límite de saltos (default: 2 * dimensions)
    
    Returns:
        Lista de IDs formando la ruta (incluye start y dest)
    """
    if max_hops is None:
        max_hops = 2 * dimensions
    
    path = [start_id]
    current = start_id
    
    for hop in range(max_hops):
        if current == dest_id:
            break
        
        # Calcular vecinos del nodo actual
        node = HypercubeNode(current, dimensions)
        potential_neighbors = set(node.get_neighbors())
        available_neighbors = potential_neighbors & active_nodes
        
        next_hop = route_next_hop(current, dest_id, available_neighbors, dimensions)
        
        if next_hop is None:
            break
        
        if next_hop in path:
            logger.error(f"Loop detectado en ruta: {path} -> {next_hop}")
            break
        
        path.append(next_hop)
        current = next_hop
    
    return path


def generate_node_id(seed: str, dimensions: int = 20) -> int:
    """
    Genera un ID de nodo a partir de una semilla (ej: "host:port").
    
    Args:
        seed: String para hashear
        dimensions: Dimensiones del hipercubo
    
    Returns:
        ID de nodo válido
    """
    hash_value = hash(seed)
    max_id = (1 << dimensions) - 1
    return abs(hash_value) % (max_id + 1)
