"""
DistriSearch - Inicialización del Cluster

Inicializa los servicios del cluster Master-Slave:
- HeartbeatService para monitoreo de nodos
- BullyElection para elección de líder
- Integración con el estado del cluster
"""
import asyncio
import logging
from typing import Optional, Dict

# Importar desde el nuevo módulo cluster
from cluster import HeartbeatService, BullyElection

logger = logging.getLogger(__name__)

# Estado global del cluster (importación tardía para evitar circular)
cluster_state = None

def _get_cluster_state():
    """Obtiene el estado del cluster (importación tardía)"""
    global cluster_state
    if cluster_state is None:
        from routes.cluster import cluster_state as cs
        cluster_state = cs
    return cluster_state


class ClusterInitializer:
    """
    Inicializador del cluster que configura:
    - Servicios de heartbeat
    - Elección de líder
    - Conexión entre componentes
    """
    
    def __init__(self):
        self.heartbeat_service: Optional[HeartbeatService] = None
        self.election_service: Optional[BullyElection] = None
        self._tasks: list = []
    
    def _parse_peers(self) -> list:
        """
        Parsea la variable de entorno CLUSTER_PEERS.
        Formato: node_id:ip:http_port:hb_port:el_port,...
        """
        peers_str = os.getenv("CLUSTER_PEERS", "")
        if not peers_str:
            return []
        
        peers = []
        for peer in peers_str.split(","):
            parts = peer.strip().split(":")
            if len(parts) >= 5:
                peers.append({
                    "node_id": parts[0],
                    "ip_address": parts[1],
                    "http_port": int(parts[2]),
                    "heartbeat_port": int(parts[3]),
                    "election_port": int(parts[4]),
                    "can_be_master": True
                })
        
        return peers
    
    async def initialize(self) -> None:
        """Inicializa todos los servicios del cluster"""
        node_id = os.getenv("NODE_ID", "node_1")
        heartbeat_port = int(os.getenv("HEARTBEAT_PORT", "5000"))
        election_port = int(os.getenv("ELECTION_PORT", "5001"))
        heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "5"))
        heartbeat_timeout = int(os.getenv("HEARTBEAT_TIMEOUT", "15"))
        master_candidate = os.getenv("MASTER_CANDIDATE", "true").lower() == "true"
        
        peers = self._parse_peers()
        
        logger.info(f"🔧 Inicializando cluster para nodo {node_id}")
        logger.info(f"   Peers: {[p['node_id'] for p in peers]}")
        logger.info(f"   Puede ser Master: {master_candidate}")
        
        # Crear servicio de heartbeat
        self.heartbeat_service = HeartbeatService(
            node_id=node_id,
            port=heartbeat_port,
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            on_node_down=self._on_node_down,
            on_master_down=self._on_master_down
        )
        
        # Crear servicio de elección
        self.election_service = BullyElection(
            node_id=node_id,
            port=election_port,
            on_become_master=self._on_become_master,
            on_new_master=self._on_new_master
        )
        
        # Registrar peers
        for peer in peers:
            # Para heartbeat
            self.heartbeat_service.add_peer(
                peer["node_id"],
                peer["ip_address"],
                peer["heartbeat_port"]
            )
            
            # Para elección
            self.election_service.add_peer(
                peer["node_id"],
                peer["ip_address"],
                peer["election_port"],
                peer.get("can_be_master", True)
            )
        
        # Guardar referencias en cluster_state
        cs = _get_cluster_state()
        cs.heartbeat_service = self.heartbeat_service
        cs.election_service = self.election_service
        
        # Iniciar servicios
        await self.heartbeat_service.start()
        await self.election_service.start()
        
        logger.info("✅ Servicios de heartbeat y elección iniciados")
        
        # Si somos el nodo con ID más alto o no hay otros, iniciar elección
        if master_candidate:
            # Esperar un poco para que otros nodos se inicien
            await asyncio.sleep(2)
            
            # Si no conocemos un master, iniciar elección
            if cs.current_master is None:
                logger.info("🗳️ Iniciando elección de líder...")
                await self.election_service.start_election()
    
    async def shutdown(self) -> None:
        """Detiene los servicios del cluster"""
        logger.info("🛑 Deteniendo servicios del cluster...")
        
        if self.heartbeat_service:
            await self.heartbeat_service.stop()
        
        if self.election_service:
            await self.election_service.stop()
        
        logger.info("✅ Servicios del cluster detenidos")
    
    def _on_node_down(self, node_id: str) -> None:
        """Callback cuando un nodo cae"""
        logger.warning(f"⚠️ Nodo caído detectado: {node_id}")
        
        cs = _get_cluster_state()
        # Actualizar estado en cluster_state
        if node_id in cs.peers:
            # Marcar como offline
            pass
    
    def _on_master_down(self) -> None:
        """Callback cuando el master cae"""
        logger.warning("🚨 ¡MASTER CAÍDO! Iniciando nueva elección...")
        
        cs = _get_cluster_state()
        cs.current_master = None
        cs.is_master = False
        
        # Iniciar elección en background
        asyncio.create_task(self.election_service.start_election())
    
    def _on_become_master(self) -> None:
        """Callback cuando este nodo se convierte en master"""
        logger.info("👑 ¡Este nodo es ahora el MASTER!")
        
        cs = _get_cluster_state()
        cs.is_master = True
        cs.current_master = cs.node_id
        
        # Inicializar componentes de Master
        self._initialize_master_components()
    
    def _on_new_master(self, master_id: str) -> None:
        """Callback cuando hay un nuevo master"""
        logger.info(f"📢 Nuevo MASTER anunciado: {master_id}")
        
        cs = _get_cluster_state()
        cs.current_master = master_id
        cs.is_master = False
        
        # Actualizar heartbeat service
        if self.heartbeat_service:
            self.heartbeat_service.set_master(master_id)
    
    def _initialize_master_components(self) -> None:
        """Inicializa componentes específicos del Master"""
        try:
            from master.location_index import SemanticLocationIndex
            from master.load_balancer import LoadBalancer
            from master.embedding_service import get_embedding_service
            
            cs = _get_cluster_state()
            
            # Crear índice de ubicación
            embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            embedding_service = get_embedding_service(embedding_model)
            
            cs.location_index = SemanticLocationIndex(
                embedding_dim=embedding_service.embedding_dim
            )
            
            # Crear balanceador
            cs.load_balancer = LoadBalancer(strategy="weighted")
            
            logger.info("✅ Componentes de Master inicializados")
            
        except Exception as e:
            logger.error(f"Error inicializando componentes de Master: {e}")


# Instancia global
_cluster_initializer: Optional[ClusterInitializer] = None


async def initialize_cluster() -> ClusterInitializer:
    """Función de conveniencia para inicializar el cluster"""
    global _cluster_initializer
    
    if _cluster_initializer is None:
        _cluster_initializer = ClusterInitializer()
        await _cluster_initializer.initialize()
    
    return _cluster_initializer


async def shutdown_cluster() -> None:
    """Función de conveniencia para detener el cluster"""
    global _cluster_initializer
    
    if _cluster_initializer:
        await _cluster_initializer.shutdown()
        _cluster_initializer = None
