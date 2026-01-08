# VP-Tree Distribuido

## Árboles de Vantage-Point para Espacios Métricos

---

## 1. ¿Qué es un VP-Tree?

Un **Vantage-Point Tree (VP-Tree)** es una estructura de datos para organizar puntos en un espacio métrico, permitiendo búsquedas eficientes de vecinos cercanos.

### 1.1 Concepto Básico

1. Se elige un punto como **vantage point (VP)** o punto de referencia
2. Se calcula la **distancia mediana** de todos los puntos al VP
3. Los puntos se dividen en dos grupos:
   - **Izquierda**: Puntos más cercanos que la mediana
   - **Derecha**: Puntos más lejanos que la mediana
4. Se repite recursivamente

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESTRUCTURA VP-TREE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                         [VP₀]                                   │
│                     median = 0.45                               │
│                    /            \                               │
│                   /              \                              │
│           d ≤ 0.45              d > 0.45                       │
│              /                      \                           │
│          [VP₁]                    [VP₂]                        │
│       median = 0.23            median = 0.31                   │
│         /    \                   /    \                         │
│        /      \                 /      \                        │
│   [Leaf₁]  [Leaf₂]         [Leaf₃]  [Leaf₄]                   │
│   docs A   docs B          docs C   docs D                     │
│                                                                 │
│  Complejidad búsqueda: O(log n) promedio                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. ¿Por Qué VP-Tree para DistriSearch?

### 2.1 Requisitos del Sistema

1. **Sin hash para ubicación**: Restricción del proyecto
2. **Preservar localidad semántica**: Docs similares juntos
3. **Espacios métricos arbitrarios**: Nuestra distancia combinada

### 2.2 Propiedades de VP-Tree

| Propiedad | Beneficio |
|-----------|-----------|
| Funciona con cualquier métrica | Compatible con nuestra distancia ponderada |
| Divide por distancia, no posición | Agrupa por similaridad |
| Búsqueda logarítmica | Eficiente en grandes corpus |
| Fácil de distribuir | Cada hoja → un nodo del cluster |

---

## 3. Implementación en DistriSearch

### 3.1 Estructura VPNode

```python
# backend/app/core/partitioning/vp_tree.py

@dataclass
class VPNode:
    """
    Nodo en la estructura VP-Tree.
    """
    vantage_point: Optional[Dict[str, Any]] = None  # Documento elegido como VP
    vantage_id: Optional[str] = None                 # ID del documento VP
    median_distance: float = 0.0                     # Umbral de partición
    left: Optional['VPNode'] = None                  # Subárbol izquierdo
    right: Optional['VPNode'] = None                 # Subárbol derecho
    documents: List[Dict[str, Any]] = field(default_factory=list)  # Docs en hojas
    node_id: str = ""                                # ID único del nodo
    depth: int = 0                                   # Profundidad en el árbol
    assigned_node: Optional[str] = None              # Nodo del cluster asignado
    
    @property
    def is_leaf(self) -> bool:
        """¿Es nodo hoja?"""
        return self.left is None and self.right is None
    
    @property
    def size(self) -> int:
        """Número de documentos en subárbol."""
        if self.is_leaf:
            return len(self.documents)
        
        count = 1 if self.vantage_point else 0
        if self.left:
            count += self.left.size
        if self.right:
            count += self.right.size
        return count
```

### 3.2 Clase VPTree

```python
class VPTree:
    """
    VP-Tree para particionamiento de documentos.
    """
    
    def __init__(
        self,
        distance_calculator: Optional[DistanceCalculator] = None,
        leaf_size: int = 50,
        selection_strategy: VantagePointSelection = VantagePointSelection.K_MEDOIDS,
        sample_size: int = 10
    ):
        """
        Args:
            distance_calculator: Calculador de distancias
            leaf_size: Máximo documentos por hoja
            selection_strategy: Estrategia para elegir VP
            sample_size: Candidatos a muestrear para VP
        """
        self.distance_calc = distance_calculator or DistanceCalculator()
        self.leaf_size = leaf_size
        self.selection_strategy = selection_strategy
        self.sample_size = sample_size
        self.root: Optional[VPNode] = None
        self._all_nodes: Dict[str, VPNode] = {}
```

---

## 4. Construcción Recursiva

### 4.1 Algoritmo

