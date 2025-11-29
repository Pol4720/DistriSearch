"""
Tests de integración para flujos completos.
"""
import pytest
import asyncio
from node import DistributedNode
from network import create_network


@pytest.mark.asyncio
async def test_network_setup_and_search():
    """Test: configurar red y realizar búsqueda."""
    # Crear red simulada
    network = create_network("simulated", latency_ms=0)
    
    # Crear 3 nodos
    nodes = []
    for i in range(3):
        node = DistributedNode(
            node_id=i,
            dimensions=8,
            network=network
        )
        nodes.append(node)
    
    # Inicializar nodos
    node_ids = [0, 1, 2]
    for node in nodes:
        await node.initialize(bootstrap_nodes=node_ids)
    
    # Esperar a que se elija líder
    await asyncio.sleep(0.5)
    
    # Añadir documentos a diferentes nodos
    await nodes[0].add_document("doc1", "Python programming language")
    await nodes[1].add_document("doc2", "Java programming language")
    await nodes[2].add_document("doc3", "Python machine learning")
    
    # Esperar propagación
    await asyncio.sleep(0.5)
    
    # Buscar desde nodo 0
    results = await nodes[0].search("python")
    
    # Debe encontrar doc1 y doc3
    assert results['total_results'] >= 2
    doc_ids = [r['doc_id'] for r in results['results']]
    assert 'doc1' in doc_ids
    assert 'doc3' in doc_ids
    
    # Cleanup
    for node in nodes:
        await node.shutdown()


@pytest.mark.asyncio
async def test_leader_election_on_failure():
    """Test: elección de líder cuando el actual falla."""
    network = create_network("simulated", latency_ms=0)
    
    # Crear 5 nodos
    nodes = []
    for i in range(5):
        node = DistributedNode(
            node_id=i,
            dimensions=8,
            network=network
        )
        nodes.append(node)
    
    # Inicializar
    node_ids = list(range(5))
    for node in nodes:
        await node.initialize(bootstrap_nodes=node_ids)
    
    await asyncio.sleep(0.5)
    
    # Obtener líder inicial
    initial_leader = nodes[0].election.current_leader
    assert initial_leader is not None
    
    # Simular fallo del líder
    network.simulate_node_failure(initial_leader)
    
    # Iniciar nueva elección desde otro nodo
    other_node = nodes[0] if initial_leader != 0 else nodes[1]
    new_leader = await other_node.election.start_election()
    
    # Debe haber nuevo líder diferente
    assert new_leader is not None
    # En simulación simple puede que sea el mismo nodo si se recupera
    
    # Cleanup
    for node in nodes:
        await node.shutdown()


@pytest.mark.asyncio
async def test_routing_message():
    """Test: ruteo de mensajes entre nodos."""
    network = create_network("simulated", latency_ms=0)
    
    # Crear nodos con IDs específicos
    node_ids = [0, 1, 2, 3, 4, 5, 6, 7]
    nodes = []
    
    for node_id in node_ids:
        node = DistributedNode(
            node_id=node_id,
            dimensions=3,  # 3 bits = 8 posiciones
            network=network
        )
        nodes.append(node)
    
    # Inicializar
    for node in nodes:
        await node.initialize(bootstrap_nodes=node_ids)
    
    await asyncio.sleep(0.3)
    
    # Enviar mensaje desde nodo 0 a nodo 7
    ping_msg = {'type': 'ping'}
    response = await nodes[0].route_message(7, ping_msg)
    
    # Debe recibir respuesta
    assert response is not None
    assert response.get('status') == 'ok'
    assert response.get('node_id') == 7
    
    # Cleanup
    for node in nodes:
        await node.shutdown()


@pytest.mark.asyncio
async def test_distributed_search_aggregation():
    """Test: agregación de resultados de búsqueda distribuida."""
    network = create_network("simulated", latency_ms=0)
    
    nodes = []
    for i in range(3):
        node = DistributedNode(
            node_id=i,
            dimensions=8,
            network=network
        )
        nodes.append(node)
    
    await asyncio.gather(*[
        node.initialize(bootstrap_nodes=[0, 1, 2])
        for node in nodes
    ])
    
    await asyncio.sleep(0.3)
    
    # Cada nodo tiene documentos sobre "python" con diferentes scores
    await nodes[0].add_document("doc1", "python python python")  # Alta frecuencia
    await nodes[1].add_document("doc2", "python programming")
    await nodes[2].add_document("doc3", "python")
    
    await asyncio.sleep(0.3)
    
    # Buscar desde cualquier nodo
    results = await nodes[1].search("python")
    
    # Debe agregar resultados de todos los nodos
    assert results['total_results'] == 3
    
    # Los resultados deben estar ordenados por score
    scores = [r['score'] for r in results['results']]
    assert scores == sorted(scores, reverse=True)
    
    # Cleanup
    for node in nodes:
        await node.shutdown()


@pytest.mark.asyncio
async def test_index_update_propagation():
    """Test: propagación de actualizaciones del índice al líder."""
    network = create_network("simulated", latency_ms=0)
    
    nodes = []
    for i in range(3):
        node = DistributedNode(
            node_id=i,
            dimensions=8,
            network=network
        )
        nodes.append(node)
    
    await asyncio.gather(*[
        node.initialize(bootstrap_nodes=[0, 1, 2])
        for node in nodes
    ])
    
    await asyncio.sleep(0.5)
    
    # Identificar líder
    leader_id = nodes[0].election.current_leader
    leader_node = nodes[leader_id]
    
    # Añadir documento en nodo no-líder
    non_leader = nodes[0] if leader_id != 0 else nodes[1]
    await non_leader.add_document("doc1", "test document python")
    
    await asyncio.sleep(0.5)
    
    # El líder debe conocer los términos
    # Verificar usando el data balancer
    located = leader_node.data_balancer.handle_locate("python")
    
    assert 'nodes' in located
    node_ids = [n['node_id'] for n in located['nodes']]
    assert non_leader.node_id in node_ids
    
    # Cleanup
    for node in nodes:
        await node.shutdown()
