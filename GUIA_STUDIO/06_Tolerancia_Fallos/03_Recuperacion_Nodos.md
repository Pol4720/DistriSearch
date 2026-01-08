# Recuperación de Nodos

## Concepto

Cuando un nodo que había fallado vuelve a estar disponible, debe **reintegrarse** al cluster de forma ordenada. Este proceso incluye:

1. Detección de recuperación
2. Sincronización de estado
3. Reintegración en VP-Tree
4. Posible redistribución de documentos

## Detección de Recuperación

```
┌──────────────────────────────────────────────────────────────────────┐
│                  RECUPERACIÓN DE NODO                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ANTES (Nodo_3 caído):                                             │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│   │ Nodo_1  │  │ Nodo_2  │  │ Nodo_3  │  │ Nodo_4  │               │
│   │ HEALTHY │  │ HEALTHY │  │ FAILED  │  │ HEALTHY │               │
│   └─────────┘  └─────────┘  └────╳────┘  └─────────┘               │
│                                                                      │
│   DURANTE (Nodo_3 vuelve):                                          │
│   ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌─────────┐             │
│   │ Nodo_1  │  │ Nodo_2  │  │  Nodo_3   │  │ Nodo_4  │             │
│   │ HEALTHY │  │ HEALTHY │  │RECOVERING │  │ HEALTHY │             │
│   └─────────┘  └─────────┘  └───────────┘  └─────────┘             │
│                                  │                                   │
│                                  ▼                                   │
│                         Sincronizar estado                          │
│                         Unirse a VP-Tree                            │
│                         Recibir documentos                          │
│                                  │                                   │
│                                  ▼                                   │
│   DESPUÉS (Nodo_3 integrado):                                       │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│   │ Nodo_1  │  │ Nodo_2  │  │ Nodo_3  │  │ Nodo_4  │               │
│   │ HEALTHY │  │ HEALTHY │  │ HEALTHY │  │ HEALTHY │               │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Flujo de Recuperación en FailureDetector

```python
def record_heartbeat(
    self,
    node_id: str,
    latency_ms: float = 0.0,
    metadata: Optional[Dict] = None
) -> None:
    """Record a heartbeat from a node."""
    health = self._nodes[node_id]
    was_failed = health.status == NodeStatus.FAILED
    
    # Actualizar estado
    health.last_heartbeat = datetime.utcnow()
    health.consecutive_failures = 0
    health.status = NodeStatus.HEALTHY
    
    # Detectar recuperación
    if was_failed:
        self._failed_nodes.discard(node_id)
        health.status = NodeStatus.RECOVERING  # Estado transitorio
        logger.info(f"Node {node_id} recovered")
        
        # Disparar callback de recuperación
        if self._on_recovery:
            asyncio.create_task(self._on_recovery(node_id))
```

## Proceso de Reintegración

```
┌─────────────────────────────────────────────────────────────────────┐
│                FASES DE REINTEGRACIÓN                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   FASE 1: Registro                                                  │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │ 1. Nodo envía heartbeat con metadata                    │      │
│   │ 2. Master detecta nodo recuperado                       │      │
│   │ 3. Master registra nodo como RECOVERING                 │      │
│   └─────────────────────────────────────────────────────────┘      │
│                              │                                      │
│                              ▼                                      │
│   FASE 2: Sincronización de Estado                                 │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │ 1. Nodo solicita estado actual del cluster              │      │
│   │ 2. Recibe VP-Tree actual                                │      │
│   │ 3. Recibe lista de documentos asignados                 │      │
│   │ 4. Sincroniza UserDocumentRegistry via Gossip           │      │
│   └─────────────────────────────────────────────────────────┘      │
│                              │                                      │
│                              ▼                                      │
│   FASE 3: Verificación de Datos                                    │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │ 1. Verificar documentos locales                         │      │
│   │ 2. Reportar documentos disponibles al Master            │      │
│   │ 3. Identificar documentos faltantes/obsoletos           │      │
│   └─────────────────────────────────────────────────────────┘      │
│                              │                                      │
│                              ▼                                      │
│   FASE 4: Reintegración al VP-Tree                                 │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │ 1. Master recalcula VP-Tree incluyendo nodo             │      │
│   │ 2. Posible rebalanceo hacia el nodo recuperado          │      │
│   │ 3. Nodo comienza a recibir consultas                    │      │
│   └─────────────────────────────────────────────────────────┘      │
│                              │                                      │
│                              ▼                                      │
│   FASE 5: Estado HEALTHY                                           │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │ Nodo completamente operacional                          │      │
│   └─────────────────────────────────────────────────────────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Sincronización via Gossip

El protocolo Gossip ayuda en la sincronización:

