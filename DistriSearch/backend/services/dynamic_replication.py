"""
Servicio de replicación dinámica con consistencia eventual
Implementa el protocolo de escritura local y consenso adaptativo
"""
import logging
import asyncio
import hashlib
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
import os

import httpx
from pymongo import MongoClient

logger = logging.getLogger(__name__)

class DynamicReplicationService:
    """
    Implementa replicación dinámica con:
    - Consistencia eventual
    - Escritura local (datos migran al nodo más cercano)
    - Detección automática de conflictos
    """
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DBNAME", "distrisearch")
        self.replication_factor = int(os.getenv("REPLICATION_FACTOR", "3"))
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        
        # Configuración de consistencia
        self.sync_interval = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))
        self.conflict_resolution = os.getenv("CONFLICT_RESOLUTION", "last_write_wins")
        
    def get_replication_nodes(self, file_id: str, exclude_nodes: Set[str] = None) -> List[Dict]:
        """
        Selecciona nodos para replicar según:
        1. Factor de replicación
        2. Nodos online
        3. Distribución geográfica/de carga
        """
        exclude_nodes = exclude_nodes or set()
        
        # Obtener nodos online
        online_nodes = list(self.db.nodes.find({
            "status": "online",
            "node_id": {"$nin": list(exclude_nodes)}
        }))
        
        if len(online_nodes) < self.replication_factor:
            logger.warning(f"Solo {len(online_nodes)} nodos disponibles, factor requerido: {self.replication_factor}")
        
        # Seleccionar usando hash consistente
        file_hash = int(hashlib.md5(file_id.encode()).hexdigest(), 16)
        sorted_nodes = sorted(online_nodes, key=lambda n: abs(hash(n['node_id']) - file_hash))
        
        return sorted_nodes[:self.replication_factor]
    
    async def replicate_file(self, file_meta: Dict, source_node_id: str) -> Dict:
        """
        Replica un archivo a N nodos según el factor de replicación
        Protocolo: Escritura Local
        """
        file_id = file_meta['file_id']
        
        # Obtener nodos destino
        target_nodes = self.get_replication_nodes(file_id, exclude_nodes={source_node_id})
        
        results = {
            "file_id": file_id,
            "replicated_to": [],
            "failed": [],
            "timestamp": datetime.utcnow()
        }
        
        # Replicar en paralelo
        tasks = []
        for node in target_nodes:
            tasks.append(self._replicate_to_node(file_meta, source_node_id, node))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for idx, response in enumerate(responses):
            node = target_nodes[idx]
            if isinstance(response, Exception):
                results['failed'].append({
                    'node_id': node['node_id'],
                    'error': str(response)
                })
            else:
                results['replicated_to'].append(node['node_id'])
        
        # Guardar metadata de replicación
        self.db.replications.insert_one({
            "file_id": file_id,
            "source_node": source_node_id,
            "target_nodes": results['replicated_to'],
            "timestamp": results['timestamp'],
            "status": "completed" if not results['failed'] else "partial"
        })
        
        return results
    
    async def _replicate_to_node(self, file_meta: Dict, source_node_id: str, target_node: Dict):
        """Replica archivo a un nodo específico"""
        try:
            # Obtener contenido del archivo desde el nodo fuente
            source_node = self.db.nodes.find_one({"node_id": source_node_id})
            if not source_node:
                raise Exception(f"Nodo fuente {source_node_id} no encontrado")
            
            # Descargar archivo del nodo fuente
            async with httpx.AsyncClient(timeout=60) as client:
                source_url = f"http://{source_node['ip_address']}:{source_node['port']}/files/{file_meta['file_id']}"
                response = await client.get(source_url)
                response.raise_for_status()
                file_content = response.content
            
            # Subir al nodo destino
            async with httpx.AsyncClient(timeout=60) as client:
                target_url = f"http://{target_node['ip_address']}:{target_node['port']}/upload"
                files = {'file': (file_meta['name'], file_content, file_meta['mime_type'])}
                data = {'metadata': str(file_meta)}
                
                response = await client.post(target_url, files=files, data=data)
                response.raise_for_status()
            
            # Registrar en índice central
            self.db.files.insert_one({
                **file_meta,
                "node_id": target_node['node_id'],
                "replicated_from": source_node_id,
                "replication_timestamp": datetime.utcnow()
            })
            
            logger.info(f"Archivo {file_meta['file_id']} replicado a {target_node['node_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error replicando a {target_node['node_id']}: {e}")
            raise
    
    async def synchronize_eventual_consistency(self):
        """
        Sincronización periódica para garantizar consistencia eventual
        - Detecta archivos desactualizados
        - Resuelve conflictos
        - Propaga cambios
        """
        logger.info("Iniciando sincronización de consistencia eventual")
        
        # Obtener todos los archivos únicos
        pipeline = [
            {"$group": {
                "_id": "$file_id",
                "versions": {"$push": {
                    "node_id": "$node_id",
                    "last_updated": "$last_updated",
                    "content_hash": "$content_hash"
                }}
            }}
        ]
        
        files_versions = list(self.db.files.aggregate(pipeline))
        
        conflicts_resolved = 0
        files_synced = 0
        
        for file_group in files_versions:
            file_id = file_group['_id']
            versions = file_group['versions']
            
            # Detectar conflictos (versiones diferentes)
            if len(set(v.get('content_hash') for v in versions if v.get('content_hash'))) > 1:
                # Resolver conflicto
                canonical_version = self._resolve_conflict(file_id, versions)
                
                # Propagar versión canónica
                await self._propagate_canonical_version(file_id, canonical_version, versions)
                conflicts_resolved += 1
            
            files_synced += 1
        
        logger.info(f"Sincronización completada: {files_synced} archivos, {conflicts_resolved} conflictos resueltos")
        
        return {
            "files_synced": files_synced,
            "conflicts_resolved": conflicts_resolved,
            "timestamp": datetime.utcnow()
        }
    
    def _resolve_conflict(self, file_id: str, versions: List[Dict]) -> Dict:
        """
        Resolución de conflictos según estrategia configurada
        - last_write_wins: Versión más reciente
        - vector_clock: Relojes vectoriales (más complejo)
        """
        if self.conflict_resolution == "last_write_wins":
            # Ordenar por timestamp y tomar el más reciente
            sorted_versions = sorted(versions, key=lambda v: v.get('last_updated', datetime.min), reverse=True)
            return sorted_versions[0]
        
        # Otras estrategias...
        return versions[0]
    
    async def _propagate_canonical_version(self, file_id: str, canonical: Dict, all_versions: List[Dict]):
        """Propaga la versión canónica a todos los nodos"""
        source_node_id = canonical['node_id']
        
        # Obtener nodos con versiones desactualizadas
        outdated_nodes = [v['node_id'] for v in all_versions if v['node_id'] != source_node_id]
        
        # Obtener metadata completa
        file_meta = self.db.files.find_one({"file_id": file_id, "node_id": source_node_id})
        if not file_meta:
            logger.error(f"No se encontró metadata para {file_id} en {source_node_id}")
            return
        
        # Replicar a nodos desactualizados
        for node_id in outdated_nodes:
            node = self.db.nodes.find_one({"node_id": node_id})
            if node and node.get('status') == 'online':
                try:
                    await self._replicate_to_node(file_meta, source_node_id, node)
                except Exception as e:
                    logger.error(f"Error propagando a {node_id}: {e}")
    
    def get_replication_status(self) -> Dict:
        """Obtiene estado de la replicación del sistema"""
        total_files = self.db.files.count_documents({})
        
        # Archivos con replicación completa
        pipeline = [
            {"$group": {
                "_id": "$file_id",
                "replica_count": {"$sum": 1}
            }},
            {"$match": {
                "replica_count": {"$gte": self.replication_factor}
            }}
        ]
        fully_replicated = len(list(self.db.files.aggregate(pipeline)))
        
        # Archivos sub-replicados
        under_replicated = total_files - fully_replicated
        
        return {
            "total_unique_files": self.db.files.distinct("file_id").__len__(),
            "total_replicas": total_files,
            "replication_factor": self.replication_factor,
            "fully_replicated": fully_replicated,
            "under_replicated": under_replicated,
            "replication_coverage": (fully_replicated / total_files * 100) if total_files > 0 else 0
        }


# Singleton global
_replication_service = None

def get_replication_service() -> DynamicReplicationService:
    global _replication_service
    if _replication_service is None:
        _replication_service = DynamicReplicationService()
    return _replication_service