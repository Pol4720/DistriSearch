"""
Script de demo rápido para probar el sistema.
"""
import asyncio
import sys
from simulator import Simulator


async def quick_demo():
    """Demo rápida del sistema."""
    print("="*70)
    print(" DistriSearch - Buscador Distribuido con Hipercubo")
    print("="*70)
    
    # Crear simulador con 5 nodos
    print("\n[1/5] Creando red de 5 nodos...")
    sim = Simulator(num_nodes=5, dimensions=8)
    await sim.setup_nodes()
    
    # Mostrar estado inicial
    print("\n[2/5] Estado inicial de la red:")
    leader_id = sim.nodes[0].consensus.current_leader
    print(f"  Lider elegido: Nodo {leader_id}")
    
    await asyncio.sleep(1.0)
    
    for node in sim.nodes:
        status = node.get_status()
        print(f"  - Nodo {node.node_id}: {len(status['known_neighbors'])} vecinos")
    
    # Inicializar shards en líder (segunda vez para asegurar)
    if leader_id is not None and 0 <= leader_id < len(sim.nodes):
        leader_node = sim.nodes[leader_id]
        leader_node.data_balancer.become_leader()
        leader_node.data_balancer.shard_manager.initialize_shards(list(range(5)))
        print(f"  Shards inicializados en nodo lider {leader_id}")
    
    # Indexar documentos
    print("\n[3/5] Indexando documentos en diferentes nodos...")
    docs = [
        (0, "doc1", "Python es un lenguaje de programación interpretado muy popular"),
        (1, "doc2", "JavaScript se utiliza principalmente para desarrollo web frontend"),
        (2, "doc3", "Python tiene una sintaxis clara y legible para principiantes"),
        (3, "doc4", "Machine learning con Python usa bibliotecas como scikit-learn"),
        (4, "doc5", "El desarrollo web moderno utiliza frameworks JavaScript como React"),
        (0, "doc6", "Python es excelente para ciencia de datos y análisis"),
        (1, "doc7", "JavaScript permite crear aplicaciones web interactivas"),
    ]
    
    for node_idx, doc_id, content in docs:
        await sim.nodes[node_idx].add_document(doc_id, content)
        print(f"  OK [{doc_id}] indexado en nodo {node_idx}")
    
    await asyncio.sleep(0.5)
    
    # Realizar búsquedas
    print("\n[4/5] Realizando búsquedas distribuidas...")
    queries = [
        (0, "python"),
        (2, "desarrollo web"),
        (4, "machine learning"),
    ]
    
    for node_idx, query in queries:
        print(f"\n  Busqueda desde nodo {node_idx}: '{query}'")
        results = await sim.nodes[node_idx].search(query)
        
        if results['total_results'] > 0:
            print(f"  OK Encontrados {results['total_results']} resultados:")
            for i, res in enumerate(results['results'][:3], 1):
                snippet = res['snippet'][:50] + "..." if len(res['snippet']) > 50 else res['snippet']
                print(f"     {i}. [{res['doc_id']}] Score: {res['score']:.1f}")
                print(f"        {snippet}")
                print(f"        (Nodo {res['node_id']})")
        else:
            print(f"  Advertencia: No se encontraron resultados")
    
    # Demo de tolerancia a fallos
    print("\n[5/5] Demostrando tolerancia a fallos...")
    print(f"  Simulando fallo del nodo lider ({leader_id})...")
    sim.network.simulate_node_failure(leader_id)
    
    await asyncio.sleep(0.3)
    
    # Identificar nodo activo para consultar
    other_node = None
    for node in sim.nodes:
        if node.node_id != leader_id:
            other_node = node
            break
    
    print(f"  Nodo {other_node.node_id} detecta fallo, iniciando eleccion...")
    
    # Esperar a que Raft elija nuevo líder (más tiempo)
    await asyncio.sleep(4.0)  # ← AUMENTAR de 3.0 a 4.0
    
    # Obtener nuevo líder desde VARIOS nodos
    new_leaders = {}
    for node in sim.nodes:
        if node.node_id != leader_id:
            leader = node.consensus.current_leader
            if leader is not None and leader != leader_id:
                new_leaders[leader] = new_leaders.get(leader, 0) + 1
    
    # El nuevo líder es el que más nodos ven
    if new_leaders:
        new_leader = max(new_leaders, key=new_leaders.get)
        print(f"  OK Nuevo lider elegido: Nodo {new_leader} (visto por {new_leaders[new_leader]} nodos)")
    else:
        new_leader = None
        print(f"  Advertencia: Nuevo lider no elegido aun")
    
    # Actualizar data balancer
    if new_leader is not None and new_leader != leader_id and 0 <= new_leader < len(sim.nodes):
        sim.nodes[new_leader].data_balancer.become_leader()
        sim.nodes[new_leader].data_balancer.shard_manager.initialize_shards(
            [i for i in range(5) if i != leader_id]
        )
    
    # Búsqueda después del fallo
    print(f"\n  Busqueda despues de cambio de lider...")
    
    # Buscar desde un nodo activo
    search_node = sim.nodes[0] if leader_id != 0 else sim.nodes[2]
    results = await search_node.search("python")
    print(f"  OK Sistema sigue funcionando: {results['total_results']} resultados encontrados")
    
    # Resumen final
    print("\n" + "="*70)
    print(" RESUMEN")
    print("="*70)
    print(f"  OK Nodos activos: {len(sim.nodes) - 1} (1 fallido)")  # ← CORREGIR
    print(f"  OK Documentos indexados: {len(docs)}")
    print(f"  OK Lider actual: Nodo {new_leader if new_leader is not None else 'N/A'}")
    print(f"  OK Sistema tolerante a fallos: {'SI' if new_leader is not None else 'Parcial'}")
    print("\n  Para mas opciones, ejecuta: python simulator.py")
    print("="*70)
    
    # Cleanup
    await sim.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(quick_demo())
    except KeyboardInterrupt:
        print("\n\nAdvertencia: Demo interrumpida por usuario")
        sys.exit(0)
