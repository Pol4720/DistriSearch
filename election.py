"""
Algoritmo de elección de líder (Bully adaptado para overlay hipercubo).
"""
import asyncio
import logging
from enum import Enum
from typing import Optional, Set, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Tipos de mensajes en el protocolo de elección."""
    ELECTION = "ELECTION"
    OK = "OK"
    COORDINATOR = "COORDINATOR"


@dataclass
class ElectionMessage:
    """Mensaje del protocolo de elección."""
    msg_type: MessageType
    sender_id: int
    election_id: int = 0  # Para distinguir diferentes elecciones


class BullyElection:
    """
    Implementación del algoritmo Bully para elección de líder.
    
    Reglas:
    - El nodo con mayor ID gana
    - Cuando un nodo detecta fallo del líder, inicia elección
    - Envía ELECTION a todos los nodos con ID mayor
    - Si recibe OK, espera que ellos se encarguen
    - Si no recibe OK en timeout, se declara coordinator
    """
    
    def __init__(self, node_id: int, all_node_ids: Set[int], 
                 send_message_func: Callable, timeout: float = 3.0):
        """
        Inicializa el módulo de elección.
        
        Args:
            node_id: ID de este nodo
            all_node_ids: Set de todos los IDs en la red
            send_message_func: Función async para enviar mensajes a otros nodos
            timeout: Timeout para esperar respuestas (segundos)
        """
        self.node_id = node_id
        self.all_node_ids = all_node_ids
        self.send_message = send_message_func
        self.timeout = timeout
        
        self.current_leader: Optional[int] = None
        self.election_in_progress = False
        self.election_id = 0
        self.received_ok = False
    
    def is_leader(self) -> bool:
        """Verifica si este nodo es el líder actual."""
        return self.current_leader == self.node_id
    
    async def start_election(self) -> int:
        """
        Inicia un proceso de elección.
        
        Returns:
            ID del nuevo líder
        """
        if self.election_in_progress:
            logger.info(f"Nodo {self.node_id}: elección ya en progreso")
            # Esperar a que termine
            for _ in range(int(self.timeout * 10)):
                await asyncio.sleep(0.1)
                if not self.election_in_progress:
                    break
            return self.current_leader
        
        self.election_in_progress = True
        self.election_id += 1
        self.received_ok = False
        
        logger.info(f"Nodo {self.node_id}: iniciando elección #{self.election_id}")
        
        # Encontrar nodos con ID mayor
        higher_nodes = {nid for nid in self.all_node_ids if nid > self.node_id}
        
        if not higher_nodes:
            # Soy el nodo con mayor ID, me declaro coordinator
            await self._become_coordinator()
            return self.node_id
        
        # Enviar ELECTION a nodos con ID mayor
        election_msg = ElectionMessage(
            msg_type=MessageType.ELECTION,
            sender_id=self.node_id,
            election_id=self.election_id
        )
        
        tasks = []
        for node_id in higher_nodes:
            tasks.append(self._send_election_message(node_id, election_msg))
        
        # Enviar mensajes en paralelo
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Esperar respuestas OK
        try:
            await asyncio.wait_for(self._wait_for_ok(), timeout=self.timeout)
        except asyncio.TimeoutError:
            pass
        
        if not self.received_ok:
            # No recibí OK, me declaro coordinator
            await self._become_coordinator()
        else:
            # Esperar a que el nodo mayor se declare coordinator
            try:
                await asyncio.wait_for(
                    self._wait_for_coordinator(), 
                    timeout=self.timeout * 2
                )
            except asyncio.TimeoutError:
                logger.warning(f"Nodo {self.node_id}: timeout esperando COORDINATOR")
                # Reintentar elección
                self.election_in_progress = False
                return await self.start_election()
        
        self.election_in_progress = False
        return self.current_leader
    
    async def handle_election_message(self, message: ElectionMessage):
        """
        Maneja un mensaje de elección recibido.
        
        Args:
            message: Mensaje recibido
        """
        if message.msg_type == MessageType.ELECTION:
            await self._handle_election(message)
        elif message.msg_type == MessageType.OK:
            await self._handle_ok(message)
        elif message.msg_type == MessageType.COORDINATOR:
            await self._handle_coordinator(message)
    
    async def _handle_election(self, message: ElectionMessage):
        """Maneja mensaje ELECTION."""
        logger.info(f"Nodo {self.node_id}: recibido ELECTION de {message.sender_id}")
        
        if message.sender_id < self.node_id:
            # Responder con OK
            ok_msg = ElectionMessage(
                msg_type=MessageType.OK,
                sender_id=self.node_id,
                election_id=message.election_id
            )
            await self._send_election_message(message.sender_id, ok_msg)
            
            # Iniciar mi propia elección si no hay una en progreso
            if not self.election_in_progress:
                asyncio.create_task(self.start_election())
    
    async def _handle_ok(self, message: ElectionMessage):
        """Maneja mensaje OK."""
        logger.info(f"Nodo {self.node_id}: recibido OK de {message.sender_id}")
        if message.election_id == self.election_id:
            self.received_ok = True
    
    async def _handle_coordinator(self, message: ElectionMessage):
        """Maneja mensaje COORDINATOR."""
        logger.info(f"Nodo {self.node_id}: nuevo líder es {message.sender_id}")
        self.current_leader = message.sender_id
        self.election_in_progress = False
    
    async def _become_coordinator(self):
        """Este nodo se convierte en coordinator."""
        logger.info(f"Nodo {self.node_id}: me declaro COORDINATOR")
        self.current_leader = self.node_id
        
        # Anunciar a todos los nodos
        coordinator_msg = ElectionMessage(
            msg_type=MessageType.COORDINATOR,
            sender_id=self.node_id,
            election_id=self.election_id
        )
        
        tasks = []
        for node_id in self.all_node_ids:
            if node_id != self.node_id:
                tasks.append(self._send_election_message(node_id, coordinator_msg))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_election_message(self, dest_id: int, message: ElectionMessage):
        """Envía un mensaje de elección a otro nodo."""
        try:
            await self.send_message(dest_id, {
                'type': 'election',
                'msg_type': message.msg_type.value,
                'sender_id': message.sender_id,
                'election_id': message.election_id
            })
        except Exception as e:
            logger.debug(f"Error enviando mensaje a {dest_id}: {e}")
    
    async def _wait_for_ok(self):
        """Espera a recibir al menos un mensaje OK."""
        while not self.received_ok:
            await asyncio.sleep(0.1)
    
    async def _wait_for_coordinator(self):
        """Espera a recibir mensaje COORDINATOR."""
        initial_leader = self.current_leader
        while self.current_leader == initial_leader:
            await asyncio.sleep(0.1)
