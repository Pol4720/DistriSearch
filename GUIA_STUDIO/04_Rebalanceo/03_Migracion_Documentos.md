# Migración de Documentos

## Concepto

La **migración de documentos** es el proceso de transferir documentos de un nodo a otro durante el rebalanceo. DistriSearch implementa un sistema de migración robusto con:

- **Transferencias en batch** (50 docs/batch)
- **Rate limiting** (1 segundo entre batches)
- **Reintentos automáticos**
- **Seguimiento de progreso**

## Clase `MigrationHandler`

**Ubicación:** `backend/app/core/rebalancing/migration_handler.py`

```python
class MigrationHandler:
    """
    Handles document migrations between cluster nodes.
    
    Implements:
    - Batch transfers (50 docs/batch per architecture spec)
    - Rate limiting (1s sleep between batches)
    - Progress tracking
    - Retry logic
    - Cancellation support
    """
    
    def __init__(
        self,
        config: Optional[MigrationConfig] = None,
        transfer_func: Callable[[str, str, List[str]], Awaitable[Dict]] = None
    ):
        self.config = config or MigrationConfig()
        self._transfer_func = transfer_func
        self._tasks: Dict[str, MigrationTask] = {}
```

## Configuración de Migración

```python
@dataclass 
class MigrationConfig:
    """Configuration for migration operations."""
    batch_size: int = 50              # docs por batch (según especificación)
    batch_delay_sec: float = 1.0      # sleep entre batches
    max_concurrent_batches: int = 1   # una migración a la vez
    max_retries: int = 3              # reintentos por batch fallido
    retry_delay_sec: float = 5.0      # espera antes de reintentar
    transfer_timeout_sec: float = 30.0 # timeout por transferencia
```

## Proceso de Migración Paso a Paso

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE MIGRACIÓN                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. CREAR TAREA                                                     │
│     ┌─────────────────────────────────────────────────────────┐     │
│     │ MigrationTask(                                          │     │
│     │   task_id="mig_abc123",                                 │     │
│     │   source_node="node_1",                                 │     │
│     │   target_node="node_4",                                 │     │
│     │   document_ids=["doc1", "doc2", ..., "doc200"]          │     │
│     │ )                                                       │     │
│     └─────────────────────────────────────────────────────────┘     │
│                              ↓                                      │
│  2. DIVIDIR EN BATCHES                                              │
│     ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐        │
│     │ Batch 1   │ │ Batch 2   │ │ Batch 3   │ │ Batch 4   │        │
│     │ 50 docs   │ │ 50 docs   │ │ 50 docs   │ │ 50 docs   │        │
│     └───────────┘ └───────────┘ └───────────┘ └───────────┘        │
│                              ↓                                      │
│  3. EJECUTAR BATCH + RATE LIMITING                                  │
│                                                                     │
│     Batch 1 ───[transfer]───▶ OK                                    │
│         │                                                           │
│         └── sleep(1.0s) ──┐                                         │
│                           │                                         │
│     Batch 2 ◀─────────────┘                                         │
│         │                                                           │
│         ├── [transfer] ──▶ FAIL ──▶ retry (3 intentos)              │
│         │                                                           │
│         └── sleep(1.0s) ──┐                                         │
│                           │                                         │
│     Batch 3 ◀─────────────┘                                         │
│         │                                                           │
│         ... (continúa)                                              │
│                              ↓                                      │
│  4. RESULTADO FINAL                                                 │
│     ┌─────────────────────────────────────────────────────────┐     │
│     │ MigrationResult(                                        │     │
│     │   success=True,                                         │     │
│     │   documents_migrated=195,                               │     │
│     │   documents_failed=5,                                   │     │
│     │   duration_sec=8.5                                      │     │
│     │ )                                                       │     │
│     └─────────────────────────────────────────────────────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Estructura de la Tarea de Migración

```python
@dataclass
class MigrationTask:
    """Represents a document migration task."""
    task_id: str
    source_node: str
    target_node: str
    document_ids: List[str]
    status: MigrationStatus = MigrationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0                # 0.0 a 1.0
    documents_migrated: int = 0
    documents_failed: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def total_documents(self) -> int:
        return len(self.document_ids)
    
    @property
    def is_complete(self) -> bool:
        return self.status in (
            MigrationStatus.COMPLETED, 
            MigrationStatus.FAILED, 
            MigrationStatus.CANCELLED
        )
```

