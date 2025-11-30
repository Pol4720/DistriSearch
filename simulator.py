"""
Simulador: ejecuta múltiples nodos en modo demo local.
"""
import asyncio
import logging
import sys
from typing import List
import argparse

from node.node import DistributedNode
from network.simulated_network import SimulatedNetwork


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('distrisearch.log')
    ]
)
logger = logging.getLogger(__name__)


class Simulator:
    """Simulador de red de nodos distribuidos."""
    
    def __init__(self, num_nodes: int = 5, dimensions: int = 20):
        """
        Inicializa el simulador.
        
        Args:
            num_nodes: Número de nodos a crear
            dimensions: Dimensiones del hipercubo
        """
        self.num_nodes = num_nodes
        self.dimensions = dimensions
        self.nodes: List[DistributedNode] = []
        
        # Crear red simulada compartida (usamos node_id=0 como coordinador)
        self.network = SimulatedNetwork(node_id=0, latency_ms=5)
    
    async def setup_nodes(self):
        """Crea e inicializa todos los nodos."""
        print(f"Creando {self.num_nodes} nodos...")  # ← SIN SÍMBOLO ✓
        
        # Generar IDs de nodos (0 a num_nodes-1 para simplificar)
        node_ids = list(range(self.num_nodes))
        
        # Crear nodos
        for node_id in node_ids:
            node = DistributedNode(
                node_id=node_id,
                dimensions=self.dimensions,
                host="localhost",
                port=8000 + node_id,
                network=self.network
            )
            self.nodes.append(node)
        
        # Inicializar nodos con bootstrap
        for i, node in enumerate(self.nodes):
            # Cada nodo conoce a todos los demás al inicio
            bootstrap_nodes = node_ids.copy()
            
            print(f"Inicializando nodo {node.node_id}...")
            await node.initialize(bootstrap_nodes)
        
        # Verificar que hay líder
        leader_id = None
        for node in self.nodes:
            if node.consensus.current_leader is not None:
                leader_id = node.consensus.current_leader
                break
        
        # Inicializar shards en el líder
        if leader_id is not None and 0 <= leader_id < len(self.nodes):
            leader_node = self.nodes[leader_id]
            leader_node.data_balancer.shard_manager.initialize_shards(node_ids)
            print(f"Shards inicializados en nodo lider {leader_id}")
        
        print(f"LISTO: {len(self.nodes)} nodos inicializados")
    
    async def demo_basic_operations(self):
        """Demuestra operaciones básicas."""
        logger.info("\n" + "="*60)
        logger.info("DEMO: Operaciones básicas")
        logger.info("="*60)
        
        # Añadir documentos a diferentes nodos
        docs = [
            (0, "doc1", "Python es un lenguaje de programación interpretado"),
            (1, "doc2", "JavaScript se usa para desarrollo web frontend"),
            (2, "doc3", "Python tiene una gran comunidad de desarrolladores"),
            (0, "doc4", "El desarrollo web moderno usa frameworks como React"),
            (1, "doc5", "Machine learning con Python es muy popular"),
        ]
        
        logger.info("\n1. Añadiendo documentos a nodos...")
        for node_idx, doc_id, content in docs:
            result = await self.nodes[node_idx].add_document(doc_id, content)
            logger.info(f"   Nodo {node_idx}: añadido '{doc_id}' ({result['terms_indexed']} términos)")
        
        # Esperar un poco para que se propague
        await asyncio.sleep(0.5)
        
        # Realizar búsquedas desde diferentes nodos
        queries = [
            (0, "python"),
            (2, "desarrollo web"),
            (1, "machine learning"),
        ]
        
        logger.info("\n2. Realizando búsquedas distribuidas...")
        for node_idx, query in queries:
            logger.info(f"\n   Búsqueda desde nodo {node_idx}: '{query}'")
            result = await self.nodes[node_idx].search(query)
            
            logger.info(f"   Encontrados {result['total_results']} resultados:")
            for i, res in enumerate(result['results'][:3], 1):
                snippet = res['snippet'][:60] + "..." if len(res['snippet']) > 60 else res['snippet']
                logger.info(f"      {i}. [{res['doc_id']}] Score: {res['score']:.1f} - {snippet}")
                logger.info(f"         (en nodo {res['node_id']})")
    
    async def demo_leader_election(self):
        """Demuestra elección de líder."""
        logger.info("\n" + "="*60)
        logger.info("DEMO: Elección de líder")
        logger.info("="*60)
        
        # Mostrar líder actual
        leader_id = self.nodes[0].election.current_leader
        logger.info(f"\nLíder actual: Nodo {leader_id}")
        
        # Simular fallo del líder
        if leader_id is not None and 0 <= leader_id < len(self.nodes):
            logger.info(f"\n>>> Simulando fallo del nodo {leader_id} (líder)...")
            
            # Marcar como fallido en la red simulada
            self.network.simulate_node_failure(leader_id)
            
            # Esperar un poco
            await asyncio.sleep(1)
            
            # Iniciar elección desde otro nodo
            other_node = self.nodes[0] if leader_id != 0 else self.nodes[1]
            logger.info(f"Nodo {other_node.node_id} detecta fallo, iniciando elección...")
            
            new_leader = await other_node.election.start_election()
            
            logger.info(f"\n✓ Nuevo líder elegido: Nodo {new_leader}")
            
            # Actualizar data balancer en el nuevo líder
            if 0 <= new_leader < len(self.nodes):
                self.nodes[new_leader].data_balancer.become_leader()
            
            # Recuperar el nodo caído
            logger.info(f"\n>>> Recuperando nodo {leader_id}...")
            self.network.simulate_node_recovery(leader_id)
            
            # Reiniciar nodo recuperado
            if 0 <= leader_id < len(self.nodes):
                recovered_node = self.nodes[leader_id]
                recovered_node.election.current_leader = new_leader
                recovered_node.data_balancer.become_follower(new_leader)
                logger.info(f"✓ Nodo {leader_id} recuperado, reconoce líder {new_leader}")
    
    async def demo_routing(self):
        """Demuestra ruteo en el hipercubo."""
        logger.info("\n" + "="*60)
        logger.info("DEMO: Ruteo en hipercubo")
        logger.info("="*60)
        
        if len(self.nodes) < 3:
            logger.info("Se necesitan al menos 3 nodos para demostrar ruteo")
            return
        
        # Enviar ping desde nodo 0 a nodo más lejano
        source = self.nodes[0]
        dest_id = self.num_nodes - 1
        
        logger.info(f"\nEnviando PING desde nodo {source.node_id} a nodo {dest_id}")
        logger.info(f"Dirección origen: {source.hypercube.binary_address}")
        logger.info(f"Dirección destino: {self.nodes[dest_id].hypercube.binary_address}")
        logger.info(f"Distancia Hamming: {source.hypercube.hamming_distance(dest_id)}")
        
        ping_msg = {'type': 'ping'}
        response = await source.route_message(dest_id, ping_msg)
        
        if response:
            logger.info(f"✓ Respuesta recibida: {response}")
        else:
            logger.info("✗ No se recibió respuesta")
    
    async def show_network_status(self):
        """Muestra estado de la red."""
        logger.info("\n" + "="*60)
        logger.info("ESTADO DE LA RED")
        logger.info("="*60)
        
        for node in self.nodes:
            status = node.get_status()
            is_leader_str = "★ LÍDER" if status['is_leader'] else ""
            
            logger.info(f"\nNodo {status['node_id']} {is_leader_str}")
            logger.info(f"  Dirección binaria: {status['binary_address']}")
            logger.info(f"  Vecinos activos: {status['known_neighbors']}")
            logger.info(f"  Documentos: {status['storage_stats']['num_documents']}")
            logger.info(f"  Términos: {status['storage_stats']['num_terms']}")
    
    async def interactive_menu(self):
        """Menú interactivo para demos."""
        logger.info("\n" + "="*60)
        logger.info("MENÚ INTERACTIVO")
        logger.info("="*60)
        
        while True:
            print("\nOpciones:")
            print("  1. Mostrar estado de la red")
            print("  2. Demo: Operaciones básicas (indexado y búsqueda)")
            print("  3. Demo: Ruteo en hipercubo")
            print("  4. Demo: Elección de líder")
            print("  5. Añadir documento personalizado")
            print("  6. Buscar")
            print("  0. Salir")
            
            try:
                choice = input("\nSelecciona opción: ").strip()
                
                if choice == '0':
                    break
                elif choice == '1':
                    await self.show_network_status()
                elif choice == '2':
                    await self.demo_basic_operations()
                elif choice == '3':
                    await self.demo_routing()
                elif choice == '4':
                    await self.demo_leader_election()
                elif choice == '5':
                    await self._interactive_add_doc()
                elif choice == '6':
                    await self._interactive_search()
                else:
                    print("Opción no válida")
            
            except (EOFError, KeyboardInterrupt):
                break
    
    async def _interactive_add_doc(self):
        """Añade documento interactivamente."""
        try:
            node_idx = int(input(f"Nodo (0-{self.num_nodes-1}): "))
            if not (0 <= node_idx < self.num_nodes):
                print("Nodo inválido")
                return
            
            doc_id = input("ID del documento: ").strip()
            content = input("Contenido: ").strip()
            
            result = await self.nodes[node_idx].add_document(doc_id, content)
            print(f"✓ Documento añadido: {result['terms_indexed']} términos")
        
        except Exception as e:
            print(f"Error: {e}")
    
    async def _interactive_search(self):
        """Busca interactivamente."""
        try:
            node_idx = int(input(f"Nodo desde el que buscar (0-{self.num_nodes-1}): "))
            if not (0 <= node_idx < self.num_nodes):
                print("Nodo inválido")
                return
            
            query = input("Consulta: ").strip()
            
            result = await self.nodes[node_idx].search(query)
            
            print(f"\n✓ Encontrados {result['total_results']} resultados:")
            for i, res in enumerate(result['results'], 1):
                print(f"\n{i}. {res['doc_id']} (Score: {res['score']:.2f}, Nodo: {res['node_id']})")
                print(f"   {res['snippet']}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    async def run_auto_demo(self):
        """Ejecuta todas las demos automáticamente."""
        await self.show_network_status()
        await asyncio.sleep(2)
        
        await self.demo_basic_operations()
        await asyncio.sleep(2)
        
        await self.demo_routing()
        await asyncio.sleep(2)
        
        await self.demo_leader_election()
        await asyncio.sleep(2)
        
        await self.show_network_status()
    
    async def cleanup(self):
        """Limpia recursos."""
        logger.info("\nCerrando simulador...")
        
        for node in self.nodes:
            try:
                await node.shutdown()
            except Exception as e:
                logger.error(f"Error cerrando nodo {node.node_id}: {e}")
        
        logger.info("OK Simulador cerrado")  # ← CAMBIAR ✓ por OK


async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description='Simulador de buscador distribuido')
    parser.add_argument('--nodes', type=int, default=5, help='Número de nodos (default: 5)')
    parser.add_argument('--dimensions', type=int, default=20, help='Dimensiones del hipercubo (default: 20)')
    parser.add_argument('--auto', action='store_true', help='Ejecutar demos automáticas')
    parser.add_argument('--debug', action='store_true', help='Activar logging DEBUG')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Crear simulador
    sim = Simulator(num_nodes=args.nodes, dimensions=args.dimensions)
    
    try:
        # Configurar nodos
        await sim.setup_nodes()
        
        # Ejecutar demos
        if args.auto:
            await sim.run_auto_demo()
        else:
            await sim.interactive_menu()
    
    finally:
        await sim.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
