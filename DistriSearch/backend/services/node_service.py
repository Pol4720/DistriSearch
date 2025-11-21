from typing import Dict, List, Optional
from models import NodeInfo, NodeStatus
import database as database_viejo
from datetime import datetime, timedelta

def register_node(node: NodeInfo) -> Dict:
    """
    Registra un nuevo nodo o actualiza uno existente
    """
    # Verificar si el nodo ya existe
    existing_node = database_viejo.get_node(node.node_id)
    
    if existing_node:
        # Actualizar datos conservando el último status
        node.status = existing_node["status"]
    else:
        # Nodo nuevo, establecer como online
        node.status = NodeStatus.ONLINE
    
    # Actualizar timestamp
    node.last_seen = datetime.now()
    
    # Guardar en la base de datos
    database_viejo.register_node(node)
    
    return {
        "node_id": node.node_id,
        "status": node.status,
        "last_seen": node.last_seen
    }

def update_node_heartbeat(node_id: str) -> bool:
    """
    Actualiza el estado y timestamp de última conexión del nodo
    """
    node = database_viejo.get_node(node_id)
    if not node:
        return False
    
    database_viejo.update_node_status(node_id, NodeStatus.ONLINE.value)
    return True

def get_node(node_id: str) -> Optional[Dict]:
    """
    Obtiene información de un nodo
    """
    return database_viejo.get_node(node_id)

def get_all_nodes() -> List[Dict]:
    """
    Obtiene todos los nodos registrados
    """
    return database_viejo.get_all_nodes()

def check_node_timeouts():
    """
    Verifica nodos que no han enviado heartbeat recientemente
    y los marca como offline
    """
    timeout = datetime.now() - timedelta(minutes=5)  # 5 minutos sin heartbeat
    
    with database_viejo.get_connection() as conn:
        cursor = conn.cursor()
        # No marcar como offline a los nodos simulados (tienen carpeta montada y no envían heartbeats)
        cursor.execute(
            """
            UPDATE nodes
            SET status = ?
            WHERE status = ?
              AND last_seen < ?
              AND node_id NOT IN (SELECT node_id FROM node_mounts)
                            AND node_id != 'central'
            """,
            (
                NodeStatus.OFFLINE.value,
                NodeStatus.ONLINE.value,
                timeout,
            ),
        )
        conn.commit()
        return cursor.rowcount  # Número de nodos marcados como offline


def register_node_dynamic(
    node_id: str, 
    name: Optional[str] = None,
    ip_address: Optional[str] = None,
    port: int = 8080,
    request_host: Optional[str] = None,  # IP del request (FastAPI puede pasarla)
    shared_folder: Optional[str] = None
) -> Dict:
    """
    Registra un nodo dinámicamente sin requerir configuración previa.
    
    Args:
        node_id: Identificador único del nodo
        name: Nombre descriptivo (opcional, usa node_id si no se proporciona)
        ip_address: IP del nodo (opcional, se autodetecta si es None)
        port: Puerto del agente
        request_host: IP del requestor (para autodetectar)
        shared_folder: Ruta de carpeta compartida (si es nodo local simulado)
    """
    
    # Si no hay IP, intentar autodetectar desde la petición
    if not ip_address and request_host:
        ip_address = request_host.split(":")[0]
    
    # Validar que no exista ya
    existing = database_viejo.get_node(node_id)
    if existing:
        # Actualizar timestamp y marcar como online
        update_node_heartbeat(node_id)
        
        # Si se proporciona carpeta, configurar mount
        if shared_folder:
            database_viejo.set_node_mount(node_id, shared_folder)
        
        return {
            "node_id": node_id,
            "status": "updated",
            "message": "Nodo ya existente, actualizado",
            "ip_address": ip_address,
            "port": port
        }
    
    # Crear nuevo nodo
    node = NodeInfo(
        node_id=node_id,
        name=name or f"Nodo {node_id}",
        ip_address=ip_address or "unknown",
        port=port,
        status=NodeStatus.ONLINE,
        last_seen=datetime.now(),
        shared_files_count=0
    )
    
    # Registrar en MongoDB
    database_viejo.register_node(node)
    
    # Si es nodo simulado con carpeta, configurar mount
    if shared_folder:
        database_viejo.set_node_mount(node_id, shared_folder)
        
        # Si auto_scan está activado, escanear inmediatamente
        if os.getenv("AUTO_SCAN_ON_REGISTER", "false").lower() in {"true", "1", "yes"}:
            from services import index_service
            try:
                # Esto simula el comportamiento del agente
                index_service.scan_and_register_local_files(node_id, shared_folder)
                node.shared_files_count = count
                database_viejo.update_node_shared_files_count(node_id, count)
            except Exception as e:
                logger.warning(f"No se pudo auto-escanear nodo {node_id}: {e}")
    
    return {
        "node_id": node_id,
        "status": "registered",
        "message": "Nodo registrado exitosamente",
        "ip_address": ip_address,
        "port": port
    }

def get_node_config(node_id: str) -> Optional[Dict]:
    """
    Obtiene configuración completa de un nodo (incluye mount folder si existe)
    """
    node = database_viejo.get_node(node_id)
    if not node:
        return None
    
    mount = database_viejo.get_node_mount(node_id)
    node["mount_folder"] = mount
    node["api_key"] = os.getenv("ADMIN_API_KEY", "")  # Para que el nodo se autentique
    
    return node