```
┌──────────────────────────────────────────────────────────────────────┐
│                  GOSSIP SYNC DURANTE RECUPERACIÓN                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Nodo_3 (recuperado)          Nodo_1, Nodo_2, Nodo_4               │
│          │                              │                            │
│          │   "¿Qué me perdí?"          │                            │
│          ├─────────────────────────────▶│                            │
│          │                              │                            │
│          │   UserDocumentRegistry       │                            │
│          │◀─────────────────────────────┤                            │
│          │                              │                            │
│          │   Cluster State              │                            │
│          │◀─────────────────────────────┤                            │
│          │                              │                            │
│          │   VP-Tree Updates            │                            │
│          │◀─────────────────────────────┤                            │
│          │                              │                            │
│          ▼                              │                            │
│   Estado sincronizado                   │                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Manejo de Datos Obsoletos

Cuando un nodo vuelve, puede tener datos obsoletos:

```python
async def handle_node_rejoin(self, node_id: str) -> None:
    """
    Handle a previously failed node rejoining.
    """
    # 1. Obtener documentos que el nodo cree tener
    claimed_docs = await self._get_node_documents(node_id)
    
    # 2. Verificar contra estado actual
    for doc_id in claimed_docs:
        current_replicas = await self._get_replica_info(doc_id)
        
        if current_replicas is None:
            # Documento fue eliminado mientras nodo estaba caído
            await self._notify_delete(node_id, doc_id)
            continue
        
        current_version = current_replicas.get("version", 0)
        node_version = await self._get_node_doc_version(node_id, doc_id)
        
        if node_version < current_version:
            # Versión obsoleta, sincronizar
            await self._sync_document(node_id, doc_id)
```

## Escenarios de Recuperación

### Escenario 1: Recuperación Rápida (<1 minuto)

```
- Nodo reiniciado por actualizaciones
- Datos locales intactos
- Solo necesita sincronizar estado
- Documentos válidos, sin re-replicación necesaria
```

### Escenario 2: Recuperación Media (1-10 minutos)

```
- Nodo caído por problema transitorio
- Datos locales intactos pero posiblemente obsoletos
- Re-replicación ya ocurrió para algunos documentos
- Necesita reconciliar réplicas duplicadas
```

### Escenario 3: Recuperación Larga (>10 minutos) o Nuevo Nodo

```
- Nodo reemplazado o datos perdidos
- Sin documentos locales
- Actúa como nodo completamente nuevo
- Recibe documentos via rebalanceo
```

## Rebalanceo Post-Recuperación

Cuando un nodo vuelve, puede disparar rebalanceo:

```python
async def on_node_rejoin(self, node_id: str) -> None:
    """
    Handle node rejoining the cluster.
    """
    # 1. Marcar como HEALTHY
    self.failure_detector.record_heartbeat(node_id)
    
    # 2. Verificar si hay desbalance
    summary = self.load_calculator.calculate_cluster_summary()
    
    # El nodo recuperado probablemente tiene pocos documentos
    # (fueron redistribuidos mientras estaba caído)
    node_load = summary.get_node_load(node_id)
    avg_load = summary.avg_load_factor
    
    if node_load < avg_load * 0.5:  # Significativamente bajo carga
        # Disparar rebalanceo para redistribuir hacia el nodo
        await self.active_rebalancer.execute_rebalance()
```

## Diagrama de Estados Completo

```
               ┌─────────────────────────────────────────────────┐
               │                                                 │
    ┌──────────▼──────────┐                                      │
    │      UNKNOWN        │──────────────────────────────────┐   │
    └──────────┬──────────┘                                  │   │
               │ heartbeat                                   │   │
               ▼                                             │   │
    ┌──────────────────────┐                                 │   │
┌──▶│       HEALTHY        │◀────────────────────────┐       │   │
│   └──────────┬───────────┘                         │       │   │
│              │ 2 missed                            │       │   │
│              ▼                                     │       │   │
│   ┌──────────────────────┐                         │       │   │
│   │       SUSPECT        │─────────────────────────┤       │   │
│   └──────────┬───────────┘    heartbeat            │       │   │
│              │ 3 missed                            │       │   │
│              ▼                                     │       │   │
│   ┌──────────────────────┐                         │       │   │
│   │        FAILED        │                         │       │   │
│   └──────────┬───────────┘                         │       │   │
│              │ heartbeat                           │       │   │
│              ▼                                     │       │   │
│   ┌──────────────────────┐                         │       │   │
│   │     RECOVERING       │─────────────────────────┘       │   │
│   └──────────┬───────────┘                                 │   │
│              │ sync complete                               │   │
│              │                                             │   │
└──────────────┘                                             │   │
                                                             │   │
       ┌─────────────────────────────────────────────────────┘   │
       │  timeout sin heartbeat                                  │
       └─────────────────────────────────────────────────────────┘
```

## Troubleshooting de Recuperación

Problemas comunes de la guía de despliegue:

| Problema | Causa | Solución |
|----------|-------|----------|
| Nodo no se reintegra | Red aislada | Verificar conectividad |
| Datos inconsistentes | Partición larga | Forzar sincronización |
| Rebalanceo lento | Muchos documentos | Aumentar batch_size |
| Documentos duplicados | Réplicas no limpiadas | Ejecutar cleanup |

---

**Navegación:**
- [← Anterior: Re-Replicación](02_Re_Replicacion.md)
- [→ Siguiente: Consenso Raft](../07_Consenso_Raft/README.md)