## Estados de Migración

```python
class MigrationStatus(Enum):
    PENDING = "pending"         # Creada, esperando ejecución
    IN_PROGRESS = "in_progress" # Ejecutándose
    COMPLETED = "completed"     # Terminada exitosamente
    FAILED = "failed"           # Falló (agotó reintentos)
    CANCELLED = "cancelled"     # Cancelada manualmente
    PAUSED = "paused"           # Pausada
```

```
    ┌─────────┐     ┌─────────────┐     ┌───────────┐
    │ PENDING │────▶│ IN_PROGRESS │────▶│ COMPLETED │
    └─────────┘     └──────┬──────┘     └───────────┘
                           │
                           ├────────────▶ FAILED
                           │
                           ├────────────▶ CANCELLED
                           │
                           └────────────▶ PAUSED ──▶ IN_PROGRESS
```

## Ejecución con Rate Limiting

```python
async def _execute_migration(self, task: MigrationTask) -> MigrationResult:
    """Execute the actual migration with batching and rate limiting."""
    failed_docs = []
    
    # Dividir en batches de 50
    batches = [
        task.document_ids[i:i + self.config.batch_size]
        for i in range(0, len(task.document_ids), self.config.batch_size)
    ]
    
    total_batches = len(batches)
    logger.info(f"Task {task.task_id}: {total_batches} batches")
    
    for batch_idx, batch in enumerate(batches):
        # Verificar cancelación
        if task.task_id in self._cancelled:
            task.status = MigrationStatus.CANCELLED
            break
        
        # Ejecutar transferencia del batch
        try:
            batch_result = await self._transfer_batch(
                task.source_node,
                task.target_node,
                batch
            )
            
            task.documents_migrated += len(batch_result.get("migrated", []))
            task.documents_failed += len(batch_result.get("failed", []))
            
        except Exception as e:
            # Lógica de reintentos
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                await asyncio.sleep(self.config.retry_delay_sec)  # 5s
                # Reintentar...
            else:
                task.documents_failed += len(batch)
        
        # Actualizar progreso
        task.progress = (batch_idx + 1) / total_batches
        
        # RATE LIMITING: sleep entre batches
        if batch_idx < total_batches - 1:
            await asyncio.sleep(self.config.batch_delay_sec)  # 1s
    
    # Finalizar
    task.completed_at = datetime.utcnow()
    return MigrationResult(...)
```

## Selección de Documentos "Frontera"

Los documentos candidatos a migración son aquellos en el **borde** de la partición: los más alejados del vantage point actual.

```
┌──────────────────────────────────────────────────────────────────┐
│                SELECCIÓN DE DOCUMENTOS FRONTERA                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│                           Nodo_1                                  │
│                                                                   │
│                            ★ VP                                   │
│                         ·  │  ·                                   │
│                      ·     │     ·                                │
│                   ·  ●     │     ●  ·       ● Documentos          │
│                ·    ●  ●   │   ●  ●    ·    cercanos al VP       │
│              ·      ● ●●●  │  ●●● ●      ·   (NO migrar)          │
│             ·        ●●●●  │  ●●●●        ·                       │
│            ·           ●●● │ ●●●           ·                      │
│           ·              ●●│●●              ·                     │
│          ·                 │                 ·                    │
│         ·       ○          │          ○       ·   ○ Documentos    │
│        ·     ○    ○        │        ○    ○     ·    FRONTERA      │
│       ·   ○          ○     │     ○          ○   ·   (MIGRAR)      │
│      ·  ○              ○   │   ○              ○  ·                │
│     · ○                    │                    ○ ·               │
│                                                                   │
│     Los documentos ○ están más lejos del VP y son candidatos     │
│     ideales para migrar al nuevo nodo                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

```python
def _get_documents_to_migrate(
    self, 
    node_id: str, 
    target_count: int,
    prefer_similar_to_new_vp: bool = True
) -> List[Document]:
    """Selecciona documentos para migrar usando criterio de frontera."""
    docs = self.partition_index.get_documents_in_node(node_id)
    vp = self.vantage_points[node_id]
    
    # Ordenar por distancia al VP (los más lejanos son candidatos)
    docs.sort(key=lambda d: d.compute_distance(vp), reverse=True)
    
    return docs[:target_count]
