"""
Módulo core del nodo distribuido.
Contiene la inicialización y gestión de componentes básicos.
"""
import asyncio
import logging
from typing import Set, List, Optional

from core.hypercube import HypercubeNode
from storage import DocumentStore, InvertedIndex
from storage.persistence import PersistenceManager
from network.simulated_network import SimulatedNetwork
from network.http_network import HTTPNetwork
from network.network_interface import NetworkInterface
from consensus import RaftConsensus, NodeState
from replication.replica_manager import ReplicaManager
from replication.quorum import QuorumConfig
from balancer import DataBalancer

logger = logging.getLogger(__name__)


class NodeCore:
    """
    Clase base que contiene todos los componentes del nodo.
    Maneja inicialización y configuración básica.
    """
    
    def __init__(
        self, 
        node_id: int, 
        dimensions: int = 20, 
        host: str = "localhost", 
        port: int = 8000,
        network: NetworkInterface = None,
        enable_tls: bool = False
    ):
        """
        Inicializa componentes del nodo.
        
        Args:
            node_id: ID único del nodo
            dimensions: Dimensiones del hipercubo (default 20)
            host: Host para servidor HTTP
            port: Puerto para servidor HTTP
            network: Interfaz de red (None = simulada)
            enable_tls: Habilitar TLS/SSL
        """
        self.node_id = node_id
        self.dimensions = dimensions
        self.host = host
        self.port = port
        
        # Componentes de topología
        self.hypercube = HypercubeNode(node_id, dimensions)
        
        # Storage
        self.document_store = DocumentStore()
        self.inverted_index = InvertedIndex()
        self.persistence = PersistenceManager(f"data/node_{node_id}")
        
        # Red
        self.network = network or SimulatedNetwork(node_id)
        
        # Vecinos y nodos activos
        self.known_neighbors: Set[int] = set()
        self.active_nodes: Set[int] = set()
        
        # Consenso Raft
        self.consensus = RaftConsensus(
            node_id=node_id,
            all_node_ids=self.active_nodes,
            network=self.network
        )
        
        # Replicación de documentos
        self.replication = ReplicaManager(
            node_id=node_id,
            network=self.network,
            hypercube=self.hypercube,
            config=QuorumConfig(replication_factor=3, write_quorum=2, read_quorum=2)
        )
        
        # Data Balancer
        self.data_balancer = DataBalancer(node_id=node_id)
        
        logger.info(
            f"NodeCore {node_id} inicializado "
            f"(dims={dimensions}, TLS={enable_tls})"
        )
    
    async def initialize(self, bootstrap_nodes: List[int] = None):
        """
        Inicializa el nodo y se une a la red.
        
        Args:
            bootstrap_nodes: Lista de IDs de nodos existentes para unirse
        """
        # Registrar en la red
        await self.network.register_node(self.node_id, self)
        
        # Actualizar nodos activos
        if bootstrap_nodes:
            self.active_nodes = set(bootstrap_nodes)
        else:
            self.active_nodes = {self.node_id}
        
        # Actualizar vecinos conocidos
        self._update_known_neighbors()
        
        # Actualizar consenso con nodos activos
        self.consensus.all_nodes = self.active_nodes.copy()
        
        # Actualizar replicación con nodos activos
        self.replication.update_active_nodes(list(self.active_nodes))
        
        # Iniciar consenso Raft
        await self.consensus.start()
        
        # Esperar a que se elija líder
        await asyncio.sleep(2.0)
        
        # Si soy líder, activar Data Balancer
        if self.consensus.state == NodeState.LEADER:
            self.data_balancer.become_leader()
            # Inicializar sharding con nodos activos
            self.data_balancer.shard_manager.initialize_shards(
                list(self.active_nodes)
            )
            logger.info(f"Nodo {self.node_id}: Shards inicializados como líder")
        
        logger.info(
            f"Nodo {self.node_id} inicializado. "
            f"Líder: {self.consensus.current_leader}, "
            f"Estado Raft: {self.consensus.state.state.value}"
        )
    
    def _update_known_neighbors(self):
        """Actualiza lista de vecinos conocidos que están activos."""
        potential_neighbors = set(self.hypercube.get_neighbors())
        self.known_neighbors = potential_neighbors & self.active_nodes
        
        logger.debug(
            f"Nodo {self.node_id}: {len(self.known_neighbors)} vecinos activos"
        )
    
    def get_status(self) -> dict:
        """
        Obtiene estado completo del nodo.
        
        Returns:
            Diccionario con estado del nodo y todos sus componentes
        """
        from metrics import raft_term, raft_state, index_size
        
        # Actualizar métricas Prometheus
        raft_term.labels(node_id=self.node_id).set(self.consensus.current_term)
        state_map = {
            NodeState.FOLLOWER: 0, 
            NodeState.CANDIDATE: 1, 
            NodeState.LEADER: 2
        }
        raft_state.labels(node_id=self.node_id).set(
            state_map[self.consensus.state]
        )
        index_size.labels(node_id=self.node_id).set(len(self.storage.index))
        
        return {
            'node_id': self.node_id,
            'binary_address': self.hypercube.binary_address,
            'raft_state': self.consensus.state.value,
            'raft_term': self.consensus.current_term,
            'current_leader': self.consensus.current_leader,
            'known_neighbors': list(self.known_neighbors),
            'active_nodes': list(self.active_nodes),
            'storage_stats': self.storage.get_stats(),
            'cache_stats': self.cache.local_cache.stats(),
            'shard_stats': (
                self.data_balancer.shard_manager.get_shard_stats() 
                if self.consensus.state == NodeState.LEADER 
                else {}
            )
        }
    
    async def shutdown(self):
        """Apaga el nodo limpiamente."""
        logger.info(f"Apagando nodo {self.node_id}...")
        
        # Detener consenso
        await self.consensus.stop()
        
        # Detener Data Balancer
        await self.data_balancer.shutdown()
        
        # Guardar estado
        self.storage.save()
        
        # Cerrar red
        if hasattr(self.network, 'close'):
            await self.network.close()
        
        logger.info(f"Nodo {self.node_id} apagado")
