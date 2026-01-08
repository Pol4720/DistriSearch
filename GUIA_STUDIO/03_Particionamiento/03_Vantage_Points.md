# Vantage Points

## Selección y Gestión de Puntos de Referencia

---

## 1. ¿Qué es un Vantage Point?

Un **Vantage Point (VP)** es un documento elegido como **punto de referencia** para dividir el espacio. La calidad del VP afecta directamente la eficiencia del árbol.

```
┌─────────────────────────────────────────────────────────────────┐
│                   ROL DEL VANTAGE POINT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  El VP define cómo se divide el espacio:                       │
│                                                                 │
│         Todos los documentos                                    │
│              │                                                  │
│              ▼                                                  │
│         [VP elegido]                                            │
│         median = m                                              │
│        /          \                                             │
│   d ≤ m            d > m                                       │
│   (cercanos)       (lejanos)                                   │
│                                                                 │
│  Un buen VP:                                                   │
│  ├── Divide el espacio en mitades equilibradas                │
│  ├── Maximiza la separación entre grupos                       │
│  └── Minimiza la superposición de regiones                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Estrategias de Selección

DistriSearch implementa tres estrategias:

```python
# backend/app/core/partitioning/vp_tree.py

class VantagePointSelection(Enum):
    """Estrategias para seleccionar vantage points."""
    RANDOM = "random"       # Aleatorio (rápido, baja calidad)
    K_MEDOIDS = "k_medoids" # 🔴 Por defecto (óptimo)
    MAX_SPREAD = "max_spread"  # Máxima varianza
```

| Estrategia | Complejidad | Calidad | Uso |
|------------|-------------|---------|-----|
| RANDOM | O(1) | Baja | Construcción rápida |
| K_MEDOIDS | O(n·k) | **Alta** | **Producción** |
| MAX_SPREAD | O(n·k) | Media-Alta | Alternativa |

---

## 3. Algoritmo K-Medoids

### 3.1 Concepto

El **medoid** es el punto que **minimiza la suma de distancias** a todos los demás puntos del conjunto. Es más robusto que el centroide (k-means) porque:

- No requiere calcular promedios (válido para cualquier métrica)
- Siempre es un punto real del dataset
- Más resistente a outliers

### 3.2 Fórmula

Para un conjunto de puntos $P$, el medoid $m$ es:

$$
m = \arg\min_{p \in P} \sum_{q \in P} d(p, q)
$$

### 3.3 Implementación

```python
# backend/app/core/partitioning/vp_tree.py

def _select_vantage_point_kmedoids(
    self,
    documents: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], int]:
    """
    Selecciona VP usando enfoque k-medoids.
    
    Encuentra el documento que minimiza la suma de distancias
    a todos los demás (el medoid).
    """
    n = len(documents)
    
    # Muestrear candidatos para eficiencia
    if n <= self.sample_size:
        candidates = list(range(n))
    else:
        candidates = random.sample(range(n), self.sample_size)
    
    best_idx = candidates[0]
    best_total_dist = float('inf')
    
    for idx in candidates:
        # Calcular suma de distancias a todos los documentos
        total_dist = 0.0
        for j in range(n):
            if j != idx:
                total_dist += self._distance(documents[idx], documents[j])
        
        # Actualizar mejor candidato
        if total_dist < best_total_dist:
            best_total_dist = total_dist
            best_idx = idx
    
    return documents[best_idx], best_idx
```

### 3.4 Visualización

```
Documentos: [D1, D2, D3, D4, D5]

Distancias (matriz simétrica):
       D1    D2    D3    D4    D5
D1     0    0.3   0.5   0.7   0.4
D2    0.3    0    0.4   0.6   0.3
D3    0.5   0.4    0    0.3   0.5
D4    0.7   0.6   0.3    0    0.6
D5    0.4   0.3   0.5   0.6    0

Suma de distancias:
D1: 0.3 + 0.5 + 0.7 + 0.4 = 1.9
D2: 0.3 + 0.4 + 0.6 + 0.3 = 1.6 ← Mínimo (MEDOID)
D3: 0.5 + 0.4 + 0.3 + 0.5 = 1.7
D4: 0.7 + 0.6 + 0.3 + 0.6 = 2.2
D5: 0.4 + 0.3 + 0.5 + 0.6 = 1.8

