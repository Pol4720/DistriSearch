# Factor de Replicación

## Concepto

El **factor de replicación** define cuántas copias de cada documento existen en el cluster. En DistriSearch, el valor por defecto es **2** (1 primario + 1 réplica).

## Configuración

```python
@dataclass
class ReplicationConfig:
    replication_factor: int = 2  # Total de copias
    # ...
```

$$copies = replication\_factor = primary + replicas$$

| Factor | Primario | Réplicas | Tolerancia |
|--------|----------|----------|------------|
| 1 | 1 | 0 | 0 fallos |
| 2 | 1 | 1 | 1 fallo |
| 3 | 1 | 2 | 2 fallos |

## Trade-offs

```
┌──────────────────────────────────────────────────────────────────────┐
│                    TRADE-OFFS DEL FACTOR DE REPLICACIÓN             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   FACTOR BAJO (1-2):                                                │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │ ✓ Menor uso de almacenamiento                               │    │
│   │ ✓ Escrituras más rápidas (menos réplicas a sincronizar)    │    │
│   │ ✗ Menor tolerancia a fallos                                 │    │
│   │ ✗ Mayor riesgo de pérdida de datos                          │    │
│   └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│   FACTOR ALTO (3+):                                                 │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │ ✓ Alta tolerancia a fallos (sobrevive a N-1 fallos)        │    │
│   │ ✓ Mejor disponibilidad de lectura                           │    │
│   │ ✗ Mayor uso de almacenamiento (factor × tamaño)            │    │
│   │ ✗ Escrituras más lentas (sincronizar más réplicas)         │    │
│   │ ✗ Mayor complejidad de consistencia                         │    │
│   └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Cálculo de Almacenamiento

$$storage\_total = \sum_{doc} size(doc) \times replication\_factor$$

**Ejemplo:**
- 10,000 documentos
- Tamaño promedio: 100 KB
- Factor = 2

$$storage = 10,000 \times 100 KB \times 2 = 2 GB$$

## Diversidad de Zonas de Fallo

No basta con tener réplicas; deben estar en **zonas de fallo diferentes**:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ZONAS DE FALLO                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   MAL: Réplicas en mismo rack                                       │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │   Rack_A                           Rack_B                   │    │
│   │   ┌─────────┬─────────┐           ┌─────────┬─────────┐    │    │
│   │   │ Nodo_1  │ Nodo_2  │           │ Nodo_3  │ Nodo_4  │    │    │
│   │   │ Doc_A●  │ Doc_A○  │           │         │         │    │    │
│   │   └─────────┴─────────┘           └─────────┴─────────┘    │    │
│   │                                                              │    │
│   │   Si Rack_A falla → Doc_A PERDIDO                           │    │
│   └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│   BIEN: Réplicas en racks diferentes                                │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │   Rack_A                           Rack_B                   │    │
│   │   ┌─────────┬─────────┐           ┌─────────┬─────────┐    │    │
│   │   │ Nodo_1  │ Nodo_2  │           │ Nodo_3  │ Nodo_4  │    │    │
│   │   │ Doc_A●  │         │           │ Doc_A○  │         │    │    │
│   │   └─────────┴─────────┘           └─────────┴─────────┘    │    │
│   │                                                              │    │
│   │   Si Rack_A falla → Doc_A aún disponible en Rack_B         │    │
│   └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Verificación de Tolerancia a Fallos

```python
def _ensures_fault_tolerance(
    self, 
    current_selection: List[str], 
    candidate: str
) -> bool:
    """Verifica que el candidato no esté en el mismo rack/zona."""
    candidate_zone = self._get_failure_zone(candidate)
    selected_zones = {self._get_failure_zone(n) for n in current_selection}
    return candidate_zone not in selected_zones
