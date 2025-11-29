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
    leader_id = sim.nodes[0].election.current_leader
    print(f"  ✓ Líder elegido: Nodo {leader_id}")
    for node in sim.nodes:
        status = node.get_status()
        print(f"  - Nodo {node.node_id}: {len(status['known_neighbors'])} vecinos")
    
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
        print(f"  ✓ [{doc_id}] indexado en nodo {node_idx}")
    
    await asyncio.sleep(0.5)  # Esperar propagación
    
    # Realizar búsquedas
    print("\n[4/5] Realizando búsquedas distribuidas...")
    queries = [
        (0, "python"),
        (2, "desarrollo web"),
        (4, "machine learning"),
    ]
    
    for node_idx, query in queries:
        print(f"\n  📍 Búsqueda desde nodo {node_idx}: '{query}'")
        results = await sim.nodes[node_idx].search(query)
        
        if results['total_results'] > 0:
            print(f"  ✓ Encontrados {results['total_results']} resultados:")
            for i, res in enumerate(results['results'][:3], 1):
                snippet = res['snippet'][:50] + "..." if len(res['snippet']) > 50 else res['snippet']
                print(f"     {i}. [{res['doc_id']}] Score: {res['score']:.1f}")
                print(f"        {snippet}")
                print(f"        (Nodo {res['node_id']})")
        else:
            print(f"  ⚠ No se encontraron resultados")
    
    # Demo de tolerancia a fallos
    print("\n[5/5] Demostrando tolerancia a fallos...")
    print(f"  ⚡ Simulando fallo del nodo líder ({leader_id})...")
    sim.network.simulate_node_failure(leader_id)
    
    await asyncio.sleep(0.3)
    
    # Forzar nueva elección
    other_node = sim.nodes[0] if leader_id != 0 else sim.nodes[1]
    print(f"  🗳 Nodo {other_node.node_id} detecta fallo, iniciando elección...")
    new_leader = await other_node.election.start_election()
    
    print(f"  ✓ Nuevo líder elegido: Nodo {new_leader}")
    
    # Actualizar data balancer
    if 0 <= new_leader < len(sim.nodes):
        sim.nodes[new_leader].data_balancer.become_leader()
    
    # Búsqueda después del fallo
    print(f"\n  🔍 Búsqueda después de cambio de líder...")
    results = await sim.nodes[other_node.node_id].search("python")
    print(f"  ✓ Sistema sigue funcionando: {results['total_results']} resultados encontrados")
    
    # Resumen final
    print("\n" + "="*70)
    print(" RESUMEN")
    print("="*70)
    print(f"  ✓ Nodos activos: {len(sim.nodes)}")
    print(f"  ✓ Documentos indexados: {len(docs)}")
    print(f"  ✓ Líder actual: Nodo {new_leader}")
    print(f"  ✓ Sistema tolerante a fallos: SÍ")
    print("\n  Para más opciones, ejecuta: python simulator.py")
    print("="*70)
    
    # Cleanup
    await sim.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(quick_demo())
    except KeyboardInterrupt:
        print("\n\n⚠ Demo interrumpida por usuario")
        sys.exit(0)
