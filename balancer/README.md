# Módulo Balancer - Data Balancer Distribuido

## 📋 Descripción

Sistema de balanceo de carga distribuido para DistriSearch. Gestiona el **índice global** de términos y el **registro de nodos**.

## 📁 Estructura

```
balancer/
├── __init__.py              # Exports públicos
├── global_index.py          # Índice global: término → nodos
├── node_registry.py         # Registro de nodos activos
├── balancer_core.py         # DataBalancer principal
└── balancer_snapshots.py    # Gestión de snapshots
```

## 🎯 Componentes

### 1. `global_index.py`
**Índice global distribuido:**
- Estructura: `término → {node_ids}`
- `add_term()`: Registrar término en nodo
- `get_nodes_for_term()`: Localizar nodos con término
- `get_nodes_for_terms()`: Localizar nodos (OR)
- `remove_node()`: Limpiar nodo completo

### 2. `node_registry.py`
**Registro de nodos:**
- `NodeMetadata`: Metadata de cada nodo
  - `node_id`, `address`, `port`
  - `last_heartbeat`, `document_count`, `term_count`
- `NodeRegistry`: Gestor de nodos
  - `register()`, `unregister()`
  - `heartbeat()`: Actualizar actividad
  - `get_active_nodes()`: Nodos vivos
  - `clean_dead_nodes()`: Eliminar inactivos

### 3. `balancer_core.py`
**DataBalancer principal:**
- Orquestador que combina GlobalIndex + NodeRegistry
- `locate_terms()`: ¿Dónde están estos términos?
- `update_node_index()`: Actualizar índice de nodo
- `register_node()` / `unregister_node()`
- `get_stats()`: Estadísticas del sistema

### 4. `balancer_snapshots.py`
**Gestión de snapshots:**
- `save_snapshot()`: Guardar estado completo
- `load_snapshot()`: Restaurar desde snapshot
- `list_snapshots()`: Listar backups

## 🔧 Uso

### Inicializar Data Balancer

```python
from balancer import DataBalancer
from storage.persistence import PersistenceManager

# Crear balancer
balancer = DataBalancer(node_id=100)

# Registrar nodos
balancer.register_node(1, "192.168.1.10", 8001)
balancer.register_node(2, "192.168.1.11", 8002)
balancer.register_node(3, "192.168.1.12", 8003)
```

### Actualizar Índice Global

```python
# Nodo 1 reporta sus términos
balancer.update_node_index(
    node_id=1,
    terms=["distributed", "consensus", "raft"]
)

# Nodo 2 reporta sus términos
balancer.update_node_index(
    node_id=2,
    terms=["hypercube", "routing", "network"]
)
```

### Localizar Términos

```python
# ¿Qué nodos tienen "consensus" o "raft"?
node_ids = balancer.locate_terms(["consensus", "raft"])
# {1}

# ¿Qué nodos tienen "hypercube"?
node_ids = balancer.locate_term("hypercube")
# {2}
```

### Heartbeats

```python
# Nodo envía heartbeat con stats
balancer.heartbeat(
    node_id=1,
    doc_count=150,
    term_count=500
)

# Verificar nodos activos
active = balancer.get_active_nodes()
# {1, 2, 3}
```

### Snapshots

```python
from balancer import SnapshotManager

# Crear gestor
persistence = PersistenceManager("data/balancer_0")
snapshots = SnapshotManager(balancer, persistence)

# Guardar snapshot
snapshots.save_snapshot("backup_latest")

# Restaurar
snapshots.load_snapshot("backup_latest")

# Listar backups
all_snapshots = snapshots.list_snapshots()
```

## 📊 Arquitectura

```
┌─────────────────────────────────────┐
│       DataBalancer (Líder)          │
├─────────────────────────────────────┤
│  GlobalIndex    │  NodeRegistry     │
│  término→nodos  │  nodos activos    │
└─────────────────────────────────────┘
          ▲                 ▲
          │ update_index    │ heartbeat
          │                 │
    ┌─────┴─────┬───────────┴────┬──────────┐
    │           │                │          │
  Node 1      Node 2          Node 3     Node 4
  (doc1-3)    (doc4-6)        (doc7-9)   (doc10-12)
```

## 🔍 Flujo de Búsqueda

1. **Cliente** envía query a cualquier nodo
2. **Nodo** tokeniza query → términos
3. **Nodo** contacta DataBalancer: `locate_terms(términos)`
4. **DataBalancer** retorna `{node_ids}` que tienen términos
5. **Nodo** contacta nodos relevantes en paralelo
6. **Nodo** agrega resultados y rankea (TF-IDF)
7. **Nodo** retorna top-K resultados a cliente

## 📈 Estadísticas

```python
stats = balancer.get_stats()
# {
#   "node_id": 100,
#   "global_index": {
#     "terms": 1500,
#     "nodes": 8
#   },
#   "node_registry": {
#     "total_nodes": 8,
#     "active_nodes": 7,
#     "total_documents": 1200,
#     "total_terms": 5000
#   }
# }
```

## 🎛️ Configuración de Heartbeat

```python
HEARTBEAT_TIMEOUT = 30.0  # segundos sin heartbeat → nodo muerto

# Limpiar nodos muertos periódicamente
removed = balancer.node_registry.clean_dead_nodes(timeout=30.0)
print(f"Eliminados {removed} nodos inactivos")
```

## 🚀 Escalabilidad

### Problema Original (Bottleneck)
❌ **Un único DataBalancer** → cuello de botella M/M/1

### Solución Propuesta
✅ **Múltiples DataBalancers** (uno por shard):
- Sharding por consistant hashing
- Cada shard tiene su DataBalancer
- Reducir carga de N/16 (para 16 shards)

```python
# En lugar de UN balancer global
balancer_global = DataBalancer()

# Usar 16 balancers (uno por shard)
balancers = [DataBalancer(i) for i in range(16)]

# Localizar término → determinar shard → consultar balancer[shard]
shard = hash(term) % 16
nodes = balancers[shard].locate_term(term)
```

## 📊 Persistencia

```python
# Guardar estado completo
data = balancer.to_dict()
persistence.save_json("global_index.json", data["global_index"])
persistence.save_json("nodes_metadata.json", data["nodes_metadata"])

# Cargar estado
global_data = persistence.load_json("global_index.json")
nodes_data = persistence.load_json("nodes_metadata.json")

balancer.from_dict({
    "global_index": global_data,
    "nodes_metadata": nodes_data
})
```

## ✅ Garantías

1. **Consistencia eventual**: Índice global se actualiza por heartbeats
2. **Fault tolerance**: Si un nodo muere, se limpia en 30s
3. **Idempotencia**: Actualizar mismo término varias veces es seguro

## 🔄 Integración con Consensus

Para **alta disponibilidad**, el DataBalancer puede usar Raft:

```python
# DataBalancer líder replica su estado
if raft.is_leader():
    await raft.replicate_command({
        "type": "update_index",
        "node_id": 1,
        "terms": ["consensus", "raft"]
    })
```

## 🚧 Mejoras Futuras

- [ ] Sharding del índice global (16 shards)
- [ ] Replicación del DataBalancer (k=3)
- [ ] Caché de locate_terms() (LRU)
- [ ] Compresión de snapshots
- [ ] Métricas Prometheus