VP elegido: D2 (medoid del conjunto)
```

---

## 4. Estrategia MAX_SPREAD

Alternativa que maximiza la **varianza** de distancias:

```python
def _select_vantage_point_spread(
    self,
    documents: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], int]:
    """
    Selecciona VP que maximiza la dispersión de distancias.
    
    Un VP con alta varianza en distancias divide mejor el espacio.
    """
    n = len(documents)
    candidates = random.sample(range(n), min(self.sample_size, n))
    
    best_idx = candidates[0]
    best_spread = -1.0
    
    for idx in candidates:
        # Calcular distancias a todos
        distances = []
        for j in range(n):
            if j != idx:
                d = self._distance(documents[idx], documents[j])
                distances.append(d)
        
        # Spread = varianza de distancias
        if distances:
            spread = np.var(distances)
            if spread > best_spread:
                best_spread = spread
                best_idx = idx
    
    return documents[best_idx], best_idx
```

### 4.1 ¿Por qué varianza?

```
Candidato A (baja varianza):
  Distancias: [0.4, 0.42, 0.38, 0.41, 0.39]
  Varianza: 0.0002
  Problema: Todos los docs equidistantes → mala partición
  
Candidato B (alta varianza):
  Distancias: [0.1, 0.15, 0.8, 0.85, 0.9]
  Varianza: 0.12
  Ventaja: Clara separación entre cercanos y lejanos
```

---

## 5. Radio de Cobertura

Cada VP tiene un **radio** (median_distance) que define su región:

```
┌─────────────────────────────────────────────────────────────────┐
│                   RADIOS DE COBERTURA                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│               Espacio de documentos                             │
│                                                                 │
│         ╭─────────────────────────────────╮                    │
│        ╱                                   ╲                   │
│       │     ┌─────────┐       ┌─────────┐  │                   │
│       │    ╱    VP₁    ╲     ╱    VP₂    ╲ │                   │
│       │   │   r₁=0.3   │   │   r₂=0.4    ││                   │
│       │   │  ● ● ●     │   │    ● ● ●   ││                   │
│       │   │   ●  ●     │   │   ●   ●    ││                   │
│       │    ╲          ╱     ╲          ╱ │                    │
│       │     └────────┘       └─────────┘  │                   │
│        ╲                                  ╱                    │
│         ╰────────────────────────────────╯                     │
│                                                                 │
│  d(doc, VP₁) ≤ r₁ → Pertenece a región de VP₁                 │
│  d(doc, VP₂) ≤ r₂ → Pertenece a región de VP₂                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.1 Cálculo del Radio

```python
def _build_recursive(self, documents: List[Dict], depth: int = 0):
    # ... seleccionar VP ...
    
    # Calcular distancias desde VP
    distances = [(self._distance(vp, doc), doc) for doc in remaining]
    distances.sort(key=lambda x: x[0])
    
    # Mediana como radio
    median_idx = len(distances) // 2
    median_distance = distances[median_idx][0]  # Este es el RADIO
    
    # Particionar
    left_docs = [doc for d, doc in distances if d <= median_distance]
    right_docs = [doc for d, doc in distances if d > median_distance]
```

---

## 6. Recomputación al Cambiar Topología

Cuando un nodo se une o abandona el cluster:

```python
# backend/app/core/partitioning/partition_manager.py

async def on_node_join(self, new_node_id: str):
    """
    Maneja la incorporación de un nuevo nodo.
    """
    # 1. Registrar nuevo nodo
    self.node_assigner.register_node(new_node_id)
    
    # 2. Recalcular asignaciones de particiones
    cluster_nodes = [n.node_id for n in self.node_assigner.get_healthy_nodes()]
    
    self._partition_assignments = self.vp_tree.assign_nodes_to_partitions(
        cluster_nodes,
        strategy="balanced"
    )
    
    # 3. Identificar documentos a migrar
    migrations = self._identify_migrations(new_node_id)
    
    # 4. Migrar gradualmente
    for batch in chunks(migrations, 50):
        await self._migrate_batch(batch, new_node_id)
        await asyncio.sleep(1)  # Rate limiting

async def on_node_leave(self, failed_node_id: str):
    """
    Maneja la salida/fallo de un nodo.
    """
    # 1. Obtener documentos huérfanos
    orphaned = self.node_assigner.unregister_node(failed_node_id)
    
    # 2. Reasignar particiones
    cluster_nodes = [n.node_id for n in self.node_assigner.get_healthy_nodes()]
    
    self._partition_assignments = self.vp_tree.assign_nodes_to_partitions(
        cluster_nodes,
        strategy="balanced"
    )
    
    # 3. Recuperar documentos desde réplicas
    for doc_id in orphaned:
        await self._recover_from_replica(doc_id)
```

