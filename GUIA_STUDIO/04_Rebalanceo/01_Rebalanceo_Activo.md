# Rebalanceo Activo

## Concepto

El **rebalanceo activo** es un mecanismo proactivo que redistribuye documentos entre nodos del clúster para mantener una carga equilibrada. A diferencia del rebalanceo reactivo (que solo actúa ante fallos), el activo monitorea continuamente y actúa preventivamente.

## Clase `ActiveRebalancer`

**Ubicación:** `backend/app/core/rebalancing/active_rebalancer.py`

```python
class ActiveRebalancer:
    """
    Actively monitors and rebalances cluster load.
    
    Features:
    - Continuous load monitoring
    - Automatic rebalance triggering
    - Coordinated migrations with rate limiting
    - Operation history tracking
    """
    
    def __init__(
        self,
        config: Optional[RebalanceConfig] = None,
        document_selector: Callable[[str, int], Awaitable[List[str]]] = None,
        transfer_func: Callable[[str, str, List[str]], Awaitable[Dict]] = None
    ):
        self.config = config or RebalanceConfig()
        self.load_calculator = LoadCalculator(
            imbalance_threshold=self.config.imbalance_threshold,
            critical_threshold=self.config.critical_threshold,
            min_transfer_size=self.config.min_documents_to_move
        )
        self.migration_handler = MigrationHandler(...)
```

## Configuración de Rebalanceo

```python
@dataclass
class RebalanceConfig:
    """Configuration for rebalancing."""
    # Umbrales
    imbalance_threshold: float = 0.2      # Desviación estándar máxima
    critical_threshold: float = 0.9        # Factor de carga crítico
    min_documents_to_move: int = 10        # Mínimo para justificar migración
    
    # Timing
    check_interval_sec: float = 60.0       # Verificar cada 60 segundos
    cooldown_after_rebalance_sec: float = 300.0  # 5 min de cooldown
    
    # Configuración de migración (según arquitectura)
    batch_size: int = 50                   # 50 docs por batch
    batch_delay_sec: float = 1.0           # 1 segundo entre batches
    max_concurrent_migrations: int = 2     # Máximo 2 migraciones paralelas
    
    # Límites
    max_documents_per_rebalance: int = 1000  # Máximo por operación
    max_duration_sec: float = 3600.0         # Máximo 1 hora
```

## Eventos Disparadores

### 1. Nuevo Nodo se Une (`on_node_join`)

```
┌──────────────────────────────────────────────────────────────┐
│              PROCESO DE REBALANCEO (NODE_JOIN)               │
├──────────────────────────────────────────────────────────────┤
│ 1. Nuevo nodo N₄ se une al cluster                          │
│                                                              │
│ 2. Master calcula nuevo VP-Tree con N₄                      │
│    - N₄ recibe un "vantage point" inicial (centroide vacío) │
│                                                              │
│ 3. Identificar documentos candidatos a migrar:              │
│    - Docs en nodos sobrecargados (>120% promedio)           │
│    - Docs cuyo VP más cercano ahora es N₄                   │
│                                                              │
│ 4. Migración gradual (no disruptiva):                       │
│    - Priorizar docs más cercanos al nuevo VP                │
│    - Transferir en batches de 50 docs                       │
│    - Mantener réplica temporal hasta confirmar              │
│                                                              │
│ 5. Actualizar índices y vantage points                      │
└──────────────────────────────────────────────────────────────┘
```

### 2. Nodo Abandona (`on_node_leave`)

Cuando un nodo abandona voluntariamente (shutdown graceful):

```python
async def on_node_leave(self, leaving_node_id: str):
    # 1. Obtener documentos del nodo que se va
    docs_to_redistribute = self._get_documents_in_node(leaving_node_id)
    
    # 2. Para cada documento, encontrar mejor nodo destino
    for doc in docs_to_redistribute:
        target = self._find_best_node(doc, exclude=[leaving_node_id])
        await self._migrate_document(doc, leaving_node_id, target)
    
    # 3. Actualizar VP-Tree sin el nodo
    self._recompute_vantage_points()
```

### 3. Desbalance de Carga

Detectado automáticamente por el monitor:

```python
async def _check_and_rebalance(self) -> None:
    """Check load and trigger rebalance if needed."""
    if self._status != RebalanceStatus.IDLE:
        return
    
    if self.is_in_cooldown:  # Evitar rebalanceos consecutivos
        return
    
    needs_rebalance, reason = self.load_calculator.needs_rebalancing()
    
    if needs_rebalance:
        logger.info(f"Rebalance triggered: {reason}")
        await self.execute_rebalance()
```

## Estados del Rebalanceo

```python
class RebalanceStatus(Enum):
    IDLE = "idle"           # Sin actividad
    ANALYZING = "analyzing"  # Analizando métricas
    PLANNING = "planning"    # Generando plan
    EXECUTING = "executing"  # Ejecutando migraciones
    COMPLETED = "completed"  # Completado
    FAILED = "failed"        # Falló
    PAUSED = "paused"        # Pausado manualmente
```

```
        ┌───────────────────────────────────────────────────┐
        │                                                   │
        ▼                                                   │
    ┌──────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
    │ IDLE │────▶│ ANALYZING │────▶│ PLANNING │────▶│EXECUTING │
    └──────┘     └───────────┘     └──────────┘     └────┬─────┘
        ▲                                                │
        │                                                │
        │        ┌───────────┐                           │
        └────────│ COMPLETED │◀──────────────────────────┤
                 └───────────┘                           │
                                                         │
                 ┌───────────┐                           │
                 │  FAILED   │◀──────────────────────────┘
                 └───────────┘
```

