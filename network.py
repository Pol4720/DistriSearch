"""
Abstracción de red: simulación vs HTTP real.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Configuración de red."""
    mode: str = "simulated"  # "simulated" o "http"
    latency_ms: int = 10  # Latencia simulada
    failure_rate: float = 0.0  # Tasa de fallos simulados (0.0 - 1.0)


class NetworkInterface(ABC):
    """Interfaz abstracta para comunicación entre nodos."""
    
    @abstractmethod
    async def send_message(self, dest_id: int, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Envía un mensaje a otro nodo.
        
        Args:
            dest_id: ID del nodo destino
            message: Payload del mensaje
        
        Returns:
            Respuesta del nodo (si hay), o None
        """
        pass
    
    @abstractmethod
    async def register_node(self, node_id: int, handler):
        """
        Registra un nodo en la red.
        
        Args:
            node_id: ID del nodo
            handler: Objeto manejador del nodo (debe tener método handle_message)
        """
        pass
    
    @abstractmethod
    async def unregister_node(self, node_id: int):
        """Elimina un nodo de la red."""
        pass


class SimulatedNetwork(NetworkInterface):
    """
    Red simulada: todos los nodos en un proceso, comunicación por colas.
    
    Útil para desarrollo y pruebas rápidas.
    """
    
    def __init__(self, config: NetworkConfig = None):
        self.config = config or NetworkConfig()
        
        # Mapa: node_id -> handler
        self.nodes: Dict[int, Any] = {}
        
        # Colas de mensajes: node_id -> asyncio.Queue
        self.message_queues: Dict[int, asyncio.Queue] = {}
        
        # Nodos fallidos (simulación)
        self.failed_nodes: Set[int] = set()
    
    async def send_message(self, dest_id: int, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Envía mensaje a otro nodo en la simulación."""
        
        # Simular latencia
        if self.config.latency_ms > 0:
            await asyncio.sleep(self.config.latency_ms / 1000.0)
        
        # Simular fallo de red
        if self.config.failure_rate > 0:
            import random
            if random.random() < self.config.failure_rate:
                logger.debug(f"Fallo simulado enviando a {dest_id}")
                raise ConnectionError(f"Fallo simulado de red a nodo {dest_id}")
        
        # Verificar si el nodo destino existe y está activo
        if dest_id not in self.nodes or dest_id in self.failed_nodes:
            raise ConnectionError(f"Nodo {dest_id} no disponible")
        
        handler = self.nodes[dest_id]
        
        try:
            # Llamar al manejador del nodo
            response = await handler.handle_message(message)
            return response
        except Exception as e:
            logger.error(f"Error procesando mensaje en nodo {dest_id}: {e}")
            raise
    
    async def register_node(self, node_id: int, handler):
        """Registra un nodo en la red simulada."""
        self.nodes[node_id] = handler
        self.message_queues[node_id] = asyncio.Queue()
        
        if node_id in self.failed_nodes:
            self.failed_nodes.remove(node_id)
        
        logger.debug(f"Nodo {node_id} registrado en red simulada")
    
    async def unregister_node(self, node_id: int):
        """Elimina un nodo de la red."""
        if node_id in self.nodes:
            del self.nodes[node_id]
        if node_id in self.message_queues:
            del self.message_queues[node_id]
        
        logger.debug(f"Nodo {node_id} eliminado de red simulada")
    
    def simulate_node_failure(self, node_id: int):
        """Simula fallo de un nodo."""
        self.failed_nodes.add(node_id)
        logger.info(f"Nodo {node_id} marcado como fallido")
    
    def simulate_node_recovery(self, node_id: int):
        """Simula recuperación de un nodo fallido."""
        if node_id in self.failed_nodes:
            self.failed_nodes.remove(node_id)
            logger.info(f"Nodo {node_id} recuperado")
    
    def get_active_nodes(self) -> Set[int]:
        """Retorna IDs de nodos activos (no fallidos)."""
        return set(self.nodes.keys()) - self.failed_nodes


class HttpNetwork(NetworkInterface):
    """
    Red HTTP real: cada nodo es un servidor HTTP independiente.
    """
    
    def __init__(self, config: NetworkConfig = None):
        self.config = config or NetworkConfig()
        
        # Mapa: node_id -> (host, port)
        self.node_endpoints: Dict[int, tuple] = {}
        
        # Session HTTP reutilizable
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtiene o crea sesión HTTP."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self.session
    
    async def send_message(self, dest_id: int, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Envía mensaje HTTP POST a otro nodo."""
        
        if dest_id not in self.node_endpoints:
            raise ConnectionError(f"Endpoint desconocido para nodo {dest_id}")
        
        host, port = self.node_endpoints[dest_id]
        url = f"http://{host}:{port}/route"
        
        session = await self._get_session()
        
        try:
            async with session.post(url, json=message) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Error HTTP {resp.status} desde nodo {dest_id}")
                    raise ConnectionError(f"HTTP {resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error conectando a nodo {dest_id}: {e}")
            raise ConnectionError(f"No se pudo conectar a nodo {dest_id}") from e
    
    async def register_node(self, node_id: int, handler):
        """
        Registra endpoint de un nodo.
        
        Para HTTP, el handler debe contener atributos host y port.
        """
        if hasattr(handler, 'host') and hasattr(handler, 'port'):
            self.node_endpoints[node_id] = (handler.host, handler.port)
            logger.debug(f"Nodo {node_id} registrado: {handler.host}:{handler.port}")
        else:
            raise ValueError("Handler debe tener atributos 'host' y 'port'")
    
    async def unregister_node(self, node_id: int):
        """Elimina endpoint de un nodo."""
        if node_id in self.node_endpoints:
            del self.node_endpoints[node_id]
            logger.debug(f"Nodo {node_id} eliminado de red HTTP")
    
    async def close(self):
        """Cierra la sesión HTTP."""
        if self.session and not self.session.closed:
            await self.session.close()


def create_network(mode: str = "simulated", **kwargs) -> NetworkInterface:
    """
    Factory para crear instancia de red.
    
    Args:
        mode: "simulated" o "http"
        **kwargs: Argumentos adicionales para NetworkConfig
    
    Returns:
        Instancia de NetworkInterface
    """
    config = NetworkConfig(mode=mode, **kwargs)
    
    if mode == "simulated":
        return SimulatedNetwork(config)
    elif mode == "http":
        return HttpNetwork(config)
    else:
        raise ValueError(f"Modo de red desconocido: {mode}")
