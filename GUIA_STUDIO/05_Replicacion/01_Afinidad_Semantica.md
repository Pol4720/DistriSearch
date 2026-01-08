# Afinidad Semántica en Replicación

## Concepto

La **afinidad semántica** es el principio de colocar réplicas de documentos en nodos que ya contienen documentos similares. Esto crea "clusters semánticos" naturales que mejoran el rendimiento de búsqueda.

## ¿Por Qué Afinidad Semántica?

### Beneficios

| Beneficio | Descripción |
|-----------|-------------|
| **Mejor localidad de caché** | Documentos relacionados comparten caché |
| **Búsquedas más rápidas** | Menos nodos a consultar para queries similares |
| **Menor tráfico de red** | Resultados encontrados localmente |
| **Mejor tolerancia a fallos** | Documentos relacionados sobreviven juntos |

### Ejemplo Visual

```
┌──────────────────────────────────────────────────────────────────────┐
│                   AFINIDAD SEMÁNTICA EN ACCIÓN                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   DOCUMENTOS:                                                        │
│   • ventas_q1.xlsx (tema: ventas, finanzas)                         │
│   • ventas_q2.xlsx (tema: ventas, finanzas) ← Similar a q1         │
│   • marketing_2024.pdf (tema: marketing)                             │
│   • rrhh_nominas.xlsx (tema: recursos humanos)                       │
│                                                                      │
│   SIN AFINIDAD:                                                      │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │
│   │    Nodo_1     │  │    Nodo_2     │  │    Nodo_3     │           │
│   │ ventas_q1●    │  │ ventas_q2●    │  │ marketing●    │           │
│   │ rrhh○         │  │ marketing○    │  │ ventas_q1○    │           │
│   └───────────────┘  └───────────────┘  └───────────────┘           │
│   Búsqueda "ventas trimestre" → consultar Nodo_1 + Nodo_2 + Nodo_3 │
│                                                                      │
│   CON AFINIDAD:                                                      │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │
│   │    Nodo_1     │  │    Nodo_2     │  │    Nodo_3     │           │
│   │ ventas_q1●    │  │ marketing●    │  │ rrhh●         │           │
│   │ ventas_q2○    │  │              │  │               │           │
│   └───────────────┘  └───────────────┘  └───────────────┘           │
│   Búsqueda "ventas trimestre" → consultar solo Nodo_1              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Clase `AffinityReplicator`

**Ubicación:** `backend/app/core/replication/affinity_replicator.py`

```python
class AffinityReplicator:
    """
    Manages document replication with semantic affinity placement.
    
    Features:
    - Automatic replica placement based on document similarity
    - Background replication monitoring
    - Re-replication on node failure
    - Replica synchronization
    """
    
    def __init__(
        self,
        config: Optional[ReplicationConfig] = None,
        replicate_func: Optional[Callable] = None,
        get_document_vectors: Optional[Callable] = None
    ):
        self.config = config or ReplicationConfig()
        
        # Componentes
        self.similarity_graph = SimilarityGraph()
        self.replica_tracker = ReplicaTracker(
            default_replication_factor=self.config.replication_factor
        )
        
        # Cola de tareas
        self._pending_tasks: Dict[str, ReplicationTask] = {}
```

## Configuración

```python
@dataclass
class ReplicationConfig:
    """Configuration for replication."""
    replication_factor: int = 2           # Número de copias totales
    max_concurrent_replications: int = 5  # Máximo paralelo
    replication_timeout_sec: float = 60.0 # Timeout por réplica
    retry_count: int = 3                  # Reintentos
    retry_delay_sec: float = 5.0          # Espera entre reintentos
    sync_batch_size: int = 10             # Tamaño de batch
    check_interval_sec: float = 30.0      # Intervalo de verificación
```

## Proceso de Selección de Nodos Réplica

```python
async def _select_replica_nodes(
    self,
    document_id: str,
    primary_node: str,
    document_vectors: Optional[Dict[str, Any]]
) -> List[str]:
    """
    Select nodes for replicas using semantic affinity.
    """
    num_replicas = self.config.replication_factor - 1
    
    if num_replicas <= 0:
        return []
    
    # Excluir nodo primario
    available_nodes = [n for n in self._cluster_nodes if n != primary_node]
    
    if not available_nodes:
        logger.warning("No available nodes for replicas")
        return []
    
    # Si tenemos vectores y documentos existentes, usar afinidad
    if document_vectors and len(self.similarity_graph._nodes) > 0:
        # Encontrar nodos con documentos similares
        affinity_scores = self.similarity_graph.find_best_replica_nodes(
            document_id=document_id,
            candidate_nodes=available_nodes,
            num_replicas=num_replicas
        )
        
        if affinity_scores:
            return [node for node, _ in affinity_scores[:num_replicas]]
    
    # Fallback: selección round-robin
    return available_nodes[:num_replicas]