## Proceso de Ejecución Completo

```python
async def execute_rebalance(self) -> RebalanceOperation:
    """Execute a rebalance operation."""
    self._operation_counter += 1
    operation = RebalanceOperation(
        operation_id=f"rebal_{self._operation_counter}",
        status=RebalanceStatus.ANALYZING,
        started_at=datetime.utcnow()
    )
    
    try:
        # FASE 1: Analizar cluster
        logger.info(f"Operation {operation.operation_id}: Analyzing cluster")
        summary = self.load_calculator.calculate_cluster_summary()
        
        # FASE 2: Generar plan
        self._status = RebalanceStatus.PLANNING
        decisions = self.load_calculator.generate_rebalance_plan()
        
        if not decisions:
            logger.info("No rebalance needed after analysis")
            operation.status = RebalanceStatus.COMPLETED
            return operation
        
        # FASE 3: Ejecutar migraciones
        self._status = RebalanceStatus.EXECUTING
        
        for decision in decisions:
            result = await self._execute_decision(decision)
            operation.documents_moved += result.documents_migrated
        
        # FASE 4: Completar
        operation.status = RebalanceStatus.COMPLETED
        self._last_rebalance = datetime.utcnow()  # Inicia cooldown
        
    except Exception as e:
        operation.status = RebalanceStatus.FAILED
        operation.error_message = str(e)
    
    return operation
```

## Métricas de Carga (`LoadCalculator`)

```python
@dataclass
class LoadMetrics:
    """Load metrics for a single node."""
    node_id: str
    document_count: int
    capacity: int
    storage_used_bytes: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    query_rate: float = 0.0       # queries/segundo
    avg_latency_ms: float = 0.0
    is_healthy: bool = True
    
    @property
    def load_factor(self) -> float:
        """Document load factor (0-1)."""
        return self.document_count / self.capacity if self.capacity > 0 else 1.0
    
    @property
    def load_level(self) -> LoadLevel:
        """Categorize load level."""
        load = self.load_factor
        if load <= 0:
            return LoadLevel.EMPTY
        elif load < 0.4:
            return LoadLevel.LOW
        elif load < 0.75:
            return LoadLevel.NORMAL
        elif load < 0.9:
            return LoadLevel.HIGH
        else:
            return LoadLevel.CRITICAL
```

## Niveles de Carga

| Nivel | Rango | Acción |
|-------|-------|--------|
| `EMPTY` | 0% | Candidato a recibir documentos |
| `LOW` | <40% | Puede recibir más documentos |
| `NORMAL` | 40-75% | Estado ideal |
| `HIGH` | 75-90% | Considerar migrar documentos |
| `CRITICAL` | >90% | Migración urgente (prioridad alta) |

## Decisión de Rebalanceo

```python
def needs_rebalancing(self) -> Tuple[bool, str]:
    """Determine if cluster needs rebalancing."""
    summary = self.calculate_cluster_summary()
    
    if summary.node_count < 2:
        return False, "Insufficient nodes for rebalancing"
    
    if summary.healthy_nodes < 2:
        return False, "Insufficient healthy nodes"
    
    # Nodos en estado crítico → rebalanceo inmediato
    if summary.critical_nodes:
        return True, f"Critical load on nodes: {summary.critical_nodes}"
    
    # Alta desviación estándar → desbalance
    if summary.load_std_dev > self.imbalance_threshold:  # 0.2
        return True, f"Load imbalance detected (std_dev={summary.load_std_dev:.3f})"
    
    # Alta ratio de desbalance
    if summary.imbalance_ratio > 0.5:
        return True, f"High imbalance ratio: {summary.imbalance_ratio:.2f}"
    
    return False, "Cluster is balanced"
```

## Ejemplo Práctico

```
Situación Inicial:
━━━━━━━━━━━━━━━━━
Nodo_1: 3000 docs / 5000 cap = 60% (NORMAL)
Nodo_2: 4500 docs / 5000 cap = 90% (CRITICAL)
Nodo_3: 1500 docs / 5000 cap = 30% (LOW)
Nodo_4: 0 docs / 5000 cap = 0% (EMPTY)  ← Nuevo

Análisis:
━━━━━━━━
Total docs: 9000
Promedio ideal: 9000 / 4 = 2250 docs/nodo
std_dev = 1.56 > 0.2 → NECESITA REBALANCEO

Plan de Migración:
━━━━━━━━━━━━━━━━━
1. Nodo_2 → Nodo_4: 2250 docs (prioridad ALTA - crítico)
2. Nodo_1 → Nodo_4: 750 docs (prioridad NORMAL)
3. Nodo_1 → Nodo_3: 0 docs (ya equilibrado)

Resultado:
━━━━━━━━━
Nodo_1: 2250 docs (45% - NORMAL)
Nodo_2: 2250 docs (45% - NORMAL)
Nodo_3: 2250 docs (45% - NORMAL)
Nodo_4: 2250 docs (45% - NORMAL)
```

---

**Navegación:**
- [← README](README.md)
- [→ Siguiente: Power of Two Choices](02_Power_Two_Choices.md)
