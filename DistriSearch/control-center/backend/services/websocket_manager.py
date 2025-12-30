"""
WebSocket Manager - Gestión de conexiones WebSocket
"""

from fastapi import WebSocket
from typing import List, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Gestiona las conexiones WebSocket para actualizaciones en tiempo real.
    """
    
    def __init__(self):
        """Inicializa el manager."""
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Acepta una nueva conexión WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Nueva conexión WebSocket. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Elimina una conexión WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Conexión WebSocket cerrada. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Envía un mensaje a todas las conexiones activas.
        
        Args:
            message: Mensaje a enviar
        """
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error enviando mensaje: {e}")
                disconnected.append(connection)
        
        # Limpiar conexiones cerradas
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_to_client(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Envía un mensaje a un cliente específico.
        
        Args:
            websocket: Conexión del cliente
            message: Mensaje a enviar
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Error enviando mensaje a cliente: {e}")
            self.disconnect(websocket)
    
    @property
    def connection_count(self) -> int:
        """Retorna el número de conexiones activas."""
        return len(self.active_connections)
