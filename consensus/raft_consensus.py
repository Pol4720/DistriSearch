"""
Orquestador principal del consenso Raft.
Combina elección y replicación para implementar Raft completo.
"""
import asyncio
import logging
from typing import Set, Dict, Optional
from consensus.raft_state import NodeState, RaftMessage, RaftState, RaftConfig
from consensus.raft_election import RaftElection
from consensus.raft_replication import RaftReplication

logger = logging.getLogger(__name__)


class RaftConsensus:
    """Orquestador principal del consenso Raft."""
    
    def __init__(
        self,
        node_id: int,
        all_node_ids: Set[int],
        network,
        config: RaftConfig = None
    ):
        """
        Inicializa el consenso Raft.
        
        Args:
            node_id: ID de este nodo
            all_node_ids: Conjunto de IDs de todos los nodos
            network: Interfaz de red
            config: Configuración opcional
        """
        self.node_id = node_id
        self.all_nodes = all_node_ids
        self.network = network
        self.config = config or RaftConfig()
        
        # Estado compartido
        self.state = RaftState(
            current_term=0,
            voted_for=None,
            log=[],
            commit_index=-1,
            last_applied=-1
        )
        
        # Componentes
        self.election = RaftElection(
            node_id=node_id,
            all_node_ids=all_node_ids,
            state=self.state,
            network=network,
            config=self.config
        )
        
        self.replication = RaftReplication(
            node_id=node_id,
            all_node_ids=all_node_ids,
            state=self.state,
            network=network,
            config=self.config
        )
        
        # Control
        self._running = False
        self._current_leader: Optional[int] = None
    
    @property
    def current_leader(self) -> Optional[int]:
        """Retorna ID del líder actual."""
        if self.state.state == NodeState.LEADER:
            return self.node_id
        return self._current_leader
    
    @current_leader.setter
    def current_leader(self, leader_id: Optional[int]):
        """Establece el líder actual."""
        self._current_leader = leader_id
    
    async def start(self):
        """Inicia el consenso Raft."""
        if self._running:
            logger.warning(f"Nodo {self.node_id}: Raft ya está corriendo")
            return
        
        self._running = True
        logger.info(f"Nodo {self.node_id}: Iniciando consenso Raft")
        
        # Todos empiezan como FOLLOWER
        self.state.become_follower(0, None)
        
        # Iniciar election timer
        await self.election.start_election_timer()
        
        logger.info(
            f"Nodo {self.node_id}: Raft iniciado como FOLLOWER (term 0)"
        )
    
    async def stop(self):
        """Detiene el consenso Raft."""
        if not self._running:
            return
        
        logger.info(f"Nodo {self.node_id}: Deteniendo consenso Raft")
        self._running = False
        
        # Detener timers
        await self.election.stop_election_timer()
        await self.replication.stop_heartbeat_loop()
        
        logger.info(f"Nodo {self.node_id}: Raft detenido")
    
    async def handle_message(self, message_type: str, payload: Dict) -> Optional[Dict]:
        """
        Maneja mensajes Raft entrantes.
        
        Args:
            message_type: Tipo de mensaje ("request_vote", "append_entries", etc.)
            payload: Datos del mensaje
            
        Returns:
            Respuesta (dict) o None
        """
        if not self._running:
            logger.warning(
                f"Nodo {self.node_id}: Mensaje rechazado (Raft no corriendo)"
            )
            return None
        
        # Dispatch según tipo
        if message_type == "request_vote":
            response = await self.election.handle_vote_request(payload)
            return {"type": "raft_message", "payload": response.__dict__}
        
        elif message_type == "vote_response":
            # Delegar a election (es manejado internamente)
            return None
        
        elif message_type == "append_entries":
            response = await self.replication.handle_append_entries(payload)
            return {"type": "raft_message", "payload": response.__dict__}
        
        elif message_type == "append_response":
            # Delegar a replication (es manejado internamente)
            return None
        
        else:
            logger.warning(
                f"Nodo {self.node_id}: Tipo de mensaje desconocido: "
                f"{message_type}"
            )
            return None
    
    async def replicate_command(self, command: Dict, timeout: float = 5.0) -> bool:
        """
        Replica un comando usando consenso Raft.
        
        Args:
            command: Comando a replicar (debe ser serializable)
            timeout: Timeout en segundos
            
        Returns:
            True si se replicó exitosamente, False en caso contrario
        """
        if not self._running:
            logger.error(
                f"Nodo {self.node_id}: No se puede replicar (Raft no corriendo)"
            )
            return False
        
        # Solo el líder puede replicar
        if self.state.state != NodeState.LEADER:
            logger.error(
                f"Nodo {self.node_id}: No soy líder, no puedo replicar comando"
            )
            return False
        
        # Delegar a replication
        try:
            return await asyncio.wait_for(
                self.replication.append_entry(command),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Nodo {self.node_id}: Timeout replicando comando"
            )
            return False
    
    def get_leader_id(self) -> Optional[int]:
        """Retorna el ID del líder actual (o None si no hay líder)."""
        if self.state.state == NodeState.LEADER:
            return self.node_id
        return self.state.current_leader
    
    def is_leader(self) -> bool:
        """Retorna True si este nodo es el líder."""
        return self.state.state == NodeState.LEADER
    
    def get_state(self) -> str:
        """Retorna el estado actual como string."""
        return self.state.state.value
    
    def get_term(self) -> int:
        """Retorna el term actual."""
        return self.state.current_term
    
    def get_commit_index(self) -> int:
        """Retorna el índice de la última entrada commiteada."""
        return self.state.commit_index
    
    def get_log_length(self) -> int:
        """Retorna la longitud del log."""
        return len(self.state.log)
    
    async def wait_for_leader_election(self, timeout: float = 10.0) -> Optional[int]:
        """
        Espera hasta que haya un líder electo.
        
        Args:
            timeout: Timeout en segundos
            
        Returns:
            ID del líder o None si timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            leader = self.get_leader_id()
            if leader is not None:
                return leader
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"Nodo {self.node_id}: Timeout esperando líder "
                    f"({timeout}s)"
                )
                return None
            
            await asyncio.sleep(0.1)
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del consenso."""
        return {
            "node_id": self.node_id,
            "state": self.get_state(),
            "term": self.get_term(),
            "leader_id": self.get_leader_id(),
            "commit_index": self.get_commit_index(),
            "log_length": self.get_log_length(),
            "running": self._running,
            "config": {
                "election_timeout": self.config.ELECTION_TIMEOUT_RANGE,
                "heartbeat_interval": self.config.HEARTBEAT_INTERVAL,
            }
        }