```

## Algoritmo de Selección

```
Algorithm: Select Replica Nodes with Affinity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT: document, primary_node, replication_factor
OUTPUT: lista de nodos para réplicas

1. num_replicas ← replication_factor - 1
2. available ← cluster_nodes - {primary_node}

3. IF document tiene vectores AND existe grafo de similaridad:
   4.   neighbors ← get_neighbors(document, limit=50)
   5.   FOR EACH candidate IN available:
   6.     affinity ← 0
   7.     FOR EACH (neighbor_id, similarity) IN neighbors:
   8.       IF neighbor_id está en candidate:
   9.         affinity ← affinity + similarity
  10.     END FOR
  11.     scores[candidate] ← affinity
  12.   END FOR
  13.   RETURN top num_replicas nodos por score

14. ELSE:
  15.   RETURN available[:num_replicas]  // Fallback
```

## Diagrama de Flujo

```
┌─────────────────┐
│ Nuevo documento │
│ llega a Nodo_1  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Calcular vectores del documento          │
│ (TF-IDF nombre, TF-IDF contenido, LDA)  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Buscar vecinos en SimilarityGraph       │
│ (documentos con alta similaridad)       │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Calcular afinidad por nodo:             │
│                                          │
│ Nodo_2: affinity = 0.8 + 0.7 = 1.5      │
│ Nodo_3: affinity = 0.3 = 0.3            │
│ Nodo_4: affinity = 0.9 + 0.6 = 1.5      │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Seleccionar mejores nodos:              │
│ • Nodo_2 (1.5) ✓                        │
│ • Nodo_4 (1.5) ✓ (desempate por carga) │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Encolar tareas de replicación:          │
│ • Nodo_1 → Nodo_2 (prioridad NORMAL)   │
│ • Nodo_1 → Nodo_4 (prioridad NORMAL)   │
└─────────────────────────────────────────┘
```

## Prioridades de Replicación

```python
class ReplicationPriority(Enum):
    """Priority levels for replication tasks."""
    CRITICAL = 4  # Primario perdido, sin réplicas
    HIGH = 3      # Sub-replicado (under-replicated)
    NORMAL = 2    # Documento nuevo
    LOW = 1       # Optimización en background
```

| Prioridad | Situación | Ejemplo |
|-----------|-----------|----------|
| CRITICAL | Sin copias | Nodo único falló |
| HIGH | Bajo factor | 1 copia cuando necesita 2 |
| NORMAL | Nuevo doc | Documento recién subido |
| LOW | Optimización | Mover réplica a mejor nodo |

## Registro de Documento

```python
async def register_document(
    self,
    document_id: str,
    primary_node: str,
    document_vectors: Optional[Dict[str, Any]] = None,
    size_bytes: int = 0,
    checksum: Optional[str] = None
) -> DocumentReplicas:
    """
    Register a new document and initiate replication.
    """
    # 1. Seleccionar nodos réplica usando afinidad
    replica_nodes = await self._select_replica_nodes(
        document_id,
        primary_node,
        document_vectors
    )
    
    # 2. Registrar en tracker
    doc_replicas = self.replica_tracker.register_document(
        document_id=document_id,
        primary_node=primary_node,
        replica_nodes=replica_nodes,
        replication_factor=self.config.replication_factor
    )
    
    # 3. Añadir al grafo de similaridad
    self.similarity_graph.add_document(
        document_id=document_id,
        primary_node=primary_node,
        document_vectors=document_vectors,
        replica_nodes=replica_nodes
    )
    
    # 4. Encolar tareas de replicación
    for replica_node in replica_nodes:
        task = self._create_task(
            document_id=document_id,
            source_node=primary_node,
            target_node=replica_node,
            priority=ReplicationPriority.NORMAL
        )
        self._pending_tasks[task.task_id] = task
    
    return doc_replicas
```

## Ventajas de la Afinidad Semántica

### 1. Localidad de Búsqueda

Consultas sobre temas específicos encuentran resultados en menos nodos.

### 2. Mejor Uso de Caché

Documentos relacionados comparten estructuras de índice.

### 3. Tolerancia a Fallos Coherente

Si un nodo falla, los documentos relacionados en otros nodos permiten respuestas parciales coherentes.

### 4. Eficiencia en Red

Menos comunicación inter-nodo para queries relacionadas.

---

**Navegación:**
- [← README](README.md)
- [→ Siguiente: Grafo de Similaridad](02_Grafo_Similaridad.md)
