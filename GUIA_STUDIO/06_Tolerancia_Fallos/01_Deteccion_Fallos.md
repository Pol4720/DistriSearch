# Detección de Fallos

## Concepto

La **detección de fallos** es el primer paso en la tolerancia a fallos. DistriSearch usa un sistema de **heartbeats** (latidos) para determinar si un nodo está funcionando.

## Mecanismo de Heartbeat

```
┌──────────────────────────────────────────────────────────────────────┐
│                    SISTEMA DE HEARTBEATS                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Master                                                             │
│     │                                                                │
│     │  "¿Estás vivo?"     cada 5 segundos                           │
│     ├────────────────────────────────────────▶ Slave_1              │
│     │                     ◀──────────────────  "Sí, aquí estoy"     │
│     │                                                                │
│     ├────────────────────────────────────────▶ Slave_2              │
│     │                     ◀──────────────────  "Sí, aquí estoy"     │
│     │                                                                │
│     ├────────────────────────────────────────▶ Slave_3              │
│     │                     ✗ Sin respuesta (timeout 15s)             │
│     │                                                                │
│     └─── Marcar Slave_3 como SUSPECT después de 2 fallos            │
│     └─── Marcar Slave_3 como FAILED después de 3 fallos             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Clase `FailureDetector`

**Ubicación:** `backend/app/core/recovery/failure_detector.py`

```python
class FailureDetector:
    """
    Detects node failures using heartbeat monitoring.
    
    Features:
    - Configurable heartbeat interval and timeout
    - Suspect state before declaring failure
    - Callback on failure detection
    - Recovery detection
    """
    
    def __init__(
        self,
        heartbeat_interval_sec: float = 5.0,
        failure_timeout_sec: float = 15.0,
        suspect_threshold: int = 2,
        failure_threshold: int = 3,
        on_failure: Optional[Callable[[FailureEvent], Awaitable[None]]] = None,
        on_recovery: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        self.heartbeat_interval = heartbeat_interval_sec
        self.failure_timeout = failure_timeout_sec
        self.suspect_threshold = suspect_threshold
        self.failure_threshold = failure_threshold
        self._on_failure = on_failure
        self._on_recovery = on_recovery
        
        self._nodes: Dict[str, NodeHealth] = {}
        self._failed_nodes: Set[str] = set()
```

## Estructura de Salud del Nodo

```python
@dataclass
class NodeHealth:
    """Health information for a node."""
    node_id: str
    status: NodeStatus = NodeStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    last_failure: Optional[datetime] = None
    recovery_attempts: int = 0
    latency_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    @property
    def time_since_heartbeat(self) -> Optional[timedelta]:
        if self.last_heartbeat:
            return datetime.utcnow() - self.last_heartbeat
        return None
    
    @property
    def is_healthy(self) -> bool:
        return self.status == NodeStatus.HEALTHY
```

## Registro de Heartbeat

```python
def record_heartbeat(
    self,
    node_id: str,
    latency_ms: float = 0.0,
    metadata: Optional[Dict] = None
) -> None:
    """Record a heartbeat from a node."""
    if node_id not in self._nodes:
        self.register_node(node_id, metadata)
    
    health = self._nodes[node_id]
    was_failed = health.status == NodeStatus.FAILED
    
    # Actualizar estado
    health.last_heartbeat = datetime.utcnow()
    health.consecutive_failures = 0
    health.latency_ms = latency_ms
    health.status = NodeStatus.HEALTHY
    
    # Detectar recuperación
    if was_failed:
        self._failed_nodes.discard(node_id)
        health.status = NodeStatus.RECOVERING
        logger.info(f"Node {node_id} recovered")
        
        if self._on_recovery:
            asyncio.create_task(self._on_recovery(node_id))
```

## Registro de Fallo

```python
def record_failure(self, node_id: str, error: str = "") -> None:
    """Record a failed health check for a node."""
    if node_id not in self._nodes:
        return
    
    health = self._nodes[node_id]
    health.consecutive_failures += 1
    health.last_failure = datetime.utcnow()
    
    # Actualizar estado basado en fallos consecutivos
    if health.consecutive_failures >= self.failure_threshold:  # 3
        if health.status != NodeStatus.FAILED:
            self._mark_failed(health, "threshold", error)
    elif health.consecutive_failures >= self.suspect_threshold:  # 2
        health.status = NodeStatus.SUSPECT
        logger.warning(f"Node {node_id} is suspect")
```

## Línea de Tiempo de Detección

```
Tiempo:    0s      5s      10s     15s     20s     25s
           │       │       │       │       │       │
           ▼       ▼       ▼       ▼       ▼       ▼
         
 Heartbeat: ✓       ✓       ✗       ✗       ✗       
 Status:   HEALTHY HEALTHY HEALTHY SUSPECT FAILED──────▶ Recovery
                                    │       │
                                    │       └─ on_failure() llamado
                                    │
                                    └─ 2 fallos consecutivos

Configuración:
  heartbeat_interval = 5s
  suspect_threshold = 2 (fallos)
  failure_threshold = 3 (fallos)
```

## Evento de Fallo

```python
@dataclass
class FailureEvent:
    """Represents a node failure event."""
    node_id: str
    detected_at: datetime
    last_healthy: Optional[datetime]
    failure_type: str  # "timeout", "error", "explicit"
    details: str = ""
    
    @property
    def downtime(self) -> Optional[timedelta]:
        if self.last_healthy:
            return self.detected_at - self.last_healthy
        return None
```

## Tipos de Fallos

| Tipo | Descripción | Ejemplo |
|------|-------------|----------|
| `timeout` | Heartbeat no recibido | Nodo sin respuesta |
| `error` | Error en health check | Conexión rechazada |
| `explicit` | Nodo reportó fallo | Shutdown graceful |

## Health Checks en Docker

Docker Swarm también realiza health checks:

```yaml
# docker-compose.yml
services:
  slave:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Endpoint /health

```python
# backend/app/api/endpoints.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "node_id": settings.NODE_ID,
        "version": settings.VERSION
    }
```

## Diagrama de Detección

```
┌─────────────────────────────────────────────────────────────────┐
│                  PROCESO DE DETECCIÓN                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. Monitor Loop                                               │
│      ┌──────────────────────────────────────────┐              │
│      │  while running:                          │              │
│      │    for node in nodes:                    │              │
│      │      if time_since_heartbeat > timeout:  │              │
│      │        record_failure(node)              │              │
│      │    sleep(heartbeat_interval)             │              │
│      └──────────────────────────────────────────┘              │
│                                                                 │
│   2. Recepción de Heartbeat                                    │
│      ┌──────────────────────────────────────────┐              │
│      │  on heartbeat(node_id):                  │              │
│      │    health.last_heartbeat = now()         │              │
│      │    health.consecutive_failures = 0       │              │
│      │    health.status = HEALTHY               │              │
│      └──────────────────────────────────────────┘              │
│                                                                 │
│   3. Timeout sin Heartbeat                                     │
│      ┌──────────────────────────────────────────┐              │
│      │  on timeout(node_id):                    │              │
│      │    health.consecutive_failures++         │              │
│      │    if failures >= 3:                     │              │
│      │      mark_failed(node_id)                │              │
│      │      trigger on_failure callback         │              │
│      └──────────────────────────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Ventajas del Estado SUSPECT

El estado intermedio SUSPECT evita falsos positivos:

- **Red temporal**: Un paquete perdido no dispara recuperación
- **Carga alta**: Nodo lento responde en siguiente ciclo
- **GC pause**: Pausa de garbage collection no es fallo real

---

**Navegación:**
- [← README](README.md)
- [→ Siguiente: Re-Replicación](02_Re_Replicacion.md)
