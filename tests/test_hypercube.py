"""
Tests para el módulo hypercube (topología y ruteo).
"""
import pytest
from core.hypercube import HypercubeNode, HypercubeTopology
from core.routing import HypercubeRouter
from core.node_id import generate_node_id


def test_hypercube_node_creation():
    """Test creación de nodo hipercubo."""
    node = HypercubeNode(node_id=5, dimensions=4)
    
    assert node.node_id == 5
    assert node.dimensions == 4
    assert node.binary_address == "0101"


def test_hypercube_neighbors():
    """Test cálculo de vecinos."""
    node = HypercubeNode(node_id=5, dimensions=4)  # 0101
    neighbors = node.get_neighbors()
    
    # Debe tener 4 vecinos (uno por cada bit que puede flipear)
    assert len(neighbors) == 4
    
    # Vecinos esperados: 0100 (4), 0111 (7), 0001 (1), 1101 (13)
    expected = [4, 7, 1, 13]
    assert set(neighbors) == set(expected)


def test_hamming_distance():
    """Test distancia de Hamming."""
    node = HypercubeNode(node_id=5, dimensions=4)  # 0101
    
    assert node.hamming_distance(5) == 0  # Misma dirección
    assert node.hamming_distance(4) == 1  # 0100 - difiere en 1 bit
    assert node.hamming_distance(7) == 1  # 0111 - difiere en 1 bit
    assert node.hamming_distance(10) == 4  # 1010 - todos los bits diferentes


def test_xor_distance():
    """Test distancia XOR."""
    node = HypercubeNode(node_id=5, dimensions=4)
    
    assert node.xor_distance(5) == 0
    assert node.xor_distance(4) == 1
    assert node.xor_distance(7) == 2


def test_route_next_hop_direct_neighbor():
    """Test ruteo a vecino directo."""
    current = 5  # 0101
    dest = 7     # 0111
    neighbors = {4, 7, 1, 13}
    
    router = HypercubeRouter(dimensions=4)
    next_hop = router.route_next_hop(current, dest, neighbors)
    
    # Debe seleccionar el vecino 7 directamente
    assert next_hop == 7


def test_route_next_hop_greedy():
    """Test ruteo greedy cuando no hay vecino directo."""
    current = 0   # 0000
    dest = 15     # 1111
    neighbors = {1, 2, 4, 8}  # Solo un bit cambiado cada uno
    
    router = HypercubeRouter(dimensions=4)
    next_hop = router.route_next_hop(current, dest, neighbors)
    
    # Debe elegir un vecino que reduzca la distancia XOR
    assert next_hop in neighbors


def test_route_next_hop_destination_reached():
    """Test cuando ya estamos en el destino."""
    current = 5
    dest = 5
    neighbors = {4, 7, 1, 13}
    
    router = HypercubeRouter(dimensions=4)
    next_hop = router.route_next_hop(current, dest, neighbors)
    
    assert next_hop is None


def test_calculate_route_path():
    """Test cálculo de ruta completa."""
    start = 0
    dest = 15  # 1111
    active_nodes = set(range(16))  # Todos los nodos activos
    
    router = HypercubeRouter(dimensions=4)
    path = router.calculate_route_path(start, dest, active_nodes)
    
    # Verificar que la ruta existe
    assert len(path) > 0
    assert path[0] == start
    assert path[-1] == dest
    
    # No debe tener loops
    assert len(path) == len(set(path))
    
    # Debe completarse en <= dimensions saltos (para hipercubo completo)
    assert len(path) - 1 <= 4


def test_calculate_route_path_missing_nodes():
    """Test ruteo con nodos faltantes."""
    start = 0
    dest = 7
    # Solo algunos nodos activos
    active_nodes = {0, 1, 3, 7}
    
    router = HypercubeRouter(dimensions=4)
    path = router.calculate_route_path(start, dest, active_nodes)
    
    # Debe encontrar ruta usando nodos disponibles
    assert path[0] == start
    assert path[-1] == dest
    assert all(node in active_nodes for node in path)


def test_generate_node_id():
    """Test generación de ID desde semilla."""
    id1 = generate_node_id("localhost:8000", dimensions=8)
    id2 = generate_node_id("localhost:8001", dimensions=8)
    id3 = generate_node_id("localhost:8000", dimensions=8)
    
    # IDs diferentes para semillas diferentes
    assert id1 != id2
    
    # Mismo ID para misma semilla
    assert id1 == id3
    
    # Debe estar en rango válido
    assert 0 <= id1 < 256


def test_hypercube_invalid_id():
    """Test validación de ID inválido."""
    with pytest.raises(ValueError):
        HypercubeNode(node_id=20, dimensions=4)  # 20 > 15 (max para 4 bits)
    
    with pytest.raises(ValueError):
        HypercubeNode(node_id=-1, dimensions=4)
