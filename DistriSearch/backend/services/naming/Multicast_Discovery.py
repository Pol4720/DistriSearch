"""
Servicio de descubrimiento automático de nodos mediante UDP Multicast
Implementa protocolo similar a mDNS para redes LAN
"""
import socket
import struct
import json
import asyncio
import logging
from typing import Callable, Optional, Dict
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Configuración Multicast
MULTICAST_GROUP = os.getenv("MULTICAST_GROUP", "239.255.0.1")
MULTICAST_PORT = int(os.getenv("MULTICAST_PORT", "5353"))
DISCOVERY_INTERVAL = int(os.getenv("DISCOVERY_INTERVAL", "30"))
TTL = 2


class MulticastDiscovery:
    """
    Descubrimiento automático de nodos mediante UDP Multicast
    ✅ CORREGIDO: Callbacks completamente asíncronos
    """
    
    def __init__(
        self,
        node_id: str,
        port: int,
        ip_address: str,
        on_node_discovered: Optional[Callable] = None,
        on_node_lost: Optional[Callable] = None
    ):
        self.node_id = node_id
        self.port = port
        self.ip_address = ip_address
        self.on_node_discovered = on_node_discovered
        self.on_node_lost = on_node_lost
        
        self.discovered_nodes: Dict[str, Dict] = {}
        self.discovery_timeout = DISCOVERY_INTERVAL * 3
        
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, TTL)
        self.send_socket.setblocking(False)  
        
        self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass
        
        try:
            self.recv_socket.bind(('', MULTICAST_PORT))
        except OSError as e:
            logger.warning(f"Puerto {MULTICAST_PORT} en uso: {e}")
            self.recv_socket.bind(('', 0))
            logger.info(f"Usando puerto alternativo: {self.recv_socket.getsockname()[1]}")
        
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        self.recv_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        self.recv_socket.setblocking(False)  # ✅ Non-blocking
        
        self.running = False
        logger.info(f"🔧 MulticastDiscovery inicializado para nodo {node_id}")
    
    async def start(self):
        """Inicia el servicio de descubrimiento"""
        self.running = True
        
        await self._send_announce()
        
        tasks = [
            asyncio.create_task(self._announce_loop(), name="announce_loop"),
            asyncio.create_task(self._listen_loop(), name="listen_loop"),
            asyncio.create_task(self._timeout_check_loop(), name="timeout_check")
        ]
        
        logger.info(f"✅ Multicast discovery iniciado en {MULTICAST_GROUP}:{MULTICAST_PORT}")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Multicast discovery detenido")
    
    async def _announce_loop(self):
        """Anuncia presencia periódicamente"""
        while self.running:
            try:
                await self._send_announce()
                await asyncio.sleep(DISCOVERY_INTERVAL)
            except Exception as e:
                logger.error(f"Error en announce loop: {e}")
                await asyncio.sleep(5)
    
    async def _send_announce(self):
        """✅ CORREGIDO: Envío asíncrono con sendto"""
        try:
            message = json.dumps({
                "type": "node_announce",
                "node_id": self.node_id,
                "ip_address": self.ip_address,
                "port": self.port,
                "timestamp": datetime.utcnow().isoformat(),
                "protocol_version": "1.0"
            }).encode('utf-8')
            
            # ✅ Usar loop.sock_sendto para operación asíncrona
            loop = asyncio.get_event_loop()
            await loop.sock_sendto(
                self.send_socket,
                message,
                (MULTICAST_GROUP, MULTICAST_PORT)
            )
            
            logger.debug(f"📡 Anuncio enviado: {self.node_id}")
            
        except Exception as e:
            logger.error(f"Error enviando anuncio: {e}")
    
    async def _listen_loop(self):
        """✅ CORREGIDO: Lectura completamente asíncrona"""
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # ✅ sock_recv con timeout implementado correctamente
                data = await asyncio.wait_for(
                    loop.sock_recv(self.recv_socket, 4096),
                    timeout=1.0
                )
                
                if data:
                    # ✅ Procesar mensaje de forma asíncrona
                    await self._process_message(data)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error en listen loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, data: bytes):
        """✅ CORREGIDO: Procesamiento completamente asíncrono"""
        try:
            message = json.loads(data.decode('utf-8'))
            msg_type = message.get('type')
            
            if msg_type == 'node_announce':
                await self._handle_announce(message)
            
            elif msg_type == 'node_query':
                await self._handle_query(message)
            
            elif msg_type == 'node_response':
                await self._handle_response(message)
                
        except json.JSONDecodeError:
            logger.warning("Mensaje multicast inválido recibido")
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
    
    async def _handle_announce(self, message: Dict):
        """✅ CORREGIDO: Callback asíncrono"""
        discovered_node_id = message.get('node_id')
        
        if discovered_node_id == self.node_id:
            return
        
        is_new_node = discovered_node_id not in self.discovered_nodes
        
        self.discovered_nodes[discovered_node_id] = {
            "node_id": discovered_node_id,
            "ip_address": message.get('ip_address'),
            "port": message.get('port'),
            "last_seen": datetime.utcnow(),
            "first_seen": self.discovered_nodes.get(discovered_node_id, {}).get(
                "first_seen", 
                datetime.utcnow()
            )
        }
        
        if is_new_node:
            logger.info(f"🔍 Nuevo nodo descubierto: {discovered_node_id} ({message.get('ip_address')}:{message.get('port')})")
            
            if self.on_node_discovered:
                try:
                    # ✅ Verificar si el callback es asíncrono
                    if asyncio.iscoroutinefunction(self.on_node_discovered):
                        await self.on_node_discovered(self.discovered_nodes[discovered_node_id])
                    else:
                        # Si es síncrono, ejecutar en executor para no bloquear
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            self.on_node_discovered,
                            self.discovered_nodes[discovered_node_id]
                        )
                except Exception as e:
                    logger.error(f"Error en callback on_node_discovered: {e}")
        else:
            logger.debug(f"♻️ Heartbeat de nodo: {discovered_node_id}")
    
    async def _handle_query(self, message: Dict):
        """✅ CORREGIDO: Respuesta asíncrona"""
        response = json.dumps({
            "type": "node_response",
            "node_id": self.node_id,
            "ip_address": self.ip_address,
            "port": self.port,
            "timestamp": datetime.utcnow().isoformat()
        }).encode('utf-8')
        
        # ✅ Envío asíncrono
        loop = asyncio.get_event_loop()
        await loop.sock_sendto(
            self.send_socket,
            response,
            (MULTICAST_GROUP, MULTICAST_PORT)
        )
        
        logger.debug(f"📤 Respuesta enviada a query")
    
    async def _handle_response(self, message: Dict):
        """Maneja respuesta a query"""
        await self._handle_announce(message)
    
    async def _timeout_check_loop(self):
        """✅ CORREGIDO: Verificación asíncrona de timeouts"""
        while self.running:
            try:
                now = datetime.utcnow()
                lost_nodes = []
                
                for node_id, info in list(self.discovered_nodes.items()):
                    time_since_last_seen = (now - info['last_seen']).total_seconds()
                    
                    if time_since_last_seen > self.discovery_timeout:
                        lost_nodes.append(node_id)
                        logger.warning(f"⚠️ Nodo perdido (timeout): {node_id}")
                        
                        if self.on_node_lost:
                            try:
                                if asyncio.iscoroutinefunction(self.on_node_lost):
                                    await self.on_node_lost(info)
                                else:
                                    loop = asyncio.get_event_loop()
                                    await loop.run_in_executor(None, self.on_node_lost, info)
                            except Exception as e:
                                logger.error(f"Error en callback on_node_lost: {e}")
                        
                        del self.discovered_nodes[node_id]
                
                await asyncio.sleep(DISCOVERY_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error en timeout check: {e}")
                await asyncio.sleep(5)
    
    async def query_nodes(self):
        """✅ CORREGIDO: Query asíncrono"""
        try:
            message = json.dumps({
                "type": "node_query",
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat()
            }).encode('utf-8')
            
            # ✅ Envío asíncrono
            loop = asyncio.get_event_loop()
            await loop.sock_sendto(
                self.send_socket,
                message,
                (MULTICAST_GROUP, MULTICAST_PORT)
            )
            
            logger.info(f"📡 Query enviado para descubrir nodos")
            
        except Exception as e:
            logger.error(f"Error enviando query: {e}")
    
    def get_discovered_nodes(self) -> Dict[str, Dict]:
        """Retorna todos los nodos descubiertos"""
        return self.discovered_nodes.copy()
    
    def stop(self):
        """Detiene el servicio"""
        self.running = False
        
        try:
            goodbye = json.dumps({
                "type": "node_goodbye",
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat()
            }).encode('utf-8')
            
            # ✅ Envío síncrono final (antes de cerrar)
            self.send_socket.sendto(goodbye, (MULTICAST_GROUP, MULTICAST_PORT))
        except:
            pass
        
        self.send_socket.close()
        self.recv_socket.close()
        logger.info("Multicast discovery detenido")


# Singleton
_multicast_service = None

async def get_multicast_service(
    node_id: str,
    port: int,
    ip_address: str,
    on_node_discovered: Optional[Callable] = None,
    on_node_lost: Optional[Callable] = None
) -> MulticastDiscovery:
    """Obtiene/crea servicio de multicast discovery"""
    global _multicast_service
    
    if _multicast_service is None:
        _multicast_service = MulticastDiscovery(
            node_id, 
            port, 
            ip_address, 
            on_node_discovered, 
            on_node_lost
        )
    
    return _multicast_service