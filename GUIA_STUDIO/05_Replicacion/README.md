# 05. Replicación con Afinidad Semántica

## Visión General

DistriSearch implementa un sistema de **replicación inteligente** que no solo garantiza tolerancia a fallos, sino que también optimiza el rendimiento de búsquedas colocando réplicas en nodos que contienen documentos semánticamente similares.

## ¿Por Qué Replicar?

```
┌──────────────────────────────────────────────────────────────────────┐
│                      SIN REPLICACIÓN                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Nodo_1: [Doc_A] [Doc_B] [Doc_C]                                   │
│   Nodo_2: [Doc_D] [Doc_E] [Doc_F]                                   │
│   Nodo_3: [Doc_G] [Doc_H] [Doc_I]                                   │
│                                                                      │
│   ⚠️ Si Nodo_1 falla → Doc_A, Doc_B, Doc_C PERDIDOS                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      CON REPLICACIÓN (factor=2)                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Nodo_1: [Doc_A●] [Doc_B●] [Doc_C●] [Doc_D○] [Doc_E○]              │
│   Nodo_2: [Doc_D●] [Doc_E●] [Doc_F●] [Doc_A○] [Doc_B○]              │
│   Nodo_3: [Doc_G●] [Doc_H●] [Doc_I●] [Doc_C○] [Doc_F○]              │
│                                                                      │
│   ● = Primario    ○ = Réplica                                       │
│                                                                      │
│   ✓ Si Nodo_1 falla → Doc_A, Doc_B, Doc_C disponibles en réplicas  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Replicación con Afinidad Semántica

La innovación de DistriSearch es colocar réplicas **estratégicamente**:

```
┌──────────────────────────────────────────────────────────────────────┐
│            REPLICACIÓN TRADICIONAL (Random/Round-Robin)             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ventas_q1.xlsx (primario: Nodo_1, réplica: Nodo_3)               │
│   ventas_q2.xlsx (primario: Nodo_2, réplica: Nodo_1)               │
│   ventas_q3.xlsx (primario: Nodo_3, réplica: Nodo_2)               │
│                                                                      │
│   Búsqueda "ventas" → consultar 3 nodos                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│            REPLICACIÓN CON AFINIDAD SEMÁNTICA                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Nodo_1: ventas_q1● ventas_q2○ ventas_q3○  ← Cluster semántico    │
│   Nodo_2: marketing_q1● marketing_q2○                               │
│   Nodo_3: rrhh_contratos● rrhh_nominas○                             │
│                                                                      │
│   Búsqueda "ventas" → consultar solo Nodo_1 (tiene todo)           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Arquitectura del Sistema de Replicación

```
┌────────────────────────────────────────────────────────────────────┐
│                  SISTEMA DE REPLICACIÓN                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ┌──────────────────┐    ┌──────────────────────┐                │
│   │ SimilarityGraph  │◄───│  AffinityReplicator  │                │
│   │                  │    │                      │                │
│   │ • Nodos = docs   │    │ • Selección nodos    │                │
│   │ • Aristas = sim  │    │ • Cola de tareas     │                │
│   │ • Vecinos        │    │ • Re-replicación     │                │
│   └──────────────────┘    └──────────┬───────────┘                │
│                                      │                             │
│                                      ▼                             │
│                           ┌──────────────────────┐                │
│                           │   ReplicaTracker     │                │
│                           │                      │                │
│                           │ • Estado réplicas    │                │
│                           │ • Under-replication  │                │
│                           │ • Versiones          │                │
│                           └──────────────────────┘                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Componentes Principales

| Componente | Archivo | Responsabilidad |
|------------|---------|------------------|
| `AffinityReplicator` | `affinity_replicator.py` | Orquesta la replicación con afinidad |
| `SimilarityGraph` | `similarity_graph.py` | Grafo de similaridad entre documentos |
| `ReplicaTracker` | `replica_tracker.py` | Seguimiento del estado de réplicas |

## Flujo de Replicación

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Documento   │────►│ Calcular        │────►│ Seleccionar     │
│ nuevo       │     │ similaridad     │     │ nodos réplica   │
└─────────────┘     └─────────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Actualizar  │◄────│ Ejecutar        │◄────│ Encolar tarea   │
│ tracker     │     │ replicación     │     │ de replicación  │
└─────────────┘     └─────────────────┘     └─────────────────┘
```

## Fórmulas Clave

### Score de Afinidad de Nodo
$$affinity(doc, node) = \sum_{neighbor \in node.docs} similarity(doc, neighbor)$$

### Selección de Nodo Réplica
$$best\_node = \arg\max_{node \in candidates} affinity(doc, node)$$

## Contenido de Esta Sección

1. **[Afinidad Semántica](01_Afinidad_Semantica.md)**: Por qué y cómo usar afinidad
2. **[Grafo de Similaridad](02_Grafo_Similaridad.md)**: Estructura del grafo
3. **[Factor de Replicación](03_Factor_Replicacion.md)**: Configuración y trade-offs

---

**Navegación:**
- [← Anterior: Rebalanceo](../04_Rebalanceo/README.md)
- [→ Siguiente: Tolerancia a Fallos](../06_Tolerancia_Fallos/README.md)
