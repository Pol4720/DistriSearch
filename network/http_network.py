"""
Implementación de red usando HTTP/REST.
Para comunicación real entre nodos distribuidos.
"""
import asyncio
import aiohttp
from typing import Dict, Any, Optional, Set
from network.network_interface import NetworkInterface
import logging

logger = logging.getLogger(__name__)


class HTTPNetwork(NetworkInterface):
    """
    Red HTTP real para comunicación entre nodos distribuidos.
    Usa aiohttp para requests asíncronos.
    """
    
    def __init__(
        self,
        node_id: int,
        host: str = "localhost",
        port: int = 8000,
        node_addresses: Dict[int, tuple] = None
    ):
        """
        Inicializa red HTTP.
        
        Args:
            node_id: ID del nodo
            host: Host donde escucha este nodo
            port: Puerto donde escucha este nodo
            node_addresses: Diccionario {node_id: (host, port)}
        """
        super().__init__(node_id)
        
        self.host = host
        self.port = port
        self.node_addresses = node_addresses or {}
        
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Inicia el cliente HTTP."""
        if self._running:
            return
        
        # Crear sesión HTTP
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        
        self._running = True
        self.logger.info(
            f"Nodo {self.node_id}: Red HTTP iniciada "
            f"({self.host}:{self.port})"
        )
    
    async def stop(self):
        """Detiene el cliente HTTP."""
        if not self._running:
            return
        
        self._running = False
        
        # Cerrar sesión
        if self._session:
            await self._session.close()
            self._session = None
        
        self.logger.info(f"Nodo {self.node_id}: Red HTTP detenida")
    
    def is_running(self) -> bool:
        """Verifica si está corriendo."""
        return self._running
    
    def register_node(self, node_id: int, host: str, port: int):
        """
        Registra la dirección de un nodo.
        
        Args:
            node_id: ID del nodo
            host: Host del nodo
            port: Puerto del nodo
        """
        self.node_addresses[node_id] = (host, port)
        self.logger.debug(f"Nodo {node_id} registrado: {host}:{port}")
    
    def get_node_url(self, node_id: int) -> Optional[str]:
        """
        Obtiene la URL base de un nodo.
        
        Args:
            node_id: ID del nodo
            
        Returns:
            URL base (ej: "http://localhost:8001") o None
        """
        if node_id not in self.node_addresses:
            return None
        
        host, port = self.node_addresses[node_id]
        return f"http://{host}:{port}"
    
    async def send_message(
        self,
        sender_id: int,
        receiver_id: int,
        message: Dict[str, Any],
        timeout: float = 5.0
    ) -> Optional[Dict]:
        """
        Envía mensaje HTTP a otro nodo.
        
        Args:
            sender_id: ID del emisor
            receiver_id: ID del receptor
            message: Mensaje a enviar
            timeout: Timeout en segundos
            
        Returns:
            Respuesta JSON o None si falla
        """
        if not self._running or not self._session:
            self.logger.warning("Red HTTP no está corriendo")
            return None
        
        # Obtener URL del receptor
        url = self.get_node_url(receiver_id)
        if not url:
            self.logger.warning(
                f"No se conoce dirección del nodo {receiver_id}"
            )
            return None
        
        # Endpoint para mensajes
        endpoint = f"{url}/message"
        
        try:
            # Log
            self.log_send(sender_id, receiver_id, message.get("type", "unknown"))
            
            # Enviar POST request
            async with self._session.post(
                endpoint,
                json=message,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    self.logger.warning(
                        f"Nodo {receiver_id} retornó status {response.status}"
                    )
                    return None
                    
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Timeout enviando mensaje a nodo {receiver_id}"
            )
            return None
            
        except aiohttp.ClientError as e:
            self.logger.error(
                f"Error de cliente HTTP a nodo {receiver_id}: {e}"
            )
            return None
            
        except Exception as e:
            self.logger.error(
                f"Error inesperado enviando a nodo {receiver_id}: {e}"
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
            if receiver_id != sender_id:
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
    
    async def send_to_endpoint(
        self,
        node_id: int,
        endpoint: str,
        method: str = "GET",
        data: Dict = None,
        timeout: float = 5.0
    ) -> Optional[Dict]:
        """
        Envía request a un endpoint específico.
        
        Args:
            node_id: ID del nodo
            endpoint: Endpoint (ej: "/search")
            method: Método HTTP (GET, POST, etc.)
            data: Datos a enviar (para POST)
            timeout: Timeout en segundos
            
        Returns:
            Respuesta JSON o None
        """
        if not self._running or not self._session:
            return None
        
        url = self.get_node_url(node_id)
        if not url:
            return None
        
        full_url = f"{url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                async with self._session.get(
                    full_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    
            elif method.upper() == "POST":
                async with self._session.post(
                    full_url,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error en {method} {full_url}: {e}")
            return None
