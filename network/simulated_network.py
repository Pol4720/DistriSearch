"""
Red simulada para testing y desarrollo.
Simula latencia, pérdida de paquetes y particiones de red.
"""
import asyncio
import random
from typing import Dict, Any, Optional, Set, Callable
from network.network_interface import NetworkInterface
import logging

logger = logging.getLogger(__name__)


class SimulatedNetwork(NetworkInterface):
    """
    Red simulada en memoria para testing.
    Permite simular condiciones de red adversas.
    """
    
    # Registro global de nodos (compartido entre instancias)
    _nodes: Dict[int, 'SimulatedNetwork'] = {}
    
    def __init__(
        self,
        node_id: int,
        latency_ms: float = 10.0,
        packet_loss: float = 0.0,
        max_latency_ms: float = 100.0
    ):
        """
        Inicializa red simulada.
        
        Args:
            node_id: ID del nodo
            latency_ms: Latencia promedio en milisegundos
            packet_loss: Probabilidad de pérdida de paquetes (0.0-1.0)
            max_latency_ms: Latencia máxima en milisegundos
        """
        super().__init__(node_id)
        
        self.latency_ms = latency_ms
        self.packet_loss = packet_loss
        self.max_latency_ms = max_latency_ms
        
        # Handler para mensajes entrantes
        self.message_handler: Optional[Callable] = None
        
        # Particiones de red (conjunto de nodos inalcanzables)
        self.partitioned_from: Set[int] = set()
        
        self._running = False
        
        # Registrar este nodo
        SimulatedNetwork._nodes[node_id] = self
    
    async def start(self):
        """Inicia el servicio de red."""
        self._running = True
        self.logger.info(f"Nodo {self.node_id}: Red simulada iniciada")
    
    async def stop(self):
        """Detiene el servicio de red."""
        self._running = False
        # Desregistrar
        if self.node_id in SimulatedNetwork._nodes:
            del SimulatedNetwork._nodes[self.node_id]
        self.logger.info(f"Nodo {self.node_id}: Red simulada detenida")
    
    def is_running(self) -> bool:
        """Verifica si está corriendo."""
        return self._running
    
    async def register_node(self, node_id: int, node_instance):
        """
        Registra un nodo en la red (compatibilidad con API antigua).
        
        Args:
            node_id: ID del nodo
            node_instance: Instancia del nodo
        """
        # El nodo ya se auto-registra en __init__
        # Este método existe solo para compatibilidad
        self.logger.debug(f"Nodo {node_id} ya registrado en red simulada")
    
    def set_message_handler(self, handler: Callable):
        """
        Configura el handler para mensajes entrantes.
        
        Args:
            handler: Función async que procesa mensajes
        """
        self.message_handler = handler
    
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
            sender_id: ID del emisor
            receiver_id: ID del receptor
            message: Mensaje a enviar
            timeout: Timeout en segundos
            
        Returns:
            Respuesta o None si falla
        """
        if not self._running:
            self.logger.warning(f"Red no está corriendo (nodo {self.node_id})")
            return None
        
        # Verificar si hay partición de red
        if receiver_id in self.partitioned_from:
            self.logger.debug(
                f"{sender_id} → {receiver_id}: BLOQUEADO (partición)"
            )
            return None
        
        # Simular pérdida de paquetes
        if random.random() < self.packet_loss:
            self.logger.debug(
                f"{sender_id} → {receiver_id}: PERDIDO ({message.get('type')})"
            )
            return None
        
        # Verificar que el receptor existe
        if receiver_id not in SimulatedNetwork._nodes:
            self.logger.debug(
                f"{sender_id} → {receiver_id}: Nodo no existe"
            )
            return None
        
        receiver = SimulatedNetwork._nodes[receiver_id]
        
        if not receiver.is_running():
            self.logger.debug(
                f"{sender_id} → {receiver_id}: Nodo no está corriendo"
            )
            return None
        
        # Simular latencia variable
        latency = random.uniform(
            self.latency_ms / 1000,
            self.max_latency_ms / 1000
        )
        await asyncio.sleep(latency)
        
        # Log
        self.log_send(sender_id, receiver_id, message.get("type", "unknown"))
        
        try:
            # Enviar mensaje al receptor
            if receiver.message_handler:
                response = await asyncio.wait_for(
                    receiver.message_handler(message),
                    timeout=timeout
                )
                return response
            else:
                self.logger.warning(
                    f"Nodo {receiver_id} no tiene message_handler"
                )
                return None
                
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Timeout enviando mensaje a nodo {receiver_id}"
            )
            return None
        except Exception as e:
            self.logger.error(
                f"Error enviando mensaje a nodo {receiver_id}: {e}"
            )
            return None
    
    async def broadcast(
        self,
        sender_id: int,
        receivers: Set[int],
        message: Dict[str, Any],
        timeout: float = 5.0
    ) -> Dict[int, Optional[Dict]]:
        """
        Envía mensaje a múltiples nodos en paralelo.
        
        Args:
            sender_id: ID del emisor
            receivers: Conjunto de receptores
            message: Mensaje a enviar
            timeout: Timeout en segundos
            
        Returns:
            Diccionario {node_id: respuesta}
        """
        tasks = []
        node_ids = []
        
        for receiver_id in receivers:
            if receiver_id != sender_id:  # No enviarse a sí mismo
                tasks.append(
                    self.send_message(sender_id, receiver_id, message, timeout)
                )
                node_ids.append(receiver_id)
        
        # Ejecutar en paralelo
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Mapear resultados
        result = {}
        for node_id, response in zip(node_ids, responses):
            if isinstance(response, Exception):
                result[node_id] = None
            else:
                result[node_id] = response
        
        return result
    
    def partition_from(self, node_ids: Set[int]):
        """
        Simula partición de red desde estos nodos.
        
        Args:
            node_ids: Nodos de los que particionar
        """
        self.partitioned_from = node_ids
        self.logger.info(
            f"Nodo {self.node_id}: Particionado de {node_ids}"
        )
    
    def heal_partition(self):
        """Restaura conectividad de red."""
        self.partitioned_from.clear()
        self.logger.info(
            f"Nodo {self.node_id}: Partición restaurada"
        )
    
    def set_latency(self, latency_ms: float):
        """Configura la latencia promedio."""
        self.latency_ms = latency_ms
    
    def set_packet_loss(self, loss_rate: float):
        """Configura la tasa de pérdida de paquetes."""
        self.packet_loss = max(0.0, min(1.0, loss_rate))
    
    @classmethod
    def get_node(cls, node_id: int) -> Optional['SimulatedNetwork']:
        """Obtiene instancia de un nodo."""
        return cls._nodes.get(node_id)
    
    @classmethod
    def clear_all(cls):
        """Limpia todos los nodos registrados."""
        cls._nodes.clear()
