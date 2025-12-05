"""
DistriSearch Master - Coordinador de Replicación

Gestiona la replicación de documentos entre Slaves
basándose en afinidad semántica.
"""
import asyncio
import httpx
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReplicationStatus(Enum):
    """Estados de una tarea de replicación"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReplicationTask:
    """Tarea de replicación de un documento"""
    file_id: str
    source_node: str
    target_nodes: List[str]
    status: ReplicationStatus = ReplicationStatus.PENDING
    completed_nodes: Set[str] = field(default_factory=set)
    failed_nodes: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    @property
    def progress(self) -> float:
        """Progreso de la replicación (0.0 - 1.0)"""
        if not self.target_nodes:
            return 1.0
        return len(self.completed_nodes) / len(self.target_nodes)
    
    def to_dict(self) -> Dict:
        return {
            "file_id": self.file_id,
            "source_node": self.source_node,
            "target_nodes": self.target_nodes,
            "status": self.status.value,
            "completed_nodes": list(self.completed_nodes),
            "failed_nodes": list(self.failed_nodes),
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message
        }


class ReplicationCoordinator:
    """
    Coordinador de replicación para el cluster Master-Slave.
    
    Responsabilidades:
    - Seleccionar nodos destino para replicación (por afinidad semántica)
    - Coordinar transferencia de archivos entre Slaves
    - Mantener factor de replicación ante fallos
    - Verificar integridad de réplicas
    """
    
    def __init__(
        self,
        replication_factor: int = 2,
        location_index = None,  # SemanticLocationIndex
        timeout: float = 30.0
    ):
        """
        Args:
            replication_factor: Número de réplicas a mantener
            location_index: Índice de ubicación semántica
            timeout: Timeout para operaciones HTTP
        """
        self.replication_factor = replication_factor
        self.location_index = location_index
        self.timeout = timeout
        
        # Endpoints de nodos: node_id -> base_url
        self._node_endpoints: Dict[str, str] = {}
        
        # Tareas de replicación: file_id -> ReplicationTask
        self._tasks: Dict[str, ReplicationTask] = {}
        
        # Cola de replicación pendiente
        self._pending_queue: asyncio.Queue = asyncio.Queue()
        
        # Worker task
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
    
    def register_node(self, node_id: str, base_url: str) -> None:
        """Registra endpoint de un nodo"""
        self._node_endpoints[node_id] = base_url.rstrip('/')
        logger.info(f"Nodo registrado para replicación: {node_id} -> {base_url}")
    
    def unregister_node(self, node_id: str) -> None:
        """Elimina nodo del coordinador"""
        self._node_endpoints.pop(node_id, None)
    
    async def start(self) -> None:
        """Inicia el worker de replicación"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._replication_worker())
        logger.info("Coordinador de replicación iniciado")
    
    async def stop(self) -> None:
        """Detiene el coordinador"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
    
    async def replicate_document(
        self,
        file_id: str,
        source_node: str,
        document_embedding = None  # np.ndarray
    ) -> ReplicationTask:
        """
        Inicia replicación de un documento.
        
        Args:
            file_id: ID del documento a replicar
            source_node: Nodo origen
            document_embedding: Embedding del documento para selección semántica
            
        Returns:
            Tarea de replicación creada
        """
        # Seleccionar nodos destino
        target_nodes = self._select_target_nodes(
            source_node, 
            document_embedding
        )
        
        if not target_nodes:
            logger.warning(f"No hay nodos disponibles para replicar {file_id}")
            task = ReplicationTask(
                file_id=file_id,
                source_node=source_node,
                target_nodes=[],
                status=ReplicationStatus.COMPLETED
            )
            self._tasks[file_id] = task
            return task
        
        # Crear tarea
        task = ReplicationTask(
            file_id=file_id,
            source_node=source_node,
            target_nodes=target_nodes
        )
        self._tasks[file_id] = task
        
        # Encolar para procesamiento
        await self._pending_queue.put(file_id)
        
        logger.info(f"Replicación encolada: {file_id} -> {target_nodes}")
        return task
    
    def _select_target_nodes(
        self, 
        source_node: str, 
        document_embedding = None
    ) -> List[str]:
        """
        Selecciona nodos para replicación.
        
        Si hay índice semántico, usa afinidad.
        Si no, selecciona nodos con menos documentos.
        """
        available = [
            node_id for node_id in self._node_endpoints.keys()
            if node_id != source_node
        ]
        
        if not available:
            return []
        
        # Número de réplicas necesarias
        num_replicas = min(self.replication_factor, len(available))
        
        # Si tenemos índice semántico y embedding, usar afinidad
        if self.location_index and document_embedding is not None:
            return self.location_index.select_replica_nodes(
                source_node,
                document_embedding,
                num_replicas
            )
        
        # Fallback: primeros N nodos disponibles
        return available[:num_replicas]
    
    async def _replication_worker(self) -> None:
        """Worker que procesa tareas de replicación"""
        while self._running:
            try:
                # Obtener siguiente tarea
                file_id = await asyncio.wait_for(
                    self._pending_queue.get(),
                    timeout=1.0
                )
                
                task = self._tasks.get(file_id)
                if not task or task.status != ReplicationStatus.PENDING:
                    continue
                
                # Procesar tarea
                await self._process_replication(task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en worker de replicación: {e}")
    
    async def _process_replication(self, task: ReplicationTask) -> None:
        """Procesa una tarea de replicación"""
        task.status = ReplicationStatus.IN_PROGRESS
        
        # Replicar a cada nodo destino en paralelo
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [
                self._replicate_to_node(client, task, target_node)
                for target_node in task.target_nodes
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Actualizar estado final
        if task.completed_nodes:
            task.status = ReplicationStatus.COMPLETED
        elif task.failed_nodes:
            task.status = ReplicationStatus.FAILED
        
        task.completed_at = datetime.utcnow()
        
        logger.info(
            f"Replicación completada: {task.file_id} "
            f"({len(task.completed_nodes)}/{len(task.target_nodes)} exitosas)"
        )
    
    async def _replicate_to_node(
        self, 
        client: httpx.AsyncClient, 
        task: ReplicationTask, 
        target_node: str
    ) -> None:
        """Replica documento a un nodo específico"""
        try:
            source_url = self._node_endpoints.get(task.source_node)
            target_url = self._node_endpoints.get(target_node)
            
            if not source_url or not target_url:
                raise ValueError(f"URL no encontrada para nodo")
            
            # 1. Obtener archivo del nodo origen
            download_url = f"{source_url}/api/download/{task.file_id}"
            response = await client.get(download_url)
            response.raise_for_status()
            
            file_content = response.content
            filename = response.headers.get(
                'content-disposition', 
                f'file_{task.file_id}'
            )
            
            # 2. Subir al nodo destino
            upload_url = f"{target_url}/api/upload"
            files = {'file': (filename, file_content)}
            data = {
                'source_node': task.source_node,
                'is_replica': 'true',
                'original_file_id': task.file_id
            }
            
            response = await client.post(upload_url, files=files, data=data)
            response.raise_for_status()
            
            task.completed_nodes.add(target_node)
            logger.debug(f"Réplica exitosa: {task.file_id} -> {target_node}")
            
        except Exception as e:
            task.failed_nodes.add(target_node)
            logger.error(f"Error replicando {task.file_id} a {target_node}: {e}")
    
    async def ensure_replication_factor(self, file_id: str) -> Optional[ReplicationTask]:
        """
        Verifica y restaura factor de replicación de un documento.
        
        Útil cuando un nodo cae y hay que re-replicar.
        """
        if not self.location_index:
            return None
        
        doc = self.location_index.get_document_location(file_id)
        if not doc:
            return None
        
        # Contar réplicas actuales
        # (Asumiendo que el location_index mantiene todas las ubicaciones)
        # TODO: Implementar tracking de réplicas
        
        # Por ahora, re-replicar desde el nodo original
        return await self.replicate_document(
            file_id,
            doc.node_id,
            doc.embedding
        )
    
    def get_task_status(self, file_id: str) -> Optional[ReplicationTask]:
        """Obtiene estado de una tarea de replicación"""
        return self._tasks.get(file_id)
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del coordinador"""
        status_counts = {
            ReplicationStatus.PENDING: 0,
            ReplicationStatus.IN_PROGRESS: 0,
            ReplicationStatus.COMPLETED: 0,
            ReplicationStatus.FAILED: 0
        }
        
        for task in self._tasks.values():
            status_counts[task.status] += 1
        
        return {
            "replication_factor": self.replication_factor,
            "registered_nodes": len(self._node_endpoints),
            "tasks": {
                "pending": status_counts[ReplicationStatus.PENDING],
                "in_progress": status_counts[ReplicationStatus.IN_PROGRESS],
                "completed": status_counts[ReplicationStatus.COMPLETED],
                "failed": status_counts[ReplicationStatus.FAILED]
            },
            "queue_size": self._pending_queue.qsize()
        }
