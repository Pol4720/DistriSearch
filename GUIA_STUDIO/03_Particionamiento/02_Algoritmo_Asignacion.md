# Algoritmo de Asignación de Documentos

## Enrutamiento Basado en VP-Tree

---

## 1. Visión General

Cuando llega un **nuevo documento**, el sistema debe decidir en qué **nodo del cluster** almacenarlo. El algoritmo garantiza que documentos similares residan juntos.

```
┌─────────────────────────────────────────────────────────────────┐
│                FLUJO DE ASIGNACIÓN                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                               │
│  │ Documento    │                                               │
│  │ nuevo        │                                               │
│  └──────┬───────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │ 1. Calcular AdaptiveDocumentVector       │                  │
│  │    ├── name_vector (TF-IDF + n-grams)    │                  │
│  │    ├── content_vector (MinHash + LDA)    │                  │
│  │    └── structural_features               │                  │
│  └──────────────────┬───────────────────────┘                  │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────┐                  │
│  │ 2. Buscar partición en VP-Tree           │                  │
│  │    ├── Calcular distancia a cada VP      │                  │
│  │    ├── Navegar según median_distance     │                  │
│  │    └── Llegar a nodo hoja               │                  │
│  └──────────────────┬───────────────────────┘                  │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────┐                  │
│  │ 3. Obtener nodo asignado a partición     │                  │
│  │    partition_assignments[partition_id]   │                  │
│  └──────────────────┬───────────────────────┘                  │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────┐                  │
│  │ 4. Almacenar en nodo primario + réplicas │                  │
│  └──────────────────────────────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Clase VPTreePartitioner (Conceptual)

El `PartitionManager` actúa como el VPTreePartitioner:

```python
# backend/app/core/partitioning/partition_manager.py

class PartitionManager:
    """
    Gestor de particiones VP-Tree.
    """
    
    def __init__(
        self,
        leaf_size: int = 50,
        replication_factor: int = 2,
        vp_selection: VantagePointSelection = VantagePointSelection.K_MEDOIDS
    ):
        self.vp_tree = VPTree(
            leaf_size=leaf_size,
            selection_strategy=vp_selection
        )
        self.node_assigner = NodeAssigner(
            replication_factor=replication_factor
        )
        self._partition_assignments: Dict[str, str] = {}  # partition → node
```

---

## 3. Algoritmo: Encontrar Partición

### 3.1 find_partition

```python
# backend/app/core/partitioning/vp_tree.py

def find_partition(self, query: Dict[str, Any]) -> Optional[str]:
    """
    Encuentra la partición (nodo hoja) donde pertenece el documento.
    
    Args:
        query: Documento con vectores
        
    Returns:
        ID de la partición (nodo hoja del VP-Tree)
    """
    if self.root is None:
        return None
    
    node = self.root
    
    while not node.is_leaf:
        # Calcular distancia al vantage point actual
        vp_dist = self._distance(query, node.vantage_point)
        
        # Decidir rama según distancia vs mediana
        if vp_dist <= node.median_distance:
            # Documento más cercano → rama izquierda
            if node.left:
                node = node.left
            else:
                break
        else:
            # Documento más lejano → rama derecha
            if node.right:
                node = node.right
            else:
                break
    
    return node.node_id
```

### 3.2 Visualización

```
Documento nuevo: "ReporteVentas_Q1_2024.xlsx"
Vector calculado: {name: {...}, content: {...}, topics: [...]}

VP-Tree:
                    [VP₀: doc_finanzas]
                     median = 0.45
                    /              \
           d ≤ 0.45                 d > 0.45
              |                        |
        [VP₁: doc_ventas]        [VP₂: doc_legal]
         median = 0.25            median = 0.30
            /    \                   /    \
    [Leaf_A]  [Leaf_B]        [Leaf_C]  [Leaf_D]
    
Proceso:
1. d(doc, VP₀) = 0.32 → ≤ 0.45 → Izquierda
2. d(doc, VP₁) = 0.18 → ≤ 0.25 → Izquierda
3. Llegamos a Leaf_A → partition_id = "vpn_3"

Resultado: Documento va a Leaf_A (asignada a Slave_1)
```

---

## 4. Cálculo de Distancia

### 4.1 Fórmula Combinada

```python
# backend/app/core/partitioning/distance_metrics.py

