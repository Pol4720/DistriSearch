"""
DistriSearch - Módulo de Mensajería del Cluster
================================================
Funciones centralizadas para serialización/deserialización de mensajes UDP.
Usado por heartbeat, election y discovery.
"""

import json
import struct
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from dataclasses import asdict

from core.models import ClusterMessage, MessageType, NodeInfo


# Constantes de protocolo
PROTOCOL_VERSION = 1
MAGIC_HEADER = b'DSM\x01'  # DistriSearch Message v1
MAX_UDP_SIZE = 65507  # Máximo UDP payload


def serialize_message(message: ClusterMessage) -> bytes:
    """
    Serializa un ClusterMessage para transmisión UDP.
    
    Formato:
    - 4 bytes: Magic header (DSM\x01)
    - 1 byte: Tipo de mensaje
    - Variable: JSON payload
    
    Args:
        message: ClusterMessage a serializar
        
    Returns:
        bytes listos para enviar por UDP
        
    Raises:
        ValueError: Si el mensaje excede el tamaño máximo UDP
    """
    # Construir payload
    payload = {
        'sender_id': message.sender_id,
        'timestamp': message.timestamp.isoformat() if message.timestamp else datetime.utcnow().isoformat(),
        'payload': message.payload or {}
    }
    
    json_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    
    # Construir mensaje completo
    result = MAGIC_HEADER + struct.pack('B', message.msg_type.value) + json_bytes
    
    if len(result) > MAX_UDP_SIZE:
        raise ValueError(f"Mensaje excede tamaño máximo UDP: {len(result)} > {MAX_UDP_SIZE}")
    
    return result


def deserialize_message(data: bytes) -> Optional[ClusterMessage]:
    """
    Deserializa bytes UDP a ClusterMessage.
    
    Args:
        data: bytes recibidos por UDP
        
    Returns:
        ClusterMessage o None si el formato es inválido
    """
    try:
        # Verificar header mágico
        if len(data) < 5 or data[:4] != MAGIC_HEADER:
            return None
        
        # Extraer tipo de mensaje
        msg_type_value = struct.unpack('B', data[4:5])[0]
        
        try:
            msg_type = MessageType(msg_type_value)
        except ValueError:
            return None
        
        # Parsear JSON
        json_data = json.loads(data[5:].decode('utf-8'))
        
        # Reconstruir timestamp
        timestamp = datetime.fromisoformat(json_data.get('timestamp', datetime.utcnow().isoformat()))
        
        return ClusterMessage(
            msg_type=msg_type,
            sender_id=json_data.get('sender_id', ''),
            timestamp=timestamp,
            payload=json_data.get('payload', {})
        )
        
    except (json.JSONDecodeError, UnicodeDecodeError, struct.error):
        return None


def create_heartbeat_ping(node_id: str, role: str, load: float = 0.0) -> bytes:
    """Crea mensaje PING de heartbeat."""
    message = ClusterMessage(
        msg_type=MessageType.PING,
        sender_id=node_id,
        payload={
            'role': role,
            'load': load
        }
    )
    return serialize_message(message)


def create_heartbeat_pong(node_id: str, role: str) -> bytes:
    """Crea mensaje PONG de respuesta."""
    message = ClusterMessage(
        msg_type=MessageType.PONG,
        sender_id=node_id,
        payload={'role': role}
    )
    return serialize_message(message)


def create_election_message(node_id: str, priority: int) -> bytes:
    """Crea mensaje de inicio de elección (Bully algorithm)."""
    message = ClusterMessage(
        msg_type=MessageType.ELECTION,
        sender_id=node_id,
        payload={'priority': priority}
    )
    return serialize_message(message)


def create_coordinator_message(node_id: str) -> bytes:
    """Crea mensaje de anuncio de nuevo Master."""
    message = ClusterMessage(
        msg_type=MessageType.COORDINATOR,
        sender_id=node_id,
        payload={'new_master': node_id}
    )
    return serialize_message(message)


