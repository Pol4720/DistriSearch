"""
DistriSearch Cluster - Elección de Líder (Algoritmo Bully)

Implementa el algoritmo Bully para elección de líder
cuando el Master actual falla.
"""
import asyncio
import socket
import json
import logging
from typing import Dict, Callable, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

# Importar modelos centralizados
from core.models import MessageType, ClusterMessage

logger = logging.getLogger(__name__)


class ElectionState(Enum):
    """Estados del proceso de elección"""
    IDLE = "idle"
    ELECTION_IN_PROGRESS = "election"
    WAITING_COORDINATOR = "waiting"
    IS_COORDINATOR = "coordinator"


@dataclass
class ElectionConfig:
    """Configuración del algoritmo de elección"""
    election_timeout: float = 5.0  # Tiempo espera respuesta ELECTION
    coordinator_timeout: float = 10.0  # Tiempo espera COORDINATOR


class BullyElection:
    """
    Implementación del algoritmo Bully para elección de líder.
    
    El algoritmo Bully selecciona como líder al nodo con mayor ID.
    
    Pasos:
    1. Cuando un nodo detecta que el master está caído, inicia elección
    2. Envía mensaje ELECTION a todos los nodos con ID mayor
    3. Si recibe OK, espera mensaje COORDINATOR
    4. Si no recibe OK (timeout), se proclama coordinador
    5. El coordinador envía COORDINATOR a todos
    """
    
    def __init__(
        self,
        node_id: str,
        port: int = 5001,
        on_become_master: Optional[Callable[[], None]] = None,
        on_new_master: Optional[Callable[[str], None]] = None
    ):
        """
        Args:
            node_id: ID de este nodo
            port: Puerto UDP para mensajes de elección
            on_become_master: Callback cuando este nodo se convierte en master
            on_new_master: Callback cuando hay un nuevo master
        """
        self.node_id = node_id
        self.port = port
        self.config = ElectionConfig()
        
        self._on_become_master = on_become_master
        self._on_new_master = on_new_master
        
        # Estado
        self._state = ElectionState.IDLE
        self._current_master: Optional[str] = None
        self._is_master = False
        
        # Peers conocidos: node_id -> (ip, port, can_be_master)
        self._peers: Dict[str, tuple] = {}
        
        # Control
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._election_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        # Eventos para coordinación
        self._got_ok = asyncio.Event()
        self._got_coordinator = asyncio.Event()
    
    def add_peer(
        self, 
        node_id: str, 
        ip_address: str, 
        port: int,
        can_be_master: bool = True
    ) -> None:
        """Añade un peer para elecciones"""
        self._peers[node_id] = (ip_address, port, can_be_master)
    
    def remove_peer(self, node_id: str) -> None:
        """Elimina un peer"""
        self._peers.pop(node_id, None)
    
    @property
    def is_master(self) -> bool:
        """Retorna si este nodo es el master actual"""
        return self._is_master
    
    @property
    def current_master(self) -> Optional[str]:
        """Retorna ID del master actual"""
        return self._current_master
    
    async def start(self) -> None:
        """Inicia el servicio de elección"""
        if self._running:
            return
        
        self._running = True
        
        # Socket UDP
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind(('0.0.0.0', self.port))
        
        logger.info(f"Servicio de elección iniciado en puerto {self.port}")
        
        # Tarea receptora
        loop = asyncio.get_event_loop()
        self._receive_task = loop.create_task(self._receive_messages())
    
    async def stop(self) -> None:
        """Detiene el servicio"""
        self._running = False
        
        if self._election_task:
            self._election_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        
        if self._socket:
            self._socket.close()
    
    async def start_election(self) -> None:
        """Inicia una elección de líder"""
        if self._state == ElectionState.ELECTION_IN_PROGRESS:
            logger.debug("Elección ya en progreso")
            return
        
        logger.info(f"Iniciando elección desde nodo {self.node_id}")
        self._state = ElectionState.ELECTION_IN_PROGRESS
        self._got_ok.clear()
        self._got_coordinator.clear()
        
        # Encontrar nodos con ID mayor
        higher_nodes = self._get_higher_nodes()
        
        if not higher_nodes:
            # Somos el nodo con mayor ID, nos proclamamos coordinador
            logger.info("No hay nodos con ID mayor, proclamándose coordinador")
            await self._become_coordinator()
            return
        
        # Enviar ELECTION a nodos mayores
        message = ClusterMessage(
            type=MessageType.ELECTION,
            sender_id=self.node_id
        )
        await self._send_to_nodes(message, higher_nodes)
        
        # Esperar respuesta OK
        try:
            await asyncio.wait_for(
                self._got_ok.wait(),
                timeout=self.config.election_timeout
            )
            
            # Recibimos OK, esperar COORDINATOR
            logger.debug("Recibido OK, esperando COORDINATOR")
            self._state = ElectionState.WAITING_COORDINATOR
            
            try:
                await asyncio.wait_for(
                    self._got_coordinator.wait(),
                    timeout=self.config.coordinator_timeout
                )
            except asyncio.TimeoutError:
                # Timeout esperando COORDINATOR, reiniciar elección
                logger.warning("Timeout esperando COORDINATOR, reiniciando elección")
                await self.start_election()
                
        except asyncio.TimeoutError:
            # Nadie respondió, nos proclamamos coordinador
            logger.info("No hubo respuesta, proclamándose coordinador")
            await self._become_coordinator()
    
    async def _become_coordinator(self) -> None:
        """Este nodo se convierte en coordinador/master"""
        self._state = ElectionState.IS_COORDINATOR
        self._is_master = True
        self._current_master = self.node_id
        
        logger.info(f"¡{self.node_id} es el nuevo MASTER!")
        
        # Notificar a todos los peers
        message = ClusterMessage(
            type=MessageType.COORDINATOR,
            sender_id=self.node_id,
            payload={"new_master": self.node_id}
        )
        await self._send_to_all(message)
        
        # Callback
        if self._on_become_master:
            self._on_become_master()
    
    async def _receive_messages(self) -> None:
        """Recibe y procesa mensajes de elección"""
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(self._socket, 1024)
                message = ClusterMessage.from_dict(json.loads(data.decode('utf-8')))
                
                await self._handle_message(message, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error recibiendo mensaje de elección: {e}")
                await asyncio.sleep(0.1)
    
    async def _handle_message(self, message: ClusterMessage, addr: tuple) -> None:
        """Procesa un mensaje de elección"""
        sender = message.sender_id
        
        if message.type == MessageType.ELECTION:
            # Recibimos ELECTION de un nodo menor
            logger.debug(f"Recibido ELECTION de {sender}")
            
            # Responder OK si tenemos ID mayor
            if self.node_id > sender:
                response = ClusterMessage(
                    type=MessageType.ELECTION_OK,
                    sender_id=self.node_id
                )
                data = json.dumps(response.to_dict()).encode('utf-8')
                self._socket.sendto(data, addr)
                
                # Iniciar nuestra propia elección
                if self._state == ElectionState.IDLE:
                    asyncio.create_task(self.start_election())
        
        elif message.type == MessageType.ELECTION_OK:
            # Recibimos OK, alguien con ID mayor está vivo
            logger.debug(f"Recibido ELECTION_OK de {sender}")
            self._got_ok.set()
        
        elif message.type == MessageType.COORDINATOR:
            # Nuevo coordinador anunciado
            new_master = message.payload.get("new_master", sender)
            logger.info(f"Nuevo MASTER anunciado: {new_master}")
            
            self._current_master = new_master
            self._is_master = (new_master == self.node_id)
            self._state = ElectionState.IDLE
            self._got_coordinator.set()
            
            # Callback
            if self._on_new_master and not self._is_master:
                self._on_new_master(new_master)
    
    def _get_higher_nodes(self) -> List[str]:
        """Retorna IDs de nodos con ID mayor que pueden ser master"""
        return [
            node_id for node_id, (_, _, can_be_master) in self._peers.items()
            if node_id > self.node_id and can_be_master
        ]
    
    async def _send_to_nodes(self, message: ClusterMessage, node_ids: List[str]) -> None:
        """Envía mensaje a nodos específicos"""
        data = json.dumps(message.to_dict()).encode('utf-8')
        
        for node_id in node_ids:
            if node_id in self._peers:
                ip, port, _ = self._peers[node_id]
                try:
                    self._socket.sendto(data, (ip, port))
                except Exception as e:
                    logger.debug(f"Error enviando a {node_id}: {e}")
    
    async def _send_to_all(self, message: ClusterMessage) -> None:
        """Envía mensaje a todos los peers"""
        data = json.dumps(message.to_dict()).encode('utf-8')
        
        for node_id, (ip, port, _) in self._peers.items():
            try:
                self._socket.sendto(data, (ip, port))
            except Exception as e:
                logger.debug(f"Error enviando a {node_id}: {e}")
    
    def set_initial_master(self, master_id: str) -> None:
        """Establece el master inicial conocido"""
        self._current_master = master_id
        self._is_master = (master_id == self.node_id)
        self._state = ElectionState.IS_COORDINATOR if self._is_master else ElectionState.IDLE
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del servicio"""
        return {
            "node_id": self.node_id,
            "state": self._state.value,
            "is_master": self._is_master,
            "current_master": self._current_master,
            "peers_count": len(self._peers),
            "higher_nodes": self._get_higher_nodes()
        }
