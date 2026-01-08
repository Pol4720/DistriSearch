# Power of Two Choices

## Fundamento Teórico

**"The Power of Two Choices"** es un algoritmo de balanceo de carga que reduce drásticamente la varianza en comparación con la asignación aleatoria simple. Fue introducido por Azar, Broder, Karlin y Upfal en 1994.

### Intuición

En lugar de elegir un nodo al azar para colocar un documento:
1. Seleccionar **2 nodos candidatos** al azar
2. Elegir el **menos cargado** de los dos

Este simple cambio reduce la carga máxima de $O(\log n / \log \log n)$ a $O(\log \log n)$.

## Comparación: Random vs Power of Two

```
                    ASIGNACIÓN ALEATORIA SIMPLE
┌─────────────────────────────────────────────────────────────────┐
│   Cada documento → 1 nodo aleatorio                             │
│                                                                  │
│   Nodo_1: ████████████████████████████████████  36 docs         │
│   Nodo_2: ████████████                          12 docs         │
│   Nodo_3: ██████████████████████████████        30 docs         │
│   Nodo_4: ██████████████████████                22 docs         │
│                                                                  │
│   Varianza: ALTA    Carga máxima: 36 (desbalanceado)            │
└─────────────────────────────────────────────────────────────────┘

                    POWER OF TWO CHOICES
┌─────────────────────────────────────────────────────────────────┐
│   Cada documento → mejor de 2 nodos aleatorios                  │
│                                                                  │
│   Nodo_1: █████████████████████████            25 docs          │
│   Nodo_2: █████████████████████████            25 docs          │
│   Nodo_3: █████████████████████████            25 docs          │
│   Nodo_4: █████████████████████████            25 docs          │
│                                                                  │
│   Varianza: BAJA    Carga máxima: 25 (equilibrado)              │
└─────────────────────────────────────────────────────────────────┘
```

## Complejidad Matemática

| Estrategia | Carga Máxima Esperada | Varianza |
|------------|----------------------|----------|
| Random | $\Theta(\frac{\log n}{\log \log n})$ | Alta |
| Power of 2 | $\Theta(\log \log n)$ | Baja |
| Power of d | $\Theta(\frac{\log \log n}{\log d})$ | Muy baja |

Para $n = 10^6$ nodos:
- Random: ~5-6 veces el promedio
- Power of 2: ~2-3 veces el promedio

## Implementación en DistriSearch

DistriSearch combina Power of Two Choices con **afinidad semántica**:

```python
# Del reporte técnico (report.tex)
def select_migration_target(doc, cluster):
    """
    Power of Two Choices + Afinidad Semántica
    """
    # 1. Seleccionar 2 nodos candidatos al azar
    choice1, choice2 = random.sample(cluster.nodes, 2)
    
    # 2. Calcular score combinado para cada candidato
    score1 = calculate_combined_score(doc, choice1)
    score2 = calculate_combined_score(doc, choice2)
    
    # 3. Elegir el mejor
    return choice1 if score1 > score2 else choice2


def calculate_combined_score(doc, node):
    """
    Score combinado: afinidad semántica + carga inversa
    
    α = 0.6 (peso afinidad)
    """
    alpha = 0.6
    
    # Afinidad semántica: coseno entre doc y centroide del nodo
    affinity = cosine_similarity(doc.vector, node.centroid)
    
    # Carga inversa (menor carga = mejor score)
    load = node.document_count / node.capacity
    load_score = 1 - load
    
    return alpha * affinity + (1 - alpha) * load_score
```

## Fórmulas del Score

### Score de Afinidad
$$affinity(doc, node) = \cos(\mathbf{v}_{doc}, \text{centroid}_{node}) = \frac{\mathbf{v}_{doc} \cdot \text{centroid}_{node}}{\|\mathbf{v}_{doc}\| \cdot \|\text{centroid}_{node}\|}$$

### Score de Carga
$$load\_score(node) = 1 - \frac{document\_count}{capacity}$$

### Score Combinado
$$score(doc, node) = \alpha \cdot affinity + (1 - \alpha) \cdot load\_score$$

Donde $\alpha = 0.6$ prioriza la afinidad semántica sobre la carga.

## Algoritmo de Rebalanceo con Power of Two Choices

