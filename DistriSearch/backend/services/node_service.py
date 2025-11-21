from typing import Dict, List, Optional
from models import NodeInfo, NodeStatus
import database
from datetime import datetime, timedelta
import logging
import os
from services.naming.ip_cache import get_ip_cache  # ✅ Agregar import

logger = logging.getLogger(__name__)


def get_node(node_id: str) -> Optional[Dict]:
    cache = get_ip_cache()
    
    # Verificar si cache está desactualizado
    cached = cache.get(node_id)
    if cached:
        # Validar con timestamp de DB cada 5 segundos
        if (datetime.now() - cached.get('cache_time', datetime.min)).seconds < 5:
            return cached
    
    # Cache miss o desactualizado - consultar DB
    node = database.get_node(node_id)
    
    if node:
        node['cache_time'] = datetime.now()
        cache.put(node_id, node)
    
    return node


def register_node(node: NodeInfo) -> Dict:
    """Registra un nuevo nodo o actualiza uno existente."""
    existing_node = database.get_node(node.node_id)
    
    if existing_node:
        node.status = existing_node["status"]
    else:
        node.status = NodeStatus.ONLINE
    
    node.last_seen = datetime.now()
    database.register_node(node)
    
    # ✅ Invalidar cache
    cache = get_ip_cache()
    cache.invalidate(node.node_id)
    
    return {
        "node_id": node.node_id,
        "status": node.status,
        "last_seen": node.last_seen
    }


def update_node_heartbeat(node_id: str) -> bool:
    """Actualiza el estado y timestamp de última conexión del nodo."""
    node = database.get_node(node_id)
    if not node:
        return False
    
    database.update_node_status(node_id, NodeStatus.ONLINE.value)
    return True


def get_all_nodes() -> List[Dict]:
    """Obtiene todos los nodos registrados."""
    return database.get_all_nodes()


def check_node_timeouts():
    """Verifica nodos que no han enviado heartbeat recientemente."""
    timeout = datetime.now() - timedelta(minutes=5)
    
    # Actualizar nodos con timeout
    result = database._db.nodes.update_many(
        {
            "status": "online",
            "last_seen": {"$lt": timeout},
            "node_id": {"$ne": "central"}  # No marcar nodo central
        },
        {"$set": {"status": "offline"}}
    )
    
    if result.modified_count > 0:
        logger.info(f"Marcados {result.modified_count} nodos como offline por timeout")
    
    return result.modified_count


def register_node_dynamic(
    node_id: str, 
    name: Optional[str] = None,
    ip_address: Optional[str] = None,
    port: int = 8080,
    request_host: Optional[str] = None,
    shared_folder: Optional[str] = None
) -> Dict:
    """Registra un nodo dinámicamente sin requerir configuración previa."""
    
    if not ip_address and request_host:
        ip_address = request_host.split(":")[0]
    
    existing = database.get_node(node_id)
    if existing:
        update_node_heartbeat(node_id)
        
        if shared_folder:
            database.set_node_mount(node_id, shared_folder)
        
        return {
            "node_id": node_id,
            "status": "updated",
            "message": "Nodo ya existente, actualizado",
            "ip_address": ip_address,
            "port": port
        }
    
    node = NodeInfo(
        node_id=node_id,
        name=name or f"Nodo {node_id}",
        ip_address=ip_address or "unknown",
        port=port,
        status=NodeStatus.ONLINE,
        last_seen=datetime.now(),
        shared_files_count=0
    )
    
    database.register_node(node)
    
    if shared_folder:
        database.set_node_mount(node_id, shared_folder)
    
    return {
        "node_id": node_id,
        "status": "registered",
        "message": "Nodo registrado exitosamente",
        "ip_address": ip_address,
        "port": port
    }


def get_node_config(node_id: str) -> Optional[Dict]:
    """Obtiene configuración completa de un nodo."""
    node = database.get_node(node_id)
    if not node:
        return None
    
    mount = database.get_node_mount(node_id)
    node["mount_folder"] = mount
    node["api_key"] = os.getenv("ADMIN_API_KEY", "")
        
    return node