def create_alive_message(node_id: str) -> bytes:
    """Crea mensaje ALIVE (respuesta a ELECTION)."""
    message = ClusterMessage(
        msg_type=MessageType.ALIVE,
        sender_id=node_id,
        payload={}
    )
    return serialize_message(message)


def create_discovery_announce(node_info: NodeInfo) -> bytes:
    """Crea mensaje de anuncio para discovery multicast."""
    message = ClusterMessage(
        msg_type=MessageType.ANNOUNCE,
        sender_id=node_info.node_id,
        payload={
            'node_id': node_info.node_id,
            'ip': node_info.ip,
            'http_port': node_info.http_port,
            'heartbeat_port': node_info.heartbeat_port,
            'election_port': node_info.election_port,
            'role': node_info.role.value if hasattr(node_info.role, 'value') else str(node_info.role),
            'status': node_info.status.value if hasattr(node_info.status, 'value') else str(node_info.status)
        }
    )
    return serialize_message(message)


def create_discovery_request(node_id: str) -> bytes:
    """Crea mensaje de solicitud de descubrimiento."""
    message = ClusterMessage(
        msg_type=MessageType.DISCOVERY_REQUEST,
        sender_id=node_id,
        payload={}
    )
    return serialize_message(message)


def create_join_cluster_message(node_info: NodeInfo) -> bytes:
    """Crea mensaje para unirse al cluster."""
    message = ClusterMessage(
        msg_type=MessageType.JOIN,
        sender_id=node_info.node_id,
        payload=asdict(node_info) if hasattr(node_info, '__dataclass_fields__') else {
            'node_id': node_info.node_id,
            'ip': node_info.ip,
            'http_port': node_info.http_port
        }
    )
    return serialize_message(message)


def create_leave_cluster_message(node_id: str, reason: str = "shutdown") -> bytes:
    """Crea mensaje de salida del cluster."""
    message = ClusterMessage(
        msg_type=MessageType.LEAVE,
        sender_id=node_id,
        payload={'reason': reason}
    )
    return serialize_message(message)


def create_sync_request(node_id: str, data_type: str, since: Optional[datetime] = None) -> bytes:
    """Crea mensaje de solicitud de sincronización."""
    message = ClusterMessage(
        msg_type=MessageType.SYNC_REQUEST,
        sender_id=node_id,
        payload={
            'data_type': data_type,  # 'files', 'index', 'metadata'
            'since': since.isoformat() if since else None
        }
    )
    return serialize_message(message)


def create_sync_response(node_id: str, data_type: str, data: Dict[str, Any]) -> bytes:
    """Crea mensaje de respuesta de sincronización."""
    message = ClusterMessage(
        msg_type=MessageType.SYNC_RESPONSE,
        sender_id=node_id,
        payload={
            'data_type': data_type,
            'data': data
        }
    )
    return serialize_message(message)


def parse_node_info_from_payload(payload: Dict[str, Any]) -> Optional[NodeInfo]:
    """
    Extrae NodeInfo desde el payload de un mensaje.
    
    Args:
        payload: Diccionario con datos del nodo
        
    Returns:
        NodeInfo o None si faltan campos requeridos
    """
    from core.models import NodeRole, NodeStatus
    
    required_fields = ['node_id', 'ip']
    if not all(field in payload for field in required_fields):
        return None
    
    try:
        role = NodeRole(payload.get('role', 'slave'))
    except ValueError:
        role = NodeRole.SLAVE
        
    try:
        status = NodeStatus(payload.get('status', 'unknown'))
    except ValueError:
        status = NodeStatus.UNKNOWN
    
    return NodeInfo(
        node_id=payload['node_id'],
        ip=payload['ip'],
        http_port=payload.get('http_port', 8000),
        heartbeat_port=payload.get('heartbeat_port', 5000),
        election_port=payload.get('election_port', 5001),
        role=role,
        status=status,
        last_seen=datetime.utcnow()
    )
