# 06. Tolerancia a Fallos

## Visión General

La **tolerancia a fallos** es la capacidad del sistema de continuar operando correctamente cuando uno o más componentes fallan. DistriSearch implementa múltiples capas de protección:

1. **Detección de fallos** via heartbeats
2. **Re-replicación automática** de datos
3. **Recuperación de nodos** al reincorporarse

## Arquitectura de Tolerancia a Fallos

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    SISTEMA DE TOLERANCIA A FALLOS                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│   │ FailureDetector │───▶│ RecoveryService │───▶│ReReplicationMgr │     │
│   │                 │    │                 │    │                 │     │
│   │ • Heartbeats    │    │ • Orquestación  │    │ • Cola tareas   │     │
│   │ • Timeouts      │    │ • Promoción     │    │ • Batch process │     │
│   │ • Status        │    │ • Verificación  │    │ • Retry logic   │     │
│   └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Flujo de Recuperación

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DETECTION  │────▶│ ASSESSMENT  │────▶│  PROMOTION  │────▶│RE-REPLICAT. │
│             │     │             │     │             │     │             │
│ Heartbeat   │     │ ¿Qué docs   │     │ Promover    │     │ Restaurar   │
│ timeout     │     │ afectados?  │     │ réplicas    │     │ factor rep. │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                                                                   ▼
                                                           ┌─────────────┐
                                                           │VERIFICATION │
                                                           │             │
                                                           │ Verificar   │
                                                           │ completitud │
                                                           └─────────────┘
```

## Componentes Principales

| Componente | Archivo | Responsabilidad |
|------------|---------|------------------|
| `FailureDetector` | `failure_detector.py` | Detecta fallos via heartbeats |
| `RecoveryService` | `recovery_service.py` | Orquesta el proceso de recuperación |
| `ReReplicationManager` | `re_replication.py` | Gestiona la re-replicación |

## Estados de Nodo

```python
class NodeStatus(Enum):
    HEALTHY = "healthy"       # Funcionando correctamente
    SUSPECT = "suspect"       # Posible fallo (2 heartbeats perdidos)
    FAILED = "failed"         # Fallo confirmado (3+ heartbeats perdidos)
    RECOVERING = "recovering" # Recuperándose después de fallo
    UNKNOWN = "unknown"       # Estado inicial
```

```
         ┌─────────┐
         │ UNKNOWN │
         └────┬────┘
              │ primer heartbeat
              ▼
         ┌─────────┐
    ┌───▶│ HEALTHY │◀───────────────┐
    │    └────┬────┘                │
    │         │ 2 heartbeats        │ heartbeat
    │         │ perdidos            │ recibido
    │         ▼                     │
    │    ┌─────────┐                │
    │    │ SUSPECT │────────────────┤
    │    └────┬────┘                │
    │         │ 3+ heartbeats       │
    │         │ perdidos            │
    │         ▼                     │
    │    ┌─────────┐                │
    │    │ FAILED  │                │
    │    └────┬────┘                │
    │         │ heartbeat           │
    │         │ recibido            │
    │         ▼                     │
    │    ┌───────────┐              │
    └────│RECOVERING │──────────────┘
         └───────────┘
```

## Fases de Recuperación

```python
class RecoveryPhase(Enum):
    DETECTION = "detection"          # Fallo detectado
    ASSESSMENT = "assessment"        # Evaluando impacto
    PROMOTION = "promotion"          # Promoviendo réplicas
    RE_REPLICATION = "re_replication" # Re-replicando datos
    VERIFICATION = "verification"    # Verificando completitud
    COMPLETED = "completed"          # Recuperación exitosa
    FAILED = "failed"                # Recuperación fallida
```

## Configuración

```python
@dataclass
class RecoveryConfig:
    # Detección de fallos
    heartbeat_interval_sec: float = 5.0    # Verificar cada 5s
    failure_timeout_sec: float = 15.0      # Timeout de 15s
    suspect_threshold: int = 2             # 2 fallos → suspect
    failure_threshold: int = 3             # 3 fallos → failed
    
    # Re-replicación
    max_concurrent_rereplications: int = 5
    re_replication_batch_size: int = 20
    re_replication_retry_limit: int = 3
    
    # Timing de recuperación
    assessment_delay_sec: float = 2.0      # Esperar estabilización
    verification_timeout_sec: float = 60.0  # Timeout verificación
```

## Contenido de Esta Sección

1. **[Detección de Fallos](01_Deteccion_Fallos.md)**: Heartbeats y timeouts
2. **[Re-Replicación](02_Re_Replicacion.md)**: Restaurar factor de replicación
3. **[Recuperación de Nodos](03_Recuperacion_Nodos.md)**: Reintegración al cluster

---

**Navegación:**
- [← Anterior: Replicación](../05_Replicacion/README.md)
- [→ Siguiente: Consenso Raft](../07_Consenso_Raft/README.md)
