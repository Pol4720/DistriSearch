from typing import Dict, List, Optional
from models import NodeInfo, NodeStatus
import database
from datetime import datetime, timedelta

def register_node(node: NodeInfo) -> Dict:
    """
    Registra un nuevo nodo o actualiza uno existente
    """
    # Verificar si el nodo ya existe
    existing_node = database.get_node(node.node_id)
    
    if existing_node:
        # Actualizar datos conservando el último status
        node.status = existing_node["status"]
    else:
        # Nodo nuevo, establecer como online
        node.status = NodeStatus.ONLINE
    
    # Actualizar timestamp
    node.last_seen = datetime.now()
    
    # Guardar en la base de datos
    database.register_node(node)
    
    return {
        "node_id": node.node_id,
        "status": node.status,
        "last_seen": node.last_seen
    }

def update_node_heartbeat(node_id: str) -> bool:
    """
    Actualiza el estado y timestamp de última conexión del nodo
    """
    node = database.get_node(node_id)
    if not node:
        return False
    
    database.update_node_status(node_id, NodeStatus.ONLINE.value)
    return True

def get_node(node_id: str) -> Optional[Dict]:
    """
    Obtiene información de un nodo
    """
    return database.get_node(node_id)

def get_all_nodes() -> List[Dict]:
    """
    Obtiene todos los nodos registrados
    """
    return database.get_all_nodes()

def check_node_timeouts():
    """
    Verifica nodos que no han enviado heartbeat recientemente
    y los marca como offline
    """
    timeout = datetime.now() - timedelta(minutes=5)  # 5 minutos sin heartbeat
    
    with database.get_connection() as conn:
        cursor = conn.cursor()
        # No marcar como offline a los nodos simulados (tienen carpeta montada y no envían heartbeats)
        cursor.execute(
            """
            UPDATE nodes
            SET status = ?
            WHERE status = ?
              AND last_seen < ?
              AND node_id NOT IN (SELECT node_id FROM node_mounts)
            """,
            (
                NodeStatus.OFFLINE.value,
                NodeStatus.ONLINE.value,
                timeout,
            ),
        )
        conn.commit()
        return cursor.rowcount  # Número de nodos marcados como offline