```python
def _build_recursive(
    self,
    documents: List[Dict[str, Any]],
    depth: int = 0
) -> Optional[VPNode]:
    """
    Construye VP-Tree recursivamente.
    """
    if not documents:
        return None
    
    node_id = self._generate_node_id()
    
    # Caso base: pocos documentos → nodo hoja
    if len(documents) <= self.leaf_size:
        node = VPNode(
            documents=documents.copy(),
            node_id=node_id,
            depth=depth
        )
        self._all_nodes[node_id] = node
        return node
    
    # Seleccionar vantage point
    vp, vp_idx = self._select_vantage_point(documents)
    vp_id = vp.get("id") or vp.get("document_id")
    
    # Calcular distancias desde VP
    remaining = documents[:vp_idx] + documents[vp_idx + 1:]
    distances = []
    
    for doc in remaining:
        d = self._distance(vp, doc)
        distances.append((d, doc))
    
    # Ordenar y encontrar mediana
    distances.sort(key=lambda x: x[0])
    median_idx = len(distances) // 2
    median_distance = distances[median_idx][0]
    
    # Particionar documentos
    left_docs = [doc for d, doc in distances if d <= median_distance]
    right_docs = [doc for d, doc in distances if d > median_distance]
    
    # Crear nodo
    node = VPNode(
        vantage_point=vp,
        vantage_id=vp_id,
        median_distance=median_distance,
        node_id=node_id,
        depth=depth
    )
    
    # Construir subárboles recursivamente
    node.left = self._build_recursive(left_docs, depth + 1)
    node.right = self._build_recursive(right_docs, depth + 1)
    
    self._all_nodes[node_id] = node
    return node
```

### 4.2 Visualización del Proceso

```
Documentos iniciales: [D1, D2, D3, D4, D5, D6, D7, D8]

Paso 1: Seleccionar VP₀ = D3 (k-medoids)
        Calcular distancias a D3:
        D1: 0.2, D2: 0.3, D4: 0.5, D5: 0.4, D6: 0.6, D7: 0.35, D8: 0.55
        
        Mediana = 0.4

Paso 2: Particionar
        Izquierda (d ≤ 0.4): [D1, D2, D7]
        Derecha (d > 0.4):    [D4, D5, D6, D8]

Paso 3: Recursión en cada subárbol...

Resultado:
                    [D3, median=0.4]
                   /                 \
          [D2, med=0.2]        [D5, med=0.5]
            /      \              /      \
         [D1]    [D7]        [D4]    [D6, D8]
```

---

## 5. Distribución: Nodos del Cluster = Hojas del Árbol

### 5.1 Concepto

Cada **nodo hoja** del VP-Tree se asigna a un **nodo del cluster**:

```
┌─────────────────────────────────────────────────────────────────┐
│            VP-TREE → CLUSTER NODES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  VP-Tree (lógico)              Cluster (físico)                │
│                                                                 │
│       [Root]                                                    │
│      /      \                  ┌──────────────────┐            │
│   [VP₁]    [VP₂]               │   Load Balancer   │            │
│   /   \    /   \               └────────┬─────────┘            │
│ [L1] [L2][L3] [L4]                      │                       │
│   │    │   │    │              ┌────────┼────────┐             │
│   │    │   │    │              ▼        ▼        ▼              │
│   │    │   │    └─────────▶ [Slave_3: L3, L4]                  │
│   │    │   └──────────────▶ [Slave_2: L2]                      │
│   │    └──────────────────▶ [Slave_1: L1]                      │
│   └───────────────────────▶ [Slave_1: L1]                      │
│                                                                 │
│  Documentos similares (misma hoja) → Mismo nodo físico         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Asignación de Particiones

```python
def assign_nodes_to_partitions(
    self,
    cluster_nodes: List[str],
    strategy: str = "balanced"
) -> Dict[str, str]:
    """
    Asigna nodos del cluster a particiones del árbol.
    
    Returns:
        Mapping: partition_id → cluster_node_id
    """
    assignments = {}
    leaf_nodes = [n for n in self._all_nodes.values() if n.is_leaf]
    
    if strategy == "balanced":
        # Ordenar hojas por tamaño (mayor primero)
        leaf_nodes.sort(key=lambda x: len(x.documents), reverse=True)
        node_loads = {n: 0 for n in cluster_nodes}
        
        for leaf in leaf_nodes:
            # Asignar al nodo menos cargado
            least_loaded = min(node_loads, key=node_loads.get)
            leaf.assigned_node = least_loaded
            assignments[leaf.node_id] = least_loaded
            node_loads[least_loaded] += len(leaf.documents)
    
    return assignments
