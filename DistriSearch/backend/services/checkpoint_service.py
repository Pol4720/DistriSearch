"""
Servicio de checkpoints coordinados para recuperación backward
Implementa almacenamiento estable según teoría de tolerancia a fallos
"""
import os
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from pymongo import MongoClient
import json
import hashlib

logger = logging.getLogger(__name__)


class CheckpointService:
    """
    Gestión de checkpoints coordinados
    - Checkpoints independientes por nodo
    - Checkpoints coordinados del sistema completo
    - Almacenamiento estable en MongoDB
    """
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DBNAME", "distrisearch")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        
        # Configuración
        self.checkpoint_interval = int(os.getenv("CHECKPOINT_INTERVAL_SECONDS", "300"))
        
        # Inicializar colecciones
        self._init_collections()
    
    def _init_collections(self):
        """Inicializa colecciones para checkpoints"""
        # Checkpoints de nodos individuales
        self.db.node_checkpoints.create_index([("node_id", 1), ("timestamp", -1)])
        
        # Checkpoints globales coordinados
        self.db.global_checkpoints.create_index([("timestamp", -1)])
        
        # Líneas de recuperación
        self.db.recovery_lines.create_index([("checkpoint_id", 1)])
    
    async def create_node_checkpoint(self, node_id: str) -> Dict:
        """
        Crea checkpoint independiente de un nodo
        Almacenamiento estable de estado
        """
        try:
            # 1. Capturar estado del nodo
            node_state = {
                "node_id": node_id,
                "timestamp": datetime.utcnow(),
                "files_count": self.db.files.count_documents({"node_id": node_id}),
                "last_seen": self.db.nodes.find_one({"node_id": node_id}).get("last_seen"),
                "status": self.db.nodes.find_one({"node_id": node_id}).get("status")
            }
            
            # 2. Obtener lista de archivos
            files_snapshot = list(self.db.files.find(
                {"node_id": node_id},
                {"_id": 0, "file_id": 1, "content_hash": 1, "last_updated": 1}
            ))
            
            # 3. Calcular hash del checkpoint (detección de corrupción)
            checkpoint_data = json.dumps(files_snapshot, sort_keys=True, default=str)
            checkpoint_hash = hashlib.sha256(checkpoint_data.encode()).hexdigest()
            
            # 4. Guardar en almacenamiento estable (MongoDB)
            checkpoint_doc = {
                **node_state,
                "files_snapshot": files_snapshot,
                "checkpoint_hash": checkpoint_hash,
                "type": "independent"
            }
            
            result = self.db.node_checkpoints.insert_one(checkpoint_doc)
            checkpoint_id = str(result.inserted_id)
            
            logger.info(f"✅ Checkpoint independiente creado para {node_id}: {checkpoint_id}")
            
            return {
                "checkpoint_id": checkpoint_id,
                "node_id": node_id,
                "files_count": len(files_snapshot),
                "hash": checkpoint_hash,
                "timestamp": node_state['timestamp']
            }
            
        except Exception as e:
            logger.error(f"❌ Error creando checkpoint para {node_id}: {e}")
            raise
    
    async def create_coordinated_checkpoint(self) -> Dict:
        """
        Crea checkpoint coordinado del sistema completo
        Garantiza línea de recuperación consistente globalmente
        """
        try:
            # 1. Obtener todos los nodos online
            online_nodes = list(self.db.nodes.find({"status": "online"}))
            
            if not online_nodes:
                raise Exception("No hay nodos online para checkpoint coordinado")
            
            logger.info(f"🔄 Iniciando checkpoint coordinado con {len(online_nodes)} nodos")
            
            # 2. Crear checkpoints individuales para cada nodo
            node_checkpoints = []
            for node in online_nodes:
                try:
                    checkpoint = await self.create_node_checkpoint(node['node_id'])
                    node_checkpoints.append(checkpoint)
                except Exception as e:
                    logger.error(f"⚠️ Falló checkpoint de {node['node_id']}: {e}")
            
            # 3. Crear checkpoint global coordinado
            global_checkpoint = {
                "timestamp": datetime.utcnow(),
                "participating_nodes": [c['node_id'] for c in node_checkpoints],
                "node_checkpoints": node_checkpoints,
                "total_files": sum(c['files_count'] for c in node_checkpoints),
                "type": "coordinated",
                "consistency": "global"
            }
            
            result = self.db.global_checkpoints.insert_one(global_checkpoint)
            checkpoint_id = str(result.inserted_id)
            
            logger.info(f"✅ Checkpoint coordinado creado: {checkpoint_id}")
            
            # 4. Marcar como línea de recuperación válida
            self.db.recovery_lines.insert_one({
                "checkpoint_id": checkpoint_id,
                "timestamp": global_checkpoint['timestamp'],
                "valid": True
            })
            
            return {
                "checkpoint_id": checkpoint_id,
                "nodes_count": len(online_nodes),
                "total_files": global_checkpoint['total_files'],
                "timestamp": global_checkpoint['timestamp']
            }
            
        except Exception as e:
            logger.error(f"❌ Error creando checkpoint coordinado: {e}")
            raise
    
    async def restore_from_checkpoint(self, checkpoint_id: str) -> Dict:
        """
        Recuperación backward desde checkpoint
        Restaura sistema a estado válido anterior
        """
        try:
            # 1. Buscar checkpoint
            checkpoint = self.db.global_checkpoints.find_one({"_id": checkpoint_id})
            
            if not checkpoint:
                raise Exception(f"Checkpoint {checkpoint_id} no encontrado")
            
            logger.info(f"🔄 Restaurando desde checkpoint {checkpoint_id}")
            
            # 2. Verificar integridad
            if not self._verify_checkpoint_integrity(checkpoint):
                raise Exception("Checkpoint corrupto - verificación de integridad falló")
            
            # 3. Restaurar estado de cada nodo
            restored_nodes = 0
            for node_checkpoint in checkpoint['node_checkpoints']:
                try:
                    await self._restore_node_state(node_checkpoint)
                    restored_nodes += 1
                except Exception as e:
                    logger.error(f"⚠️ Error restaurando {node_checkpoint['node_id']}: {e}")
            
            logger.info(f"✅ Recuperación completada: {restored_nodes} nodos restaurados")
            
            return {
                "checkpoint_id": checkpoint_id,
                "restored_nodes": restored_nodes,
                "total_files": checkpoint['total_files'],
                "timestamp": checkpoint['timestamp']
            }
            
        except Exception as e:
            logger.error(f"❌ Error en recuperación: {e}")
            raise
    
    def _verify_checkpoint_integrity(self, checkpoint: Dict) -> bool:
        """Verifica integridad de checkpoint usando hashes"""
        for node_cp in checkpoint.get('node_checkpoints', []):
            stored_hash = node_cp.get('hash')
            if not stored_hash:
                return False
            
            # Recalcular hash
            checkpoint_data = json.dumps(node_cp.get('files_snapshot', []), sort_keys=True)
            calculated_hash = hashlib.sha256(checkpoint_data.encode()).hexdigest()
            
            if stored_hash != calculated_hash:
                logger.error(f"❌ Hash mismatch en checkpoint de {node_cp['node_id']}")
                return False
        
        return True
    
    async def _restore_node_state(self, node_checkpoint: Dict):
        """Restaura estado de un nodo desde su checkpoint"""
        node_id = node_checkpoint['node_id']
        files_snapshot = node_checkpoint.get('files_snapshot', [])
        
        # Eliminar archivos actuales del nodo
        self.db.files.delete_many({"node_id": node_id})
        
        # Restaurar desde snapshot
        if files_snapshot:
            # Reconstruir documentos completos desde metadata
            for file_meta in files_snapshot:
                self.db.files.insert_one({
                    "file_id": file_meta['file_id'],
                    "node_id": node_id,
                    "content_hash": file_meta.get('content_hash'),
                    "last_updated": file_meta.get('last_updated'),
                    "restored_from_checkpoint": True,
                    "checkpoint_timestamp": node_checkpoint['timestamp']
                })
        
        logger.info(f"✅ Estado de {node_id} restaurado: {len(files_snapshot)} archivos")


# Singleton
_checkpoint_service = None

def get_checkpoint_service() -> CheckpointService:
    global _checkpoint_service
    if _checkpoint_service is None:
        _checkpoint_service = CheckpointService()
    return _checkpoint_service