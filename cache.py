"""
Cache LRU distribuido para resultados de búsqueda y localización de términos.
"""
from collections import OrderedDict
from typing import Any, Optional, Dict
import time
import logging
import asyncio

logger = logging.getLogger(__name__)


class LRUCache:
    """Cache LRU con TTL."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        Args:
            max_size: Capacidad máxima del cache
            ttl_seconds: Time-to-live en segundos
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del cache."""
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        
        # Verificar TTL
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        
        # Mover al final (más recientemente usado)
        self._cache.move_to_end(key)
        return value
    
    def put(self, key: str, value: Any):
        """Añade valor al cache."""
        # Si existe, eliminar primero
        if key in self._cache:
            del self._cache[key]
        
        # Añadir con timestamp
        self._cache[key] = (value, time.time())
        
        # Evict si excede tamaño
        if len(self._cache) > self.max_size:
            # Eliminar más antiguo (primero en el OrderedDict)
            self._cache.popitem(last=False)
    
    def invalidate(self, key: str):
        """Invalida entrada del cache."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """Limpia todo el cache."""
        self._cache.clear()
    
    def stats(self) -> Dict:
        """Estadísticas del cache."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds
        }


class DistributedCache:
    """Cache con invalidación distribuida."""
    
    def __init__(self, network, node_id: int, max_size: int = 1000):
        self.network = network
        self.node_id = node_id
        self.local_cache = LRUCache(max_size=max_size)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get con fallback a red."""
        value = self.local_cache.get(key)
        if value is not None:
            logger.debug(f"Cache hit: {key}")
        return value
    
    async def put(self, key: str, value: Any):
        """Put local."""
        self.local_cache.put(key, value)
    
    async def invalidate_globally(self, key: str, target_nodes: list):
        """Invalida cache en múltiples nodos."""
        self.local_cache.invalidate(key)
        
        # Broadcast invalidación
        tasks = []
        for node_id in target_nodes:
            if node_id != self.node_id:
                tasks.append(
                    self.network.send_message(
                        self.node_id,
                        node_id,
                        {"type": "cache_invalidate", "key": key}
                    )
                )
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)