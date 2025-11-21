"""
Sistema de Coordinación Distribuida para DistriSearch
- Exclusión mutua distribuida
"""
import time
import asyncio
from typing import Dict, List
from collections import defaultdict
from pymongo import MongoClient
from .Lamport_Clock import LamportClock
from coordinator import logger

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
        
        # Enviar solicitud a todos los nodos
        messages = []
        for node_id in all_nodes:
            if node_id != self.node_id:
                messages.append({
                    "type": "mutex_request",
                    "resource_id": resource_id,
                    "node_id": self.node_id,
                    "timestamp": self.request_timestamp
                })
        
        # Esperar confirmación de todos
        required_replies = len(all_nodes) - 1
        timeout = 30  # segundos
        start_time = time.time()
        
        while self.reply_count < required_replies:
            if time.time() - start_time > timeout:
                logger.error(f"❌ Timeout esperando confirmaciones para {resource_id}")
                self.requesting = False
                return False
            await asyncio.sleep(0.1)
        
        logger.info(f"✅ Acceso concedido a {resource_id}")
        return True
    
    async def handle_request(self, remote_node: str, remote_timestamp: int, resource_id: str) -> bool:
        """
        Maneja solicitud de acceso de otro nodo
        Retorna True si se debe enviar confirmación inmediata
        """
        await self.clock.update(remote_timestamp)
        
        async with self.lock:
            # Conceder acceso si:
            # 1. No estamos solicitando acceso
            # 2. O nuestra solicitud tiene timestamp mayor (prioridad menor)
            should_reply = (
                not self.requesting or 
                remote_timestamp < self.request_timestamp or
                (remote_timestamp == self.request_timestamp and remote_node < self.node_id)
            )
            
            if not should_reply:
                # Diferir respuesta hasta terminar nuestra región crítica
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