```
Algorithm: Rebalance with Power of Two Choices
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT: cluster, event (NODE_JOIN | NODE_LEAVE | IMBALANCE)
OUTPUT: cluster rebalanceado

1. IF event.type = NODE_JOIN:
   2.   overloaded ← GetOverloadedNodes(cluster)  // >120% promedio
   3.   FOR EACH node IN overloaded:
   4.     docs_to_migrate ← SelectMigrationCandidates(node)
   5.     FOR EACH doc IN docs_to_migrate:
   6.       choice1, choice2 ← RandomSample(cluster.nodes, 2)
   7.       score1 ← α·affinity(doc,choice1) + (1-α)·(1-load(choice1))
   8.       score2 ← α·affinity(doc,choice2) + (1-α)·(1-load(choice2))
   9.       best ← choice1 IF score1 > score2 ELSE choice2
  10.       Migrate(doc, node, best)
  11.     END FOR
  12.   END FOR

13. ELSE IF event.type = NODE_LEAVE:
  14.   orphan_docs ← event.node.documents
  15.   FOR EACH doc IN orphan_docs:
  16.     target ← FindBestNode(doc, cluster)  // Por afinidad
  17.     RestoreFromReplica(doc, target)
  18.   END FOR
  19. END IF
```

## Ejemplo Visual

```
                     POWER OF TWO CHOICES
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   Documento: "reporte_ventas_Q1.xlsx"                   │
    │   Vector: [0.8, 0.3, 0.1, ...]                          │
    │                                                         │
    │                        ↓                                │
    │                                                         │
    │   ┌─────────────────────────────────────────────────┐   │
    │   │     Seleccionar 2 nodos al azar                 │   │
    │   └─────────────────────────────────────────────────┘   │
    │                        ↓                                │
    │         ┌──────────────┴──────────────┐                │
    │         │                             │                │
    │    ┌─────────┐                   ┌─────────┐           │
    │    │ Nodo_2  │                   │ Nodo_4  │           │
    │    │         │                   │         │           │
    │    │ Load:70%│                   │ Load:30%│           │
    │    │ Aff:0.85│                   │ Aff:0.45│           │
    │    └─────────┘                   └─────────┘           │
    │         │                             │                │
    │    Score: 0.6×0.85               Score: 0.6×0.45       │
    │         + 0.4×0.30                    + 0.4×0.70       │
    │         = 0.63 ✓                      = 0.55           │
    │         │                                              │
    │         ▼                                              │
    │   ┌─────────────────────────────────────────────────┐   │
    │   │  Documento asignado a Nodo_2 (mayor afinidad)   │   │
    │   └─────────────────────────────────────────────────┘   │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

## Beneficios en DistriSearch

### 1. Reducción de Varianza
- Distribución más uniforme de documentos
- Menos "hotspots" (nodos sobrecargados)

### 2. Preservación de Localidad Semántica
- Documentos similares tienden a quedar juntos
- Búsquedas más eficientes (menos nodos a consultar)

### 3. Balanceo Adaptativo
- Considera carga actual, no solo capacidad
- Se adapta a patrones de uso

### 4. Simplicidad
- Solo 2 comparaciones por documento
- Overhead mínimo vs random simple

## Implementación en LoadCalculator

```python
# backend/app/core/rebalancing/load_calculator.py

def get_migration_candidates(
    self,
    source_node: str,
    count: int
) -> Dict[str, Any]:
    """Get information for selecting migration candidates."""
    return {
        "source_node": source_node,
        "count": count,
        "criteria": {
            # Prefer documents that:
            # 1. Have low access frequency
            # 2. Are semantically distant from node's centroid
            # 3. Have recently completed replication
            "prefer_low_access": True,
            "prefer_semantic_outliers": True,  # Docs en el "borde"
            "require_replicated": True         # Seguridad
        }
    }
```

## Selección de Candidatos a Migrar

Para Power of Two Choices, no todos los documentos son candidatos. Se priorizan:

1. **Documentos "frontera"**: Los más lejanos del centroide del nodo actual
2. **Documentos poco accedidos**: Migrarlos tiene menor impacto
3. **Documentos ya replicados**: Menor riesgo de pérdida

```python
def _get_documents_to_migrate(
    self, 
    node_id: str, 
    target_count: int
) -> List[Document]:
    """Selecciona documentos para migrar usando criterio de frontera."""
    docs = self.partition_index.get_documents_in_node(node_id)
    vp = self.vantage_points[node_id]
    
    # Ordenar por distancia al VP (los más lejanos son candidatos)
    docs.sort(key=lambda d: d.compute_distance(vp), reverse=True)
    
    return docs[:target_count]
```

---

**Navegación:**
- [← Anterior: Rebalanceo Activo](01_Rebalanceo_Activo.md)
- [→ Siguiente: Migración de Documentos](03_Migracion_Documentos.md)
