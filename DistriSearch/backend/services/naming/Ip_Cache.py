"""
Cache de IPs para nodos frecuentemente accedidos
Mejora rendimiento evitando consultas repetidas a MongoDB
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import logging
import os
import threading

logger = logging.getLogger(__name__)

class IPCache:
    """
    LRU Cache para información de nodos
    Mantiene los N nodos más accedidos en memoria
    """
    
    def __init__(self, max_size: int = None, ttl_seconds: int = None):
        self.max_size = max_size or int(os.getenv("IP_CACHE_MAX_SIZE", "100"))
        self.ttl_seconds = ttl_seconds or int(os.getenv("IP_CACHE_TTL", "300"))  # 5 min
        
        # OrderedDict para LRU
        self.cache: OrderedDict[str, Tuple[Dict, datetime]] = OrderedDict()
        
        # Estadísticas
        self.hits = 0
        self.misses = 0
    
    def get(self, node_id: str) -> Optional[Dict]:
        """
        Obtiene información de nodo desde cache
        Retorna None si no existe o expiró
        """
        if node_id not in self.cache:
            self.misses += 1
            return None
        
        node_info, cached_at = self.cache[node_id]
        
        # Verificar TTL
        age = (datetime.utcnow() - cached_at).total_seconds()
        if age > self.ttl_seconds:
            del self.cache[node_id]
            self.misses += 1
            logger.debug(f"❌ Cache expirado para nodo: {node_id}")
            return None
        
        # Mover al final (LRU)
        self.cache.move_to_end(node_id)
        
        self.hits += 1
        logger.debug(f"✅ Cache hit para nodo: {node_id}")
        return node_info.copy()
    
    def put(self, node_id: str, node_info: Dict):
        """Agrega/actualiza nodo en cache"""
        # Si ya existe, actualizar
        if node_id in self.cache:
            del self.cache[node_id]
        
        # Agregar al final
        self.cache[node_id] = (node_info, datetime.utcnow())
        
        # Evict LRU si excede tamaño
        if len(self.cache) > self.max_size:
            evicted_id, _ = self.cache.popitem(last=False)
            logger.debug(f"♻️ Cache evict (LRU): {evicted_id}")
    
    def invalidate(self, node_id: str):
        """Invalida entrada en cache"""
        if node_id in self.cache:
            del self.cache[node_id]
            logger.debug(f"🗑️ Cache invalidado: {node_id}")
    
    def clear(self):
        """Limpia todo el cache"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("🧹 Cache limpiado")
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "ttl_seconds": self.ttl_seconds
        }


# Singleton
_ip_cache = None
_ip_cache_lock = threading.Lock()

def get_ip_cache() -> IPCache:
    """Obtiene instancia singleton del cache"""
    global _ip_cache
    if _ip_cache is None:
        with _ip_cache_lock:
            if _ip_cache is None:
                _ip_cache = IPCache()
    return _ip_cache