---

## 7. Impacto en Eficiencia de Búsqueda

### 7.1 VP Bien Elegido

```
Query: doc_ventas

VP bien elegido (central):
  ├── Distancia a VP = 0.3
  ├── median = 0.4
  ├── τ (radio de búsqueda) = 0.1
  │
  ├── Condición izquierda: 0.3 - 0.1 = 0.2 ≤ 0.4 ✓ BUSCAR
  └── Condición derecha:   0.3 + 0.1 = 0.4 = 0.4  ✗ PODAR
  
  Resultado: Solo buscamos 50% del árbol
```

### 7.2 VP Mal Elegido

```
VP mal elegido (extremo):
  Todos los documentos a distancia similar del VP
  ├── Distancias: [0.5, 0.51, 0.49, 0.52, ...]
  ├── median ≈ 0.5
  │
  ├── Cualquier query cercana al borde:
  │   ├── Condición izquierda: ✓ BUSCAR
  │   └── Condición derecha:   ✓ BUSCAR
  
  Resultado: Buscamos 100% del árbol (sin poda)
```

---

## 8. Trade-offs en Selección

| Aspecto | K_MEDOIDS | MAX_SPREAD | RANDOM |
|---------|-----------|------------|--------|
| Tiempo construcción | Medio | Medio | Muy rápido |
| Calidad partición | **Óptima** | Buena | Variable |
| Balanceo | **Excelente** | Bueno | Aleatorio |
| Robustez outliers | **Alta** | Media | Baja |
| Uso recomendado | **Producción** | Testing | Prototipo |

---

## 9. Ejemplo: Recomputación de VPs

```python
# Escenario: Nuevo nodo se une

# Estado inicial
vp_tree.root = VPNode(
    vantage_id="doc_central",
    median_distance=0.45,
    left=VPNode(assigned_node="slave_1", ...),
    right=VPNode(assigned_node="slave_2", ...)
)

# Nuevo nodo: slave_3 se une

# 1. No reconstruimos el árbol completo (costoso)
# 2. Solo reasignamos particiones

new_assignments = {
    "vpn_1": "slave_1",  # Sin cambio
    "vpn_2": "slave_3",  # Movido de slave_2 a slave_3
    "vpn_3": "slave_2",
    "vpn_4": "slave_3"   # Nueva asignación
}

# 3. Migrar documentos de particiones reasignadas
migrate(from="slave_2", to="slave_3", partition="vpn_2")
```

---

## 10. Persistencia de Vantage Points

```python
def save_vp_tree(self, path: str):
    """Guarda VP-Tree para recuperación."""
    state = {
        "root": self._serialize_node(self.root),
        "partition_assignments": self._partition_assignments,
        "metadata": {
            "document_count": self._document_count,
            "leaf_size": self.leaf_size,
            "created_at": datetime.utcnow().isoformat()
        }
    }
    
    with open(path, 'w') as f:
        json.dump(state, f)

def load_vp_tree(self, path: str):
    """Recupera VP-Tree desde disco."""
    with open(path, 'r') as f:
        state = json.load(f)
    
    self.root = self._deserialize_node(state["root"])
    self._partition_assignments = state["partition_assignments"]
```

---

## 11. Resumen de Propiedades

| Propiedad | Descripción |
|-----------|-------------|
| **Medoid** | Punto que minimiza distancia total |
| **Radio** | Distancia mediana al VP |
| **Región** | Todos los puntos a distancia ≤ radio |
| **Poda** | Descartar regiones fuera del radio de búsqueda |
| **Recomputo** | Solo asignaciones, no estructura (eficiente) |

---

> **Anterior**: [02_Algoritmo_Asignacion.md](02_Algoritmo_Asignacion.md)
> 
> **Siguiente sección**: [../04_Rebalanceo/README.md](../04_Rebalanceo/README.md)