class DistanceCalculator:
    """
    Calcula distancias usando fórmula ponderada:
    d(A,B) = 0.4 * cosine_distance(name) + 
             0.4 * jaccard_distance(content) + 
             0.2 * jsd(topics)
    """
    
    def weighted_distance(
        self,
        doc_a: Dict[str, Any],
        doc_b: Dict[str, Any]
    ) -> float:
        """
        Distancia ponderada entre documentos.
        """
        # Distancia del nombre (coseno)
        name_dist = self.cosine_distance(
            doc_a.get("name_vector"),
            doc_b.get("name_vector")
        )
        
        # Distancia del contenido (Jaccard via MinHash)
        content_dist = self.jaccard_distance(
            doc_a.get("minhash_signature"),
            doc_b.get("minhash_signature")
        )
        
        # Distancia de tópicos (Jensen-Shannon)
        topic_dist = self.jensen_shannon_distance(
            doc_a.get("topic_distribution"),
            doc_b.get("topic_distribution")
        )
        
        # Combinación ponderada
        return (
            self.weights.name_weight * name_dist +
            self.weights.content_weight * content_dist +
            self.weights.topic_weight * topic_dist
        )
```

### 4.2 Métricas Individuales

```python
def cosine_distance(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Distancia coseno: d = (1 - cos(θ)) / 2
    
    Normalizada a [0, 1]
    """
    similarity = self.cosine_similarity(vec_a, vec_b)
    return (1.0 - similarity) / 2.0

def jaccard_distance(self, sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    """
    Distancia Jaccard estimada desde MinHash:
    d = 1 - J(A, B)
    """
    similarity = self.jaccard_similarity(sig_a, sig_b)
    return 1.0 - similarity

def jensen_shannon_distance(self, p: np.ndarray, q: np.ndarray) -> float:
    """
    Distancia Jensen-Shannon:
    d = sqrt(JSD(P || Q))
    
    Donde JSD = 0.5 * KL(P||M) + 0.5 * KL(Q||M), M = (P+Q)/2
    """
    m = 0.5 * (p + q)
    jsd = 0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m))
    return np.sqrt(jsd / np.log(2))
```

---

## 5. Enrutamiento Completo

### 5.1 route_document

```python
# backend/app/core/partitioning/partition_manager.py

def route_document(
    self,
    document: Dict[str, Any],
    strategy: AssignmentStrategy = AssignmentStrategy.VP_TREE_PARTITION
) -> RoutingResult:
    """
    Enruta documento al nodo apropiado.
    """
    doc_id = document.get("id")
    
    # 1. Encontrar partición en VP-Tree
    partition_id = self.vp_tree.find_partition(document)
    
    # 2. Obtener nodo asignado a esa partición
    if partition_id and partition_id in self._partition_assignments:
        primary_node = self._partition_assignments[partition_id]
        
        # 3. Obtener nodos para réplicas (afinidad semántica)
        replica_result = self.node_assigner.assign_document(
            document,
            strategy=AssignmentStrategy.SEMANTIC_AFFINITY,
            partition_id=partition_id
        )
        
        return RoutingResult(
            document_id=doc_id,
            partition_id=partition_id,
            primary_node=primary_node,
            replica_nodes=replica_result.replica_nodes
        )
    
    # Fallback: usar NodeAssigner directamente
    result = self.node_assigner.assign_document(document, strategy)
    
    return RoutingResult(
        document_id=doc_id,
        partition_id="unpartitioned",
        primary_node=result.assigned_node,
        replica_nodes=result.replica_nodes
    )
```

---

## 6. Estrategias de Asignación Alternativas

### 6.1 Enum de Estrategias

```python
# backend/app/core/partitioning/node_assignment.py

class AssignmentStrategy(Enum):
    """Estrategias de asignación de documentos."""
    ROUND_ROBIN = "round_robin"          # Rotativo
    LEAST_LOADED = "least_loaded"        # Menos cargado
    SEMANTIC_AFFINITY = "semantic_affinity"  # Por similaridad
    CONSISTENT_HASH = "consistent_hash"  # Hash consistente
    VP_TREE_PARTITION = "vp_tree_partition"  # 🔴 Principal
```

### 6.2 Afinidad Semántica (para réplicas)

```python
def _semantic_affinity_assignment(
    self,
    document: Dict[str, Any],
    exclude_nodes: Optional[List[str]] = None
) -> Optional[str]:
    """
    Asigna basándose en afinidad semántica.
    
    Coloca documento en nodo que tiene documentos más similares.
    """
    exclude = set(exclude_nodes or [])
    healthy_nodes = [
        n for n in self._nodes.values()
        if n.is_healthy and n.available_capacity > 0 and n.node_id not in exclude
    ]
    
    best_node = None
    best_affinity = float('inf')  # Menor distancia = mejor
    
    for node in healthy_nodes:
        node_docs = self._node_documents.get(node.node_id, [])
        
        if not node_docs:
            affinity = 0.5  # Nodo vacío: afinidad neutral
        else:
            # Promedio de distancias a muestra de documentos
            sample = node_docs[:10]
            distances = [
                self.distance_calc.weighted_distance(document, doc)
                for doc in sample
            ]
            affinity = np.mean(distances)
        
        # Penalizar nodos muy cargados
        load_penalty = node.load_factor * 0.2
        adjusted_affinity = affinity + load_penalty
        
        if adjusted_affinity < best_affinity:
            best_affinity = adjusted_affinity
            best_node = node.node_id
    
    return best_node
```

---

## 7. Ejemplo Completo

```python
# Nuevo documento llega
document = {
    "id": "doc_12345",
    "filename": "ReporteVentas_Q1_2024.xlsx",
    "content": "Las ventas del trimestre...",
    "vectors": {...}  # Pre-calculados
}

# 1. Vectorizar (si no está pre-calculado)
vectorizer = DocumentVectorizer()
doc_vector = vectorizer.vectorize(
    filename=document["filename"],
    content=document["content"]
)

# 2. Agregar vector al documento
document["name_vector"] = doc_vector.name_vector.tokens_tfidf
document["minhash_signature"] = doc_vector.content_vector.minhash_signatures
document["topic_distribution"] = doc_vector.content_vector.topic_distribution

# 3. Enrutar
partition_manager = PartitionManager()
routing = partition_manager.route_document(document)

print(routing)
# RoutingResult(
#     document_id="doc_12345",
#     partition_id="vpn_7",
#     primary_node="slave_2",
#     replica_nodes=["slave_1", "slave_3"]
# )

# 4. Almacenar
await store_document(routing.primary_node, document)
for replica_node in routing.replica_nodes:
    await replicate_document(replica_node, document)
```

---

## 8. Diagrama de Secuencia

```
┌────────┐  ┌─────────────────┐  ┌────────┐  ┌───────┐  ┌───────┐
│ Client │  │PartitionManager │  │ VPTree │  │ Slave │  │MongoDB│
└───┬────┘  └────────┬────────┘  └───┬────┘  └───┬───┘  └───┬───┘
    │                │               │           │          │
    │ upload(doc)    │               │           │          │
    │───────────────▶│               │           │          │
    │                │               │           │          │
    │                │ find_partition(doc)       │          │
    │                │──────────────▶│           │          │
    │                │               │           │          │
    │                │   partition_id│           │          │
    │                │◀──────────────│           │          │
    │                │               │           │          │
    │                │ get_assigned_node(partition_id)      │
    │                │──────────────────────────▶│          │
    │                │                           │          │
    │                │       primary_node        │          │
    │                │◀──────────────────────────│          │
    │                │               │           │          │
    │                │ store(doc)    │           │          │
    │                │───────────────────────────▶ insert   │
    │                │               │           │─────────▶│
    │                │               │           │          │
    │  routing_result│               │           │          │
    │◀───────────────│               │           │          │
    │                │               │           │          │
```

---

## 9. Propiedades del Algoritmo

| Propiedad | Valor |
|-----------|-------|
| Complejidad asignación | $O(\log n)$ |
| Garantía de localidad | Sí (docs similares → mismo nodo) |
| Balanceo de carga | Sí (estrategia "balanced") |
| Tolerancia a fallos | Sí (réplicas en nodos diferentes) |
| Determinístico | Sí (mismo doc → misma partición) |

---

> **Anterior**: [01_VP_Tree_Distribuido.md](01_VP_Tree_Distribuido.md)
> 
> **Siguiente**: [03_Vantage_Points.md](03_Vantage_Points.md)