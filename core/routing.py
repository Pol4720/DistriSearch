"""
Algoritmos de ruteo en hipercubo.
Ruteo XOR greedy con tolerancia a fallos.
"""
import logging
from typing import List, Optional, Set
from core.node_id import NodeID

logger = logging.getLogger(__name__)


class HypercubeRouter:
    """Router para topología de hipercubo."""
    
    def __init__(self, dimensions: int = 20):
        self.dimensions = dimensions
    
    def route_next_hop(
        self,
        current_id: int,
        dest_id: int,
        available_neighbors: Set[int]
    ) -> Optional[int]:
        """
        Calcula el próximo salto hacia destino usando ruteo XOR greedy.
        
        Estrategia:
        1. Calcular XOR entre posición actual y destino
        2. Elegir vecino que minimice distancia XOR al destino
        3. Si no hay vecinos disponibles, retornar None
        
        Args:
            current_id: ID del nodo actual
            dest_id: ID del nodo destino
            available_neighbors: IDs de vecinos disponibles
            
        Returns:
            ID del próximo salto, o None si no hay ruta
            
        Example:
            >>> router = HypercubeRouter(dimensions=4)
            >>> router.route_next_hop(5, 12, {4, 7, 13})
            13  # 1101 está más cerca de 1100 que otros vecinos
        """
        if current_id == dest_id:
            return None  # Ya estamos en destino
        
        if not available_neighbors:
            logger.warning(
                f"Sin vecinos disponibles para rutear desde {current_id} a {dest_id}"
            )
            return None
        
        # XOR actual -> destino
        xor_target = current_id ^ dest_id
        
        # Encontrar vecino que minimice distancia
        best_neighbor = None
        best_distance = float('inf')
        
        for neighbor_id in available_neighbors:
            # Distancia XOR del vecino al destino
            neighbor_xor = neighbor_id ^ dest_id
            distance = bin(neighbor_xor).count('1')
            
            if distance < best_distance:
                best_distance = distance
                best_neighbor = neighbor_id
        
        logger.debug(
            f"Ruteo: {current_id} -> {best_neighbor} (hacia {dest_id}, "
            f"distancia={best_distance})"
        )
        
        return best_neighbor
    
    def calculate_route_path(
        self,
        start_id: int,
        dest_id: int,
        active_nodes: Set[int],
        max_hops: Optional[int] = None
    ) -> List[int]:
        """
        Calcula la ruta completa desde start_id a dest_id.
        
        Args:
            start_id: Nodo origen
            dest_id: Nodo destino
            active_nodes: Conjunto de nodos activos en la red
            max_hops: Máximo número de saltos (default: dimensions)
            
        Returns:
            Lista de IDs de nodos en la ruta (incluyendo start y dest)
            Lista vacía si no hay ruta
            
        Example:
            >>> router.calculate_route_path(0, 7, {0, 1, 3, 7})
            [0, 1, 3, 7]
        """
        if start_id == dest_id:
            return [start_id]
        
        if dest_id not in active_nodes:
            logger.warning(f"Destino {dest_id} no está en nodos activos")
            return []
        
        if max_hops is None:
            max_hops = self.dimensions
        
        # Generar vecinos del nodo actual
        def get_neighbors(node_id: int) -> Set[int]:
            neighbors = set()
            for i in range(self.dimensions):
                neighbor = node_id ^ (1 << i)
                if neighbor in active_nodes:
                    neighbors.add(neighbor)
            return neighbors
        
        # BFS para encontrar ruta
        current = start_id
        path = [current]
        visited = {current}
        
        for hop in range(max_hops):
            if current == dest_id:
                return path
            
            neighbors = get_neighbors(current) - visited
            
            if not neighbors:
                logger.warning(
                    f"Sin vecinos disponibles en {current}, ruta bloqueada"
                )
                return []
            
            # Siguiente salto (route_next_hop retorna None si current == dest)
            next_hop = self.route_next_hop(current, dest_id, neighbors)
            
            if next_hop is None:
                # Puede ser que ya estamos en destino (chequeado arriba)
                # o no hay ruta
                logger.warning(f"No se puede rutear desde {current} a {dest_id}")
                return []
            
            path.append(next_hop)
            visited.add(next_hop)
            current = next_hop
        
        # Última verificación
        if current == dest_id:
            return path
        
        logger.warning(f"Máximo de saltos alcanzado ({max_hops})")
        return []
    
    def calculate_route_distance(self, start_id: int, dest_id: int) -> int:
        """
        Calcula distancia mínima (número de saltos) entre dos nodos.
        
        En un hipercubo perfecto, la distancia es el número de bits
        diferentes entre los IDs (distancia de Hamming).
        
        Args:
            start_id: Nodo origen
            dest_id: Nodo destino
            
        Returns:
            Número mínimo de saltos
        """
        xor = start_id ^ dest_id
        return bin(xor).count('1')