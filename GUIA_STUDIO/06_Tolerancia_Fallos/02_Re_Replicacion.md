# Re-Replicación

## Concepto

La **re-replicación** es el proceso de crear nuevas réplicas de documentos cuando el factor de replicación cae por debajo del objetivo (típicamente 2). Esto ocurre cuando:

- Un nodo falla permanentemente
- Se detectan réplicas corruptas
- Se aumenta el factor de replicación

## Flujo de Re-Replicación

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    PROCESO DE RE-REPLICACIÓN                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   1. Nodo_3 FALLA                                                        │
│      ┌─────────────────────────────────────────────────────────────┐    │
│      │ Antes:                                                      │    │
│      │   Doc_A: Nodo_1●  Nodo_3○  ← Nodo_3 tenía réplica          │    │
│      │   Doc_B: Nodo_3●  Nodo_2○  ← Nodo_3 era primario           │    │
│      │   Doc_C: Nodo_2●  Nodo_3○  ← Nodo_3 tenía réplica          │    │
│      └─────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              ▼                                           │
│   2. Identificar documentos afectados                                    │
│      affected_docs = [Doc_A, Doc_B, Doc_C]                              │
│                              │                                           │
│                              ▼                                           │
│   3. Clasificar por urgencia                                            │
│      ┌─────────────────────────────────────────────────────────────┐    │
│      │ CRITICAL: Doc_B (primario en nodo fallido, solo 1 réplica) │    │
│      │ HIGH:     Doc_A, Doc_C (bajo factor de replicación)        │    │
│      └─────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              ▼                                           │
│   4. Promover réplica de Doc_B                                          │
│      Doc_B: Nodo_2 promovido a primario                                 │
│                              │                                           │
│                              ▼                                           │
│   5. Re-replicar a nuevos nodos                                         │
│      ┌─────────────────────────────────────────────────────────────┐    │
│      │ Después:                                                    │    │
│      │   Doc_A: Nodo_1●  Nodo_4○  ← Nueva réplica en Nodo_4       │    │
│      │   Doc_B: Nodo_2●  Nodo_1○  ← Promovido + nueva réplica     │    │
│      │   Doc_C: Nodo_2●  Nodo_4○  ← Nueva réplica en Nodo_4       │    │
│      └─────────────────────────────────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Clase `ReReplicationManager`

**Ubicación:** `backend/app/core/recovery/re_replication.py`

```python
class ReReplicationManager:
    """
    Manages re-replication of data after failures.
    
    When a node fails:
    1. Identifies all documents that were stored on that node
    2. For each document, finds a healthy replica
    3. Replicates to a new node to maintain replication factor
    """
    
    def __init__(
        self,
        replicate_func: Optional[Callable] = None,
        get_document_replicas: Optional[Callable] = None,
        select_target_node: Optional[Callable] = None,
        max_concurrent: int = 5,
        batch_size: int = 20,
        retry_limit: int = 3
    ):
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.retry_limit = retry_limit
        
        self._pending_tasks: Dict[str, ReReplicationTask] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
```

## Tarea de Re-Replicación

```python
@dataclass
class ReReplicationTask:
    """Task to re-replicate a document."""
    task_id: str
    document_id: str
    failed_node: str
    source_node: Optional[str] = None   # Réplica sana origen
    target_node: Optional[str] = None   # Nuevo destino
    status: ReReplicationStatus = ReReplicationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    priority: int = 1  # Mayor = más urgente
```

## Estados de Re-Replicación

```python
class ReReplicationStatus(Enum):
    PENDING = "pending"         # En cola
    IN_PROGRESS = "in_progress" # Ejecutándose
    COMPLETED = "completed"     # Éxito
    FAILED = "failed"           # Falló
    CANCELLED = "cancelled"     # Cancelado
```

## Encolar Re-Replicación

```python
def queue_re_replication(
    self,
    document_id: str,
    failed_node: str,
    priority: int = 1
) -> ReReplicationTask:
    """Queue a document for re-replication."""
    task_id = f"rerep_{document_id}_{datetime.utcnow().timestamp()}"
    
    task = ReReplicationTask(
        task_id=task_id,
        document_id=document_id,
        failed_node=failed_node,
        priority=priority
    )
    
    self._pending_tasks[task_id] = task
    logger.debug(f"Queued re-replication for {document_id}")
    
    return task


def queue_bulk_re_replication(
    self,
    document_ids: List[str],
    failed_node: str,
    priority: int = 1
) -> List[ReReplicationTask]:
    """Queue multiple documents for re-replication."""
    tasks = []
    for doc_id in document_ids:
        task = self.queue_re_replication(doc_id, failed_node, priority)
        tasks.append(task)
    
    logger.info(f"Queued {len(tasks)} documents for re-replication")
    return tasks
```

## Proceso de Re-Replicación

