# Grafo de Similaridad

## Concepto

El **grafo de similaridad** es una estructura de datos donde:
- **Nodos** = Documentos
- **Aristas** = Relaciones de similaridad (peso = score de similaridad)

Este grafo permite encontrar rápidamente documentos relacionados y determinar la mejor ubicación para réplicas.

## Estructura Visual

```
┌──────────────────────────────────────────────────────────────────────┐
│                      GRAFO DE SIMILARIDAD                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│     [ventas_q1.xlsx]                                                │
│            │ sim=0.85                                                │
│            ▼                                                         │
│     [ventas_q2.xlsx] ◄──sim=0.72──► [ingresos_2024.csv]            │
│            │ sim=0.68                                                │
│            ▼                                                         │
│     [reporte_ventas.pdf]                                            │
│                                                                      │
│     ═══════════════════════════════════════                         │
│                                                                      │
│     Asignación a Nodos del Cluster:                                 │
│                                                                      │
│     Nodo_1: {ventas_q1, ventas_q2}  ← Réplica de ingresos aquí     │
│     Nodo_2: {ingresos, reporte}     ← Réplica de ventas_q2 aquí    │
│     Nodo_3: {Réplicas...}                                           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Clase `SimilarityGraph`

**Ubicación:** `backend/app/core/replication/similarity_graph.py`

```python
class SimilarityGraph:
    """
    Graph structure tracking document similarities.
    
    Used to:
    - Find semantically similar documents
    - Determine optimal replica placement
    - Support nearest-neighbor queries
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.3,
        max_neighbors: int = 20,
        distance_func: Optional[callable] = None
    ):
        self.similarity_threshold = similarity_threshold
        self.max_neighbors = max_neighbors
        self._distance_func = distance_func
        
        # Almacenamiento del grafo
        self._nodes: Dict[str, DocumentNode] = {}
        self._edges: Dict[str, Set[str]] = defaultdict(set)
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        
        # Índice para búsquedas rápidas
        self._node_to_docs: Dict[str, Set[str]] = defaultdict(set)
```

## Estructura de Datos

### Nodo del Documento

```python
@dataclass
class DocumentNode:
    """Node in the similarity graph representing a document."""
    document_id: str
    primary_node: str                           # Nodo primario
    replica_nodes: List[str] = field(default_factory=list)
    neighbors: Dict[str, float] = field(default_factory=dict)  # doc_id → sim
    created_at: datetime = field(default_factory=datetime.utcnow)
    vector_hash: Optional[str] = None           # Para detectar cambios
    
    @property
    def all_nodes(self) -> List[str]:
        """All nodes storing this document."""
        return [self.primary_node] + self.replica_nodes
```

### Arista de Similaridad

```python
@dataclass
class SimilarityEdge:
    """Edge in similarity graph between two documents."""
    doc_a: str
    doc_b: str
    similarity: float                           # 0.0 a 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
```

## Operaciones del Grafo

### Añadir Documento

```python
def add_document(
    self,
    document_id: str,
    primary_node: str,
    document_vectors: Optional[Dict[str, Any]] = None,
    replica_nodes: Optional[List[str]] = None
) -> DocumentNode:
    """Add a document to the graph."""
    node = DocumentNode(
        document_id=document_id,
        primary_node=primary_node,
        replica_nodes=replica_nodes or []
    )
    
    self._nodes[document_id] = node
    self._node_to_docs[primary_node].add(document_id)
    
    for replica in node.replica_nodes:
        self._node_to_docs[replica].add(document_id)
    
    # Calcular similaridades si hay vectores
    if document_vectors and self._distance_func:
        self._update_similarities(document_id, document_vectors)
    
    return node
```

### Añadir Similaridad

```python
def add_similarity(
    self,
    doc_a: str,
    doc_b: str,
    similarity: float
) -> bool:
    """Add or update similarity between two documents."""
    # Solo crear arista si supera umbral
    if similarity < self.similarity_threshold:  # 0.3
        return False
    
    if doc_a not in self._nodes or doc_b not in self._nodes:
        return False
    
    # Almacenar arista bidireccional
    self._edges[doc_a].add(doc_b)
    self._edges[doc_b].add(doc_a)
    
    # Cachear similaridad
    key = tuple(sorted([doc_a, doc_b]))
    self._similarity_cache[key] = similarity
    
    # Actualizar listas de vecinos
    self._nodes[doc_a].neighbors[doc_b] = similarity
    self._nodes[doc_b].neighbors[doc_a] = similarity
    
    # Podar si hay demasiados vecinos
    self._prune_neighbors(doc_a)
    self._prune_neighbors(doc_b)
    
    return True
```

### Obtener Vecinos

```python
def get_neighbors(
    self,
    document_id: str,
    limit: int = 10
) -> List[Tuple[str, float]]:
    """Get most similar neighbors of a document."""
    node = self._nodes.get(document_id)
    if not node:
        return []
    
    # Ordenar por similaridad descendente
    sorted_neighbors = sorted(
        node.neighbors.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return sorted_neighbors[:limit]
```

## Encontrar Mejores Nodos para Réplicas

```python
def find_best_replica_nodes(
    self,
    document_id: str,
    candidate_nodes: List[str],
    num_replicas: int = 1,
    exclude_primary: bool = True
) -> List[Tuple[str, float]]:
    """
    Find best nodes for replicas based on semantic affinity.
    
    Args:
        document_id: Document to replicate
        candidate_nodes: Available cluster nodes
        num_replicas: Number of replicas needed
        
    Returns:
        List of (node_id, affinity_score) tuples
    """
    node = self._nodes.get(document_id)
    if not node:
        return []
    
    # Obtener vecinos del documento
    neighbors = self.get_neighbors(document_id, limit=50)
    
    # Puntuar cada nodo candidato
    node_scores: Dict[str, float] = {}
    
    for candidate in candidate_nodes:
        if exclude_primary and candidate == node.primary_node:
            continue
        if candidate in node.replica_nodes:
            continue
        
        # Calcular afinidad: suma de similaridades con docs en este nodo
        node_docs = self.get_documents_on_node(candidate)
        
        affinity = 0.0
        for neighbor_id, similarity in neighbors:
            if neighbor_id in node_docs:
                affinity += similarity
        
        node_scores[candidate] = affinity
    
    # Ordenar por afinidad descendente
    sorted_nodes = sorted(
        node_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return sorted_nodes[:num_replicas]
```

## Ejemplo de Cálculo de Afinidad

```
Ejemplo: Buscar mejor nodo para réplica de "reporte_ventas.pdf"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Vecinos de reporte_ventas.pdf:
  • ventas_q1.xlsx: sim=0.75
  • ventas_q2.xlsx: sim=0.70
  • ingresos_2024.csv: sim=0.60
  • marketing.pdf: sim=0.35

Documentos por nodo:
  • Nodo_1: {ventas_q1, presupuesto}
  • Nodo_2: {marketing, comunicados}
  • Nodo_3: {ventas_q2, ingresos_2024}

Cálculo de afinidad:
  • Nodo_1: affinity = 0.75 (ventas_q1)           = 0.75
  • Nodo_2: affinity = 0.35 (marketing)           = 0.35
  • Nodo_3: affinity = 0.70 + 0.60 (q2 + ingresos) = 1.30 ← MEJOR

Resultado: Réplica de reporte_ventas.pdf → Nodo_3
```

## Diagrama del Grafo

```
          ┌─────────────────────────────────────────────────────┐
          │               SIMILARITY GRAPH                       │
          └─────────────────────────────────────────────────────┘

                    0.85                      0.72
          [ventas_q1]───────────[ventas_q2]───────────[ingresos]
              │                      │                     │
              │ 0.40                 │ 0.68                │ 0.55
              │                      │                     │
              ▼                      ▼                     ▼
          [budget]              [reporte]            [gastos]
                                    │
                                    │ 0.45
                                    ▼
                               [resumen]

          ═══════════════════════════════════════════════════════

          Threshold = 0.3 → Solo aristas con sim ≥ 0.3
          Max neighbors = 20 → Máximo 20 conexiones por nodo
```

## Poda de Vecinos

Para mantener el grafo eficiente, se limita el número de vecinos:

```python
def _prune_neighbors(self, document_id: str) -> None:
    """Keep only top-k neighbors."""
    node = self._nodes.get(document_id)
    if not node or len(node.neighbors) <= self.max_neighbors:
        return
    
    # Mantener vecinos con mayor similaridad
    sorted_neighbors = sorted(
        node.neighbors.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    keep = dict(sorted_neighbors[:self.max_neighbors])
    removed = set(node.neighbors.keys()) - set(keep.keys())
    
    node.neighbors = keep
    
    # Limpiar aristas y caché
    for doc_id in removed:
        self._edges[document_id].discard(doc_id)
        key = tuple(sorted([document_id, doc_id]))
        self._similarity_cache.pop(key, None)
```

## Actualización de Ubicación

```python
def update_document_location(
    self,
    document_id: str,
    primary_node: Optional[str] = None,
    replica_nodes: Optional[List[str]] = None
) -> None:
    """Update the storage location of a document."""
    node = self._nodes.get(document_id)
    if not node:
        return
    
    # Actualizar índice de nodo primario
    if primary_node and primary_node != node.primary_node:
        self._node_to_docs[node.primary_node].discard(document_id)
        self._node_to_docs[primary_node].add(document_id)
        node.primary_node = primary_node
    
    # Actualizar réplicas
    if replica_nodes is not None:
        for old_replica in node.replica_nodes:
            if old_replica not in replica_nodes:
                self._node_to_docs[old_replica].discard(document_id)
        
        for new_replica in replica_nodes:
            self._node_to_docs[new_replica].add(document_id)
        
        node.replica_nodes = replica_nodes
```

## Impacto en Tolerancia a Fallos

El grafo influye en cómo sobrevive el sistema a fallos:

```
┌──────────────────────────────────────────────────────────────┐
│                    FALLO DE Nodo_1                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ANTES:                                                     │
│   Nodo_1: [A●, B●, C○]                                      │
│   Nodo_2: [D●, A○, B○]  ← Réplicas de vecinos               │
│                                                              │
│   DESPUÉS:                                                   │
│   Nodo_1: ✗ CAÍDO                                           │
│   Nodo_2: [D●, A○, B○]  ← A y B aún disponibles            │
│                                                              │
│   Búsqueda por A o B → Nodo_2 puede responder               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

**Navegación:**
- [← Anterior: Afinidad Semántica](01_Afinidad_Semantica.md)
- [→ Siguiente: Factor de Replicación](03_Factor_Replicacion.md)
