"""
Interfaz abstracta para comunicación de red.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)


class NetworkInterface(ABC):
    """Interfaz abstracta para comunicación entre nodos."""
    
    def __init__(self, node_id: int):
        """
        Inicializa la interfaz de red.
        
        Args:
            node_id: ID del nodo local
        """
        self.node_id = node_id
        self.logger = logging.getLogger(f"{__name__}.Node{node_id}")
    
    @abstractmethod
    async def send_message(
        self,
        sender_id: int,
        receiver_id: int,
        message: Dict[str, Any],
        timeout: float = 5.0
    ) -> Optional[Dict]:
        """
        Envía un mensaje a otro nodo.
        
        Args:
            sender_id: ID del nodo emisor
            receiver_id: ID del nodo receptor
            message: Diccionario con el mensaje
            timeout: Timeout en segundos
            
        Returns:
            Respuesta del nodo receptor o None si falla
        """
        pass
    
    @abstractmethod
    async def broadcast(
        self,
        sender_id: int,
        receivers: Set[int],
        message: Dict[str, Any],
        timeout: float = 5.0
    ) -> Dict[int, Optional[Dict]]:
        """
        Envía un mensaje a múltiples nodos.
        
        Args:
            sender_id: ID del nodo emisor
            receivers: Conjunto de IDs de nodos receptores
            message: Diccionario con el mensaje
            timeout: Timeout en segundos
            
        Returns:
            Diccionario {node_id: respuesta} para cada receptor
        """
        pass
    
    @abstractmethod
    async def start(self):
        """Inicia el servicio de red."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Detiene el servicio de red."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Verifica si el servicio está corriendo."""
        pass
    
    def log_send(self, sender: int, receiver: int, msg_type: str):
        """Log de mensaje enviado."""
        self.logger.debug(f"{sender} → {receiver}: {msg_type}")
    
    def log_receive(self, sender: int, receiver: int, msg_type: str):
        """Log de mensaje recibido."""
        self.logger.debug(f"{receiver} ← {sender}: {msg_type}")