```

---

## 6. Búsqueda en VP-Tree

### 6.1 Búsqueda K-NN (K Nearest Neighbors)

```python
def search_knn(
    self,
    query: Dict[str, Any],
    k: int = 10,
    max_distance: Optional[float] = None
) -> List[Tuple[Dict[str, Any], float]]:
    """
    Encuentra los k vecinos más cercanos a la query.
    """
    neighbors: List[Tuple[float, Dict]] = []
    tau = max_distance if max_distance else float('inf')  # Radio de búsqueda
    
    def search_recursive(node: Optional[VPNode]):
        nonlocal tau
        
        if node is None:
            return
        
        if node.is_leaf:
            # Verificar todos los documentos en la hoja
            for doc in node.documents:
                d = self._distance(query, doc)
                if d < tau:
                    neighbors.append((d, doc))
                    neighbors.sort(key=lambda x: x[0])
                    if len(neighbors) > k:
                        neighbors.pop()
                    if len(neighbors) == k:
                        tau = neighbors[-1][0]  # Actualizar radio
            return
        
        # Calcular distancia al vantage point
        vp_dist = self._distance(query, node.vantage_point)
        
        # Verificar si VP califica
        if vp_dist < tau:
            neighbors.append((vp_dist, node.vantage_point))
            # ... actualizar tau
        
        # Determinar orden de búsqueda (poda inteligente)
        if vp_dist < node.median_distance:
            # Query más cerca de izquierda
            if vp_dist - tau <= node.median_distance:
                search_recursive(node.left)
            if vp_dist + tau >= node.median_distance:
                search_recursive(node.right)
        else:
            # Query más cerca de derecha
            if vp_dist + tau >= node.median_distance:
                search_recursive(node.right)
            if vp_dist - tau <= node.median_distance:
                search_recursive(node.left)
    
    search_recursive(self.root)
    return [(doc, dist) for dist, doc in neighbors]
```

### 6.2 Poda del Espacio de Búsqueda

La clave de la eficiencia es la **poda**:

```
Query Q con radio τ (distancia al k-ésimo vecino actual)

                    [VP₀]
                 median = m
                /          \
           d ≤ m           d > m
           
Si d(Q, VP₀) = 0.3 y m = 0.5:
  - Q está en región izquierda
  - Si τ = 0.1:
    - Izquierda: d(Q,VP) - τ = 0.2 ≤ 0.5 ✓ BUSCAR
    - Derecha:   d(Q,VP) + τ = 0.4 < 0.5   ✗ PODAR
    
  Resultado: Solo buscamos en subárbol izquierdo (50% poda)
```

---

## 7. El Master Mantiene el VP-Tree Global

```
┌─────────────────────────────────────────────────────────────────┐
│              MASTER: COORDINADOR DEL VP-TREE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MASTER NODE                           │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │  VP-Tree Global (en memoria + persistido)        │   │   │
│  │  │  ├── root: VPNode                                │   │   │
│  │  │  ├── _all_nodes: Dict[str, VPNode]               │   │   │
│  │  │  └── _partition_assignments: Dict[str, str]      │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                          │   │
│  │  Responsabilidades:                                      │   │
│  │  ├── Construir VP-Tree al iniciar                        │   │
│  │  ├── Reasignar particiones cuando nodos join/leave      │   │
│  │  ├── Propagar actualizaciones a Slaves                   │   │
│  │  └── Responder queries de enrutamiento                   │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Complejidad

| Operación | Complejidad |
|-----------|-------------|
| Construcción | $O(n \log n)$ |
| Búsqueda K-NN | $O(\log n)$ promedio, $O(n)$ peor caso |
| Inserción | $O(\log n)$ |
| Rango | $O(\log n + k)$ donde k = resultados |

---

## 9. Parámetros de Configuración

```python
# backend/app/core/partitioning/vp_tree.py

class VPTree:
    def __init__(
        self,
        leaf_size: int = 50,            # Docs máximos por hoja
        selection_strategy: VantagePointSelection = VantagePointSelection.K_MEDOIDS,
        sample_size: int = 10           # Candidatos para VP
    ):
```

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `leaf_size` | 50 | Más pequeño = árbol más profundo |
| `selection_strategy` | K_MEDOIDS | Mejor calidad de partición |
| `sample_size` | 10 | Trade-off calidad/velocidad |

---

> **Anterior**: [README.md](README.md)
> 
> **Siguiente**: [02_Algoritmo_Asignacion.md](02_Algoritmo_Asignacion.md)