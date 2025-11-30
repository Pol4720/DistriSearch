"""
Topología de hipercubo lógico.
Define estructura y relaciones entre nodos.
"""
import logging
from typing import List, Set
from core.node_id import NodeID, validate_node_id

logger = logging.getLogger(__name__)


class HypercubeNode:
    """
    Representa un nodo en la topología de hipercubo.
    
    Responsabilidades:
    - Mantener ID del nodo
    - Calcular vecinos directos
    - Proporcionar información de topología
    """
    
    def __init__(self, node_id: int, dimensions: int = 20):
        """
        Inicializa un nodo del hipercubo.
        
        Args:
            node_id: ID único del nodo [0, 2^dimensions - 1]
            dimensions: Dimensiones del hipercubo
            
        Raises:
            ValueError: Si node_id está fuera de rango
        """
        if not validate_node_id(node_id, dimensions):
            raise ValueError(
                f"node_id {node_id} inválido para {dimensions} dimensiones"
            )
        
        self.node_id = NodeID(node_id, dimensions)
        self.dimensions = dimensions
    
    @property
    def id(self) -> int:
        """Retorna ID numérico del nodo."""
        return self.node_id.value
    
    @property
    def binary_id(self) -> str:
        """Retorna ID en formato binario."""
        return self.node_id.binary
    
    def get_neighbors(self) -> List[int]:
        """
        Calcula IDs de todos los vecinos directos.
        
        En un hipercubo, cada nodo tiene exactamente `dimensions` vecinos,
        obtenidos invirtiendo cada bit del ID.
        
        Returns:
            Lista de IDs de vecinos
            
        Example:
            >>> node = HypercubeNode(5, dimensions=4)  # 0101
            >>> node.get_neighbors()
            [4, 7, 1, 13]  # 0100, 0111, 0001, 1101
        """
        neighbors = []
        for i in range(self.dimensions):
            # Invertir bit i-ésimo
            neighbor_id = self.id ^ (1 << i)
            neighbors.append(neighbor_id)
        
        return neighbors
    
    def is_neighbor(self, other_id: int) -> bool:
        """
        Verifica si otro nodo es vecino directo.
        
        Args:
            other_id: ID del otro nodo
            
        Returns:
            True si es vecino, False si no
        """
        # Dos nodos son vecinos si difieren en exactamente 1 bit
        xor = self.id ^ other_id
        return bin(xor).count('1') == 1
    
    @property
    def binary_address(self) -> str:
        """
        Retorna dirección binaria del nodo (alias de binary_id para compatibilidad).
        
        Returns:
            String binario formateado
        """
        return self.binary_id
    
    def hamming_distance(self, other_id: int) -> int:
        """
        Calcula distancia de Hamming a otro nodo.
        
        Args:
            other_id: ID del otro nodo
            
        Returns:
            Número de bits diferentes
        """
        xor = self.id ^ other_id
        return bin(xor).count('1')
    
    def xor_distance(self, other_id: int) -> int:
        """
        Calcula distancia XOR a otro nodo.
        
        Args:
            other_id: ID del otro nodo
            
        Returns:
            Valor XOR de los IDs
        """
        return self.id ^ other_id
    
    def distance_to(self, other_id: int) -> int:
        """
        Calcula distancia de Hamming a otro nodo.
        
        Args:
            other_id: ID del otro nodo
            
        Returns:
            Número de bits diferentes
        """
        other_node = NodeID(other_id, self.dimensions)
        return self.node_id.distance_to(other_node)
    
    def __repr__(self):
        return f"HypercubeNode(id={self.id}, binary={self.binary_id})"


class HypercubeTopology:
    """
    Gestiona la topología completa del hipercubo.
    
    Responsabilidades:
    - Validar estructura de red
    - Calcular métricas de topología
    - Verificar conectividad
    """
    
    def __init__(self, dimensions: int = 20):
        self.dimensions = dimensions
        self.max_nodes = 1 << dimensions  # 2^dimensions
    
    def calculate_diameter(self) -> int:
        """
        Calcula el diámetro del hipercubo.
        
        El diámetro es la máxima distancia entre dos nodos,
        que en un hipercubo es igual a las dimensiones.
        
        Returns:
            Diámetro de la red
        """
        return self.dimensions
    
    def calculate_network_density(self, num_active_nodes: int) -> float:
        """
        Calcula densidad de la red.
        
        Args:
            num_active_nodes: Número de nodos activos
            
        Returns:
            Densidad [0.0, 1.0]
        """
        if self.max_nodes == 0:
            return 0.0
        
        return num_active_nodes / self.max_nodes
    
    def estimate_avg_hops(self, num_active_nodes: int) -> float:
        """
        Estima número promedio de saltos en la red.
        
        En un hipercubo denso: ~dimensions/2
        En un hipercubo disperso: mayor
        
        Args:
            num_active_nodes: Número de nodos activos
            
        Returns:
            Estimación de saltos promedio
        """
        density = self.calculate_network_density(num_active_nodes)
        
        if density > 0.5:
            # Red densa: cerca del ideal
            return self.dimensions / 2
        else:
            # Red dispersa: más saltos necesarios
            return self.dimensions * (1 / density) ** 0.5
    
    def get_expected_neighbors(self, node_id: int) -> int:
        """
        Retorna el número esperado de vecinos para un nodo.
        
        Args:
            node_id: ID del nodo
            
        Returns:
            Número de vecinos (siempre `dimensions` en hipercubo perfecto)
        """
        return self.dimensions