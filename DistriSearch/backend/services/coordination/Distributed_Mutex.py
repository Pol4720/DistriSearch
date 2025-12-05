"""
Sistema de Coordinación Distribuida para DistriSearch
- Exclusión mutua distribuida
"""
import time
import asyncio
import logging
from typing import Dict, List
from collections import defaultdict
from pymongo import MongoClient
from .Lamport_Clock import LamportClock
import httpx
import os

logger = logging.getLogger(__name__)

class DistributedMutex:
    """
    Exclusión mutua distribuida usando algoritmo de Ricart-Agrawala
    Requiere confirmación de todos los nodos para acceder a región crítica
    """
    
    def __init__(self, node_id: str, lamport_clock: LamportClock):
        self.node_id = node_id
        self.clock = lamport_clock
        self.requesting = False
        self.request_timestamp = 0
        self.reply_count = 0
        self.reply_deferred: Dict[str, List] = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def request_access(self, resource_id: str, all_nodes: List[str]) -> bool:
        """
        Solicita acceso exclusivo a un recurso
        Retorna True cuando se obtiene acceso
        """
        async with self.lock:
            self.requesting = True
            self.request_timestamp = await self.clock.increment()
            self.reply_count = 0
        
        # ✅ CORRECCIÓN: Enviar solicitudes por red
        client = MongoClient(os.getenv("MONGO_URI"))
        db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
        
        # Obtener información de nodos
        send_tasks = []
        for node_id in all_nodes:
            if node_id != self.node_id:
                node = db.nodes.find_one({"node_id": node_id})
                if node and node.get("status") == "online":
                    send_tasks.append(
                        self._send_mutex_request(
                            node,
                            resource_id,
                            self.request_timestamp
                        )
                    )
        
        # Enviar todas las solicitudes en paralelo
        await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Esperar confirmación de todos
        required_replies = len(all_nodes) - 1
        timeout = 30
        start_time = time.time()
        
        while self.reply_count < required_replies:
            if time.time() - start_time > timeout:
                logger.error(f"❌ Timeout esperando confirmaciones para {resource_id}")
                self.requesting = False
                return False
            await asyncio.sleep(0.1)
        
        logger.info(f"✅ Acceso concedido a {resource_id}")
        return True
    
    async def _send_mutex_request(self, node: Dict, resource_id: str, timestamp: int):
        """Envía solicitud de mutex a un nodo"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                url = f"http://{node['ip_address']}:{node['port']}/coordination/mutex_request"
                await client.post(url, json={
                    "resource_id": resource_id,
                    "node_id": self.node_id,
                    "timestamp": timestamp
                })
        except Exception as e:
            logger.error(f"Error enviando mutex_request a {node['node_id']}: {e}")
    
    async def handle_request(self, remote_node: str, remote_timestamp: int, resource_id: str) -> bool:
        """
        Maneja solicitud de acceso de otro nodo
        Retorna True si se debe enviar confirmación inmediata
        """
        await self.clock.update(remote_timestamp)
        
        async with self.lock:
            should_reply = (
                not self.requesting or 
                remote_timestamp < self.request_timestamp or
                (remote_timestamp == self.request_timestamp and 
                 # Usar hash consistente para desempate
                 hash(remote_node) < hash(self.node_id))
            )
            
            if not should_reply:
                self.reply_deferred[resource_id].append(remote_node)
    
        return should_reply
    
    async def receive_reply(self):
        """Registra recepción de confirmación"""
        async with self.lock:
            self.reply_count += 1
    
    async def release_access(self, resource_id: str):
        """
        Libera acceso exclusivo y envía confirmaciones diferidas
        """
        async with self.lock:
            self.requesting = False
            deferred = self.reply_deferred.pop(resource_id, [])
        
        # Enviar confirmaciones diferidas
        logger.info(f"📤 Enviando {len(deferred)} confirmaciones diferidas")
        return deferred