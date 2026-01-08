# Sistema de Particionamiento

## Particionamiento Semántico con VP-Tree Distribuido

---

## 1. Visión General

DistriSearch utiliza **VP-Trees (Vantage-Point Trees)** para particionar documentos basándose en **similaridad semántica**, no en hash. Esto garantiza que documentos similares residan en el mismo nodo.

```
┌─────────────────────────────────────────────────────────────────┐
│              PARTICIONAMIENTO CON VP-TREE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    [Centroide Global]                           │
│                          │                                      │
│            ┌─────────────┼─────────────┐                       │
│            │             │             │                        │
│       [Nodo_1]      [Nodo_2]      [Nodo_3]                     │
│       d < r₁        r₁ ≤ d < r₂    d ≥ r₂                      │
│         │             │             │                           │
│    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐                     │
│    │ Docs    │   │ Docs    │   │ Docs    │                     │
│    │similares│   │similares│   │similares│                     │
│    │ a VP₁   │   │ a VP₂   │   │ a VP₃   │                     │
│    └─────────┘   └─────────┘   └─────────┘                     │
│                                                                 │
│  Cada nodo del cluster = Una región del espacio métrico        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. ¿Por Qué VP-Tree en Lugar de Hash?

| Hash Tradicional | VP-Tree Semántico |
|------------------|-------------------|
| Distribución aleatoria | Distribución por similaridad |
| Documentos similares dispersos | Documentos similares agrupados |
| Búsqueda requiere todos los nodos | Búsqueda dirigida a nodos relevantes |
| No preserva localidad | Preserva localidad semántica |

### 2.1 Ventaja Clave

Con VP-Tree, una búsqueda puede **podar nodos** que no contienen documentos relevantes:

```
Búsqueda: "reporte ventas Q1"

Hash tradicional:
  ├── Consultar Nodo 1 ✓
  ├── Consultar Nodo 2 ✓
  └── Consultar Nodo 3 ✓  → 3 consultas

VP-Tree:
  ├── Calcular distancia a VPs
  ├── Nodo 2 contiene docs similares
  └── Consultar solo Nodo 2 ✓  → 1 consulta
```

---

## 3. Arquitectura de Particionamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                 COMPONENTES DE PARTICIONAMIENTO                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  backend/app/core/partitioning/                                │
│  ├── vp_tree.py           # 🔴 VP-Tree principal               │
│  ├── node_assignment.py   # Asignación a nodos                 │
│  ├── partition_manager.py # 🔴 Coordinador de alto nivel       │
│  └── distance_metrics.py  # Métricas de distancia              │
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│                                                                 │
│  ┌──────────────────┐     ┌──────────────────┐                 │
│  │ PartitionManager │────▶│     VPTree       │                 │
│  │ (coordinador)    │     │ (estructura)     │                 │
│  └────────┬─────────┘     └──────────────────┘                 │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────┐     ┌──────────────────┐                 │
│  │  NodeAssigner    │────▶│ DistanceCalculator│                │
│  │ (balanceo)       │     │ (métricas)       │                 │
│  └──────────────────┘     └──────────────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Fórmula de Distancia

La distancia entre documentos usa la combinación ponderada:

$$
d(A, B) = 0.4 \cdot d_{name} + 0.4 \cdot d_{content} + 0.2 \cdot d_{topic}
$$

Donde:
- $d_{name}$ = distancia coseno de TF-IDF del nombre
- $d_{content}$ = distancia Jaccard de MinHash
- $d_{topic}$ = divergencia Jensen-Shannon de LDA

```python
# backend/app/core/partitioning/distance_metrics.py

@dataclass
class DistanceWeights:
    """Pesos para cálculo de distancia combinada."""
    name_weight: float = 0.4
    content_weight: float = 0.4
    topic_weight: float = 0.2
```

---

## 5. Flujo de Particionamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                  FLUJO DE PARTICIONAMIENTO                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. CONSTRUCCIÓN (al iniciar cluster)                          │
│     ├── Recopilar todos los documentos                         │
│     ├── Calcular vectores para cada documento                  │
│     ├── Construir VP-Tree con k-medoids                        │
│     └── Asignar particiones a nodos del cluster                │
│                                                                 │
│  2. INSERCIÓN (nuevo documento)                                │
│     ├── Calcular vector del documento                          │
│     ├── Encontrar partición en VP-Tree                         │
│     ├── Obtener nodo asignado a esa partición                  │
│     └── Almacenar documento en ese nodo                        │
│                                                                 │
│  3. BÚSQUEDA                                                    │
│     ├── Calcular vector de la query                            │
│     ├── Identificar particiones relevantes                     │
│     ├── Consultar solo nodos de esas particiones               │
│     └── Agregar y ordenar resultados                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Índice de Contenidos

| Archivo | Descripción |
|---------|-------------|
| [01_VP_Tree_Distribuido.md](01_VP_Tree_Distribuido.md) | Estructura del VP-Tree distribuido |
| [02_Algoritmo_Asignacion.md](02_Algoritmo_Asignacion.md) | Algoritmo de asignación de documentos |
| [03_Vantage_Points.md](03_Vantage_Points.md) | Selección y gestión de vantage points |

---

## 7. Clase Principal: PartitionManager

```python
# backend/app/core/partitioning/partition_manager.py

class PartitionManager:
    """
    Gestor de particionamiento y enrutamiento de documentos.
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
        self.node_assigner = NodeAssigner(replication_factor=replication_factor)
    
    def route_document(self, document: Dict) -> RoutingResult:
        """Enruta documento al nodo apropiado."""
        partition_id = self.vp_tree.find_partition(document)
        primary_node = self._partition_assignments[partition_id]
        return RoutingResult(
            document_id=document["id"],
            partition_id=partition_id,
            primary_node=primary_node
        )
```

---

> **Anterior**: [../02_Vectorizacion_Busqueda/README.md](../02_Vectorizacion_Busqueda/README.md)
> 
> **Siguiente**: [01_VP_Tree_Distribuido.md](01_VP_Tree_Distribuido.md)