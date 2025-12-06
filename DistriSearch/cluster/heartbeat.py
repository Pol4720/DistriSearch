"""
DistriSearch Cluster - Sistema de Heartbeat

Monitoreo de nodos mediante heartbeats UDP.
Detecta nodos caídos e inicia elección de líder si es necesario.
"""
import asyncio
import socket
import json
import logging
from typing import Dict, Callable, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field

# Importar modelos centralizados
from core.models import NodeStatus, MessageType, ClusterMessage

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatState:
    """Estado del heartbeat de un nodo"""
    node_id: str
    last_seen: datetime = field(default_factory=datetime.utcnow)
    missed_beats: int = 0
    status: NodeStatus = NodeStatus.UNKNOWN
    
    def update(self) -> None:
        """Actualiza timestamp del último heartbeat"""
        self.last_seen = datetime.utcnow()
        self.missed_beats = 0
        self.status = NodeStatus.ONLINE
    
    def check_timeout(self, timeout_seconds: int) -> bool:
        """Verifica si el nodo ha expirado"""
        elapsed = (datetime.utcnow() - self.last_seen).total_seconds()
        if elapsed > timeout_seconds:
            self.missed_beats += 1
            self.status = NodeStatus.OFFLINE
            return True
        return False


class HeartbeatService:
    """
    Servicio de heartbeat para monitoreo de nodos.
    
    Funcionalidades:
    - Envía PINGs periódicos a todos los peers
    - Recibe PONGs y actualiza estado
    - Detecta nodos caídos
    - Notifica cuando el Master cae (para iniciar elección)
    """
    
    def __init__(
        self,
        node_id: str,
        port: int = 5000,
        heartbeat_interval: int = 5,
        heartbeat_timeout: int = 15,
        on_node_down: Optional[Callable[[str], None]] = None,
        on_master_down: Optional[Callable[[], None]] = None
    ):
        """
        Args:
            node_id: ID de este nodo
            port: Puerto UDP para heartbeats
            heartbeat_interval: Segundos entre heartbeats
            heartbeat_timeout: Segundos para considerar un nodo caído
            on_node_down: Callback cuando un nodo cae
            on_master_down: Callback cuando el master cae
        """
        self.node_id = node_id
        self.port = port
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        
        self._on_node_down = on_node_down
        self._on_master_down = on_master_down
        
        # Estado de peers
        self._peers: Dict[str, HeartbeatState] = {}
        self._peer_addresses: Dict[str, tuple] = {}  # node_id -> (ip, port)
        
        # Master actual
        self._current_master: Optional[str] = None
        
        # Control de ejecución
        self._running = False
        self._socket: Optional[socket.socket] = None
        self._tasks: list = []
    
    def add_peer(self, node_id: str, ip_address: str, port: int) -> None:
        """Añade un peer para monitorear"""
        self._peers[node_id] = HeartbeatState(node_id=node_id)
        self._peer_addresses[node_id] = (ip_address, port)
        logger.info(f"Peer añadido para heartbeat: {node_id} @ {ip_address}:{port}")
    
    def remove_peer(self, node_id: str) -> None:
        """Elimina un peer del monitoreo"""
        self._peers.pop(node_id, None)
        self._peer_addresses.pop(node_id, None)
    
    def set_master(self, master_id: str) -> None:
        """Establece el master actual"""
        self._current_master = master_id
        logger.info(f"Master establecido: {master_id}")
    
    async def start(self) -> None:
        """Inicia el servicio de heartbeat"""
        if self._running:
            return
        
        self._running = True
        
        # Crear socket UDP
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind(('0.0.0.0', self.port))
        
        logger.info(f"Heartbeat iniciado en puerto UDP {self.port}")
        
        # Iniciar tareas
        loop = asyncio.get_event_loop()
        self._tasks = [
            loop.create_task(self._send_heartbeats()),
            loop.create_task(self._receive_heartbeats()),
            loop.create_task(self._check_timeouts())
        ]
    
    async def stop(self) -> None:
        """Detiene el servicio de heartbeat"""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if self._socket:
            self._socket.close()
            self._socket = None
        
        logger.info("Heartbeat detenido")
    
    async def _send_heartbeats(self) -> None:
        """Envía PINGs periódicos a todos los peers"""
        while self._running:
            try:
                message = ClusterMessage(
                    type=MessageType.PING,
                    sender_id=self.node_id,
                    payload={"timestamp": datetime.utcnow().isoformat()}
                )
                data = json.dumps(message.to_dict()).encode('utf-8')
                
                for node_id, (ip, port) in self._peer_addresses.items():
                    try:
                        self._socket.sendto(data, (ip, port))
                    except Exception as e:
                        logger.debug(f"Error enviando heartbeat a {node_id}: {e}")
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en envío de heartbeats: {e}")
                await asyncio.sleep(1)
    
    async def _receive_heartbeats(self) -> None:
        """Recibe y procesa heartbeats de peers"""
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(self._socket, 1024)
                message = ClusterMessage.from_dict(json.loads(data.decode('utf-8')))
                
                await self._handle_message(message, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error recibiendo heartbeat: {e}")
                await asyncio.sleep(0.1)
    
    async def _handle_message(self, message: ClusterMessage, addr: tuple) -> None:
        """Procesa un mensaje de heartbeat"""
        sender = message.sender_id
        
        if message.type == MessageType.PING:
            # Responder con PONG
            response = ClusterMessage(
                type=MessageType.PONG,
                sender_id=self.node_id,
                payload={"in_reply_to": sender}
            )
            data = json.dumps(response.to_dict()).encode('utf-8')
            self._socket.sendto(data, addr)
            
            # Actualizar estado del peer
            if sender in self._peers:
                self._peers[sender].update()
        
        elif message.type == MessageType.PONG:
            # Actualizar estado del peer
            if sender in self._peers:
                self._peers[sender].update()
                logger.debug(f"PONG recibido de {sender}")
    
    async def _check_timeouts(self) -> None:
        """Verifica timeouts de peers periódicamente"""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                for node_id, state in list(self._peers.items()):
                    if state.check_timeout(self.heartbeat_timeout):
                        logger.warning(f"Nodo {node_id} timeout (missed: {state.missed_beats})")
                        
                        # Primer timeout
                        if state.missed_beats == 1:
                            # Notificar nodo caído
                            if self._on_node_down:
                                self._on_node_down(node_id)
                            
                            # Si es el master, iniciar elección
                            if node_id == self._current_master:
                                logger.warning("¡Master caído! Iniciando elección...")
                                if self._on_master_down:
                                    self._on_master_down()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error verificando timeouts: {e}")
    
    def get_peer_status(self, node_id: str) -> Optional[NodeStatus]:
        """Obtiene estado de un peer"""
        state = self._peers.get(node_id)
        return state.status if state else None
    
    def get_online_peers(self) -> Set[str]:
        """Retorna IDs de peers online"""
        return {
            node_id for node_id, state in self._peers.items()
            if state.status == NodeStatus.ONLINE
        }
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del servicio"""
        return {
            "node_id": self.node_id,
            "port": self.port,
            "interval": self.heartbeat_interval,
            "timeout": self.heartbeat_timeout,
            "current_master": self._current_master,
            "peers": {
                node_id: {
                    "status": state.status.value,
                    "last_seen": state.last_seen.isoformat(),
                    "missed_beats": state.missed_beats
                }
                for node_id, state in self._peers.items()
            }
        }