```
Algorithm: Re-Replication Process
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FOR EACH document IN pending_tasks (ordenado por prioridad):

  1. ENCONTRAR fuente (réplica sana)
     source = find_healthy_replica(document)
     IF source == None:
       mark_task_failed("No healthy replica")
       CONTINUE

  2. SELECCIONAR destino
     current_nodes = get_current_replica_nodes(document)
     available = cluster_nodes - current_nodes - failed_nodes
     
     # Usar afinidad semántica si es posible
     target = select_best_node(document, available)
     IF target == None:
       mark_task_failed("No available target")
       CONTINUE

  3. EJECUTAR replicación
     TRY:
       success = await replicate(document, source, target)
       IF success:
         mark_task_completed()
       ELSE:
         retry_or_fail()
     CATCH error:
       retry_or_fail()

  4. ACTUALIZAR tracker de réplicas
     replica_tracker.add_replica(document, target)
```

## Priorización

| Prioridad | Valor | Situación |
|-----------|-------|------------|
| CRITICAL | 3 | Sin réplicas (única copia perdida) |
| HIGH | 2 | Bajo factor de replicación |
| NORMAL | 1 | Optimización de ubicación |

## Servicio de Recuperación

**Ubicación:** `backend/app/core/recovery/recovery_service.py`

```python
class RecoveryService:
    """
    Coordinates failure detection and recovery.
    
    Workflow on node failure:
    1. Detect failure via missed heartbeats
    2. Assess impact (which documents affected)
    3. Promote replicas to primary where needed
    4. Re-replicate to maintain replication factor
    5. Verify recovery complete
    """
    
    async def _execute_recovery(self, task: RecoveryTask) -> None:
        # Phase 1: Assessment
        task.phase = RecoveryPhase.ASSESSMENT
        await asyncio.sleep(self.config.assessment_delay_sec)
        
        affected_docs = await self._assess_impact(task.failed_node)
        task.affected_documents = affected_docs
        
        if not affected_docs:
            task.phase = RecoveryPhase.COMPLETED
            return
        
        # Phase 2: Promotion
        task.phase = RecoveryPhase.PROMOTION
        await self._promote_replicas(task)
        
        # Phase 3: Re-replication
        task.phase = RecoveryPhase.RE_REPLICATION
        await self._queue_re_replications(task)
        
        # Phase 4: Verification
        task.phase = RecoveryPhase.VERIFICATION
        await self._verify_recovery(task)
        
        task.phase = RecoveryPhase.COMPLETED
```

## Promoción de Réplicas

Cuando el nodo fallido era primario:

```python
async def _promote_replicas(self, task: RecoveryTask) -> None:
    """
    Promote replicas to primary where the failed node was primary.
    """
    for doc_id in task.affected_documents:
        try:
            replica_info = await self._get_replica_info(doc_id)
            if not replica_info:
                continue
            
            # Verificar si el nodo fallido era primario
            primary = replica_info.get("primary")
            if primary != task.failed_node:
                continue
            
            # Encontrar réplica sana para promover
            replicas = replica_info.get("replicas", [])
            healthy_replicas = [
                r for r in replicas
                if r.get("status") == "active" and r.get("node") != task.failed_node
            ]
            
            if healthy_replicas:
                new_primary = healthy_replicas[0]["node"]
                
                if self._promote_func:
                    success = await self._promote_func(doc_id, new_primary)
                    if success:
                        task.promoted_primaries[doc_id] = new_primary
                        logger.info(f"Promoted {new_primary} to primary for {doc_id}")
        
        except Exception as e:
            logger.error(f"Failed to promote replica for {doc_id}: {e}")
```

## Verificación de Recuperación

```python
async def _verify_recovery(self, task: RecoveryTask) -> None:
    """
    Verify that recovery is complete.
    """
    timeout = self.config.verification_timeout_sec
    start = datetime.utcnow()
    
    # Esperar a que se completen las re-replicaciones
    while (datetime.utcnow() - start).total_seconds() < timeout:
        pending = self.re_replication_mgr.get_pending_count()
        active = self.re_replication_mgr.get_active_count()
        
        if pending == 0 and active == 0:
            break
        
        await asyncio.sleep(2.0)
    
    # Obtener estadísticas
    stats = self.re_replication_mgr.get_statistics()
    task.documents_recovered = stats["total_completed"]
    task.documents_failed = stats["total_failed"]
```

## Ejemplo de Recuperación Completa

```
Escenario: Nodo_3 falla con 500 documentos
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

T=0s:   Heartbeat de Nodo_3 no recibido
T=5s:   Segundo heartbeat perdido → SUSPECT
T=10s:  Tercer heartbeat perdido → FAILED

T=10s:  RecoveryService.on_failure() llamado

T=12s:  Assessment completado
        affected_documents = 500
        primaries_on_failed = 180
        replicas_on_failed = 320

T=12s-15s: Promoción de 180 réplicas a primario

T=15s-45s: Re-replicación de 500 documentos
           batch_size = 20
           max_concurrent = 5
           ~25 batches, ~6 segundos/batch

T=45s:  Verificación completada
        documents_recovered = 498
        documents_failed = 2

T=45s:  Recovery COMPLETED
```

---

**Navegación:**
- [← Anterior: Detección de Fallos](01_Deteccion_Fallos.md)
- [→ Siguiente: Recuperación de Nodos](03_Recuperacion_Nodos.md)