```

## Replicación Temporal Durante Transferencia

Para garantizar disponibilidad durante la migración:

```
┌────────────────────────────────────────────────────────────────┐
│              MIGRACIÓN CON REPLICACIÓN TEMPORAL                 │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ESTADO INICIAL:                                               │
│   ┌──────────┐                                                  │
│   │  Nodo_1  │  Doc_A (primario)                               │
│   └──────────┘                                                  │
│   ┌──────────┐                                                  │
│   │  Nodo_2  │  Doc_A (réplica)                                │
│   └──────────┘                                                  │
│                                                                 │
│   DURANTE MIGRACIÓN:                                            │
│   ┌──────────┐                                                  │
│   │  Nodo_1  │  Doc_A (primario) ─┐                            │
│   └──────────┘                    │ copiando                   │
│   ┌──────────┐                    ▼                            │
│   │  Nodo_4  │  Doc_A (temporal)                               │
│   └──────────┘                                                  │
│   ┌──────────┐                                                  │
│   │  Nodo_2  │  Doc_A (réplica)  ← mantener hasta confirmar    │
│   └──────────┘                                                  │
│                                                                 │
│   DESPUÉS DE MIGRACIÓN:                                         │
│   ┌──────────┐                                                  │
│   │  Nodo_4  │  Doc_A (nuevo primario) ✓                       │
│   └──────────┘                                                  │
│   ┌──────────┐                                                  │
│   │  Nodo_2  │  Doc_A (réplica)  ← puede mantenerse o          │
│   └──────────┘                     reasignarse                  │
│   ┌──────────┐                                                  │
│   │  Nodo_1  │  (Doc_A eliminado después de confirmación)      │
│   └──────────┘                                                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

## Actualización de Índices

Después de cada migración exitosa:

1. **Actualizar VP-Tree**: El documento ahora pertenece a otra partición
2. **Actualizar routing table**: Las consultas deben ir al nuevo nodo
3. **Invalidar caché**: Si hay búsquedas cacheadas que incluían el documento
4. **Notificar réplicas**: Las réplicas deben saber la nueva ubicación

## Impacto en Disponibilidad de Búsqueda

| Fase | Disponibilidad | Notas |
|------|---------------|-------|
| Pre-migración | 100% | Normal |
| Durante copia | 100% | Doc disponible en origen |
| Verificación | 100% | Doc en ambos nodos |
| Eliminación origen | 100% | Doc solo en destino |

**La búsqueda nunca se interrumpe** gracias a la replicación temporal.

## Estadísticas de Migración

```python
def get_statistics(self) -> Dict[str, Any]:
    """Get migration statistics."""
    active = self.get_active_tasks()
    completed = [t for t in self._tasks.values() 
                 if t.status == MigrationStatus.COMPLETED]
    failed = [t for t in self._tasks.values() 
              if t.status == MigrationStatus.FAILED]
    
    return {
        "total_tasks": len(self._tasks),
        "active_tasks": len(active),
        "completed_tasks": len(completed),
        "failed_tasks": len(failed),
        "total_documents_migrated": self._total_migrated,
        "total_documents_failed": self._total_failed,
        "success_rate": self._total_migrated / 
                        (self._total_migrated + self._total_failed)
    }
```

## Ejemplo de Migración Completa

```
Ejemplo: Migrar 200 documentos de Nodo_1 a Nodo_4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Configuración:
  batch_size = 50
  batch_delay = 1.0s
  max_retries = 3

Ejecución:
  Batch 1: docs[0:50]   → OK (0.5s)
  [sleep 1.0s]
  Batch 2: docs[50:100] → FAIL → retry → OK (5.5s + 0.5s)
  [sleep 1.0s]
  Batch 3: docs[100:150] → OK (0.5s)
  [sleep 1.0s]
  Batch 4: docs[150:200] → OK (0.5s)

Tiempo total: 0.5 + 1 + 6 + 1 + 0.5 + 1 + 0.5 = ~10.5 segundos

Resultado:
  ✓ 200 documentos migrados
  ✓ 0 documentos fallidos
  ✓ 1 reintento realizado
```

---

**Navegación:**
- [← Anterior: Power of Two Choices](02_Power_Two_Choices.md)
- [→ Siguiente: Replicación](../05_Replicacion/README.md)