```

## Selección de Nodos para Réplicas

El algoritmo completo considera:

1. **Afinidad semántica** (documentos similares)
2. **Diversidad de zonas** (tolerancia a fallos)
3. **Carga del nodo** (balanceo)

```python
def select_replica_nodes(
    self, 
    doc_id: str, 
    source_node: str,
    doc_vector: AdaptiveDocumentVector
) -> List[str]:
    """
    Selecciona nodos para réplicas basándose en:
    1. Nodos que tienen documentos similares
    2. Diversidad geográfica/de fallos
    3. Carga actual
    """
    candidates = []
    
    # 1. Encontrar documentos similares y sus nodos
    similar_docs = self._find_similar_documents(doc_vector, top_k=10)
    
    node_affinity_scores = defaultdict(float)
    for sim_doc_id, similarity in similar_docs:
        sim_doc_node = self.partition_index.get_document(sim_doc_id).node_id
        if sim_doc_node != source_node:
            node_affinity_scores[sim_doc_node] += similarity
    
    # 2. Ordenar nodos por afinidad
    sorted_nodes = sorted(
        node_affinity_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # 3. Seleccionar top-k asegurando diversidad
    selected = []
    for node_id, affinity in sorted_nodes:
        if len(selected) >= self.replication_factor - 1:
            break
        if self._ensures_fault_tolerance(selected, node_id):
            selected.append(node_id)
    
    # 4. Completar con nodos menos cargados si faltan
    if len(selected) < self.replication_factor - 1:
        remaining = self._get_least_loaded_nodes(
            exclude=selected + [source_node],
            count=self.replication_factor - 1 - len(selected)
        )
        selected.extend(remaining)
    
    return selected
```

## Clase `ReplicaTracker`

Rastrea el estado de todas las réplicas:

```python
class ReplicaTracker:
    """
    Tracks all document replicas in the cluster.
    
    Provides:
    - Replica state management
    - Under-replication detection
    - Node-to-replica mapping
    - Version tracking for consistency
    """
    
    def __init__(self, default_replication_factor: int = 2):
        self.default_replication_factor = default_replication_factor
        
        self._documents: Dict[str, DocumentReplicas] = {}
        self._node_replicas: Dict[str, Set[str]] = defaultdict(set)
        self._under_replicated: Set[str] = set()  # Docs bajo factor
```

## Estados de Réplica

```python
class ReplicaStatus(Enum):
    ACTIVE = "active"      # Funcionando correctamente
    SYNCING = "syncing"    # Sincronizándose
    STALE = "stale"        # Desactualizada (versión vieja)
    FAILED = "failed"      # Nodo falló
    PENDING = "pending"    # Esperando creación
```

```
┌─────────────────────────────────────────────────────────────┐
│                   CICLO DE VIDA DE RÉPLICA                  │
└─────────────────────────────────────────────────────────────┘

    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │ PENDING │────►│ SYNCING │────►│ ACTIVE  │
    └─────────┘     └─────────┘     └────┬────┘
                                         │
                         ┌───────────────┼───────────────┐
                         │               │               │
                         ▼               ▼               ▼
                    ┌─────────┐    ┌─────────┐    ┌─────────┐
                    │  STALE  │    │ SYNCING │    │ FAILED  │
                    └────┬────┘    └─────────┘    └─────────┘
                         │
                         ▼
                    ┌─────────┐
                    │ ACTIVE  │
                    └─────────┘
```

## Detección de Sub-replicación

```python
@dataclass
class DocumentReplicas:
    document_id: str
    primary: Optional[ReplicaInfo] = None
    replicas: List[ReplicaInfo] = field(default_factory=list)
    replication_factor: int = 2
    
    @property
    def healthy_count(self) -> int:
        return sum(1 for r in self.all_replicas if r.is_healthy)
    
    @property
    def is_under_replicated(self) -> bool:
        return self.healthy_count < self.replication_factor
```

## Proceso de Re-replicación

Cuando se detecta sub-replicación:

```python
def _queue_replication(
    self,
    document_id: str,
    priority: ReplicationPriority = ReplicationPriority.NORMAL
) -> None:
    """Queue replication for an under-replicated document."""
    doc = self.replica_tracker.get_document_replicas(document_id)
    if not doc or not doc.is_under_replicated:
        return
    
    # Encontrar fuente (réplica sana)
    source_node = None
    for replica in doc.all_replicas:
        if replica.is_healthy:
            source_node = replica.node_id
            break
    
    if not source_node:
        logger.error(f"No healthy replica for {document_id}")
        return
    
    # Seleccionar nuevos nodos para réplicas
    current_nodes = set(doc.all_nodes)
    available = [n for n in self._cluster_nodes if n not in current_nodes]
    
    needed = doc.replication_factor - doc.healthy_count
    
    for target in available[:needed]:
        task = self._create_task(
            document_id=document_id,
            source_node=source_node,
            target_node=target,
            priority=priority
        )
        self._pending_tasks[task.task_id] = task
```

## Ejemplo Completo

```
Escenario: Documento nuevo "informe_anual.pdf" llega al cluster
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Configuracion:
  replication_factor = 2
  cluster_nodes = [Nodo_1, Nodo_2, Nodo_3, Nodo_4]
  zones = {Nodo_1: Rack_A, Nodo_2: Rack_A, Nodo_3: Rack_B, Nodo_4: Rack_B}

Paso 1: Documento llega a Nodo_1 (primario)
  primary_node = Nodo_1
  needed_replicas = 2 - 1 = 1

Paso 2: Calcular afinidad
  Vecinos similares:
    • informe_q1.pdf (sim=0.8) → Nodo_2
    • informe_q2.pdf (sim=0.75) → Nodo_3
    • resumen_anual.pdf (sim=0.6) → Nodo_2
  
  Afinidad:
    Nodo_2: 0.8 + 0.6 = 1.4
    Nodo_3: 0.75 = 0.75
    Nodo_4: 0.0 = 0.0

Paso 3: Verificar diversidad de zonas
  Nodo_1 (primario) → Rack_A
  Nodo_2 (mejor afinidad) → Rack_A ← MISMO RACK, RECHAZAR
  Nodo_3 (segunda afinidad) → Rack_B ✓ DIFERENTE RACK

Paso 4: Resultado
  Primario: Nodo_1 (Rack_A)
  Réplica:  Nodo_3 (Rack_B) ← Balanceado entre racks

Paso 5: Encolar tarea de replicación
  Task: Nodo_1 → Nodo_3 (informe_anual.pdf)
  Priority: NORMAL
```

## Métricas de Replicación

| Métrica | Descripción | Umbral |
|---------|-------------|--------|
| `under_replicated_count` | Docs con menos réplicas | 0 ideal |
| `total_replicas` | Total de réplicas | docs × factor |
| `sync_lag` | Retraso de sincronización | < 5 segundos |
| `failed_replicas` | Réplicas fallidas | 0 ideal |

---

**Navegación:**
- [← Anterior: Grafo de Similaridad](02_Grafo_Similaridad.md)
- [→ Siguiente: Tolerancia a Fallos](../06_Tolerancia_Fallos/README.md)
