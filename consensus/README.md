# Módulo Consensus - Raft Completo

## 📋 Descripción

Implementación completa del algoritmo de consenso **Raft** para DistriSearch.

## 📁 Estructura

```
consensus/
├── raft_state.py         # Estados, mensajes y configuración
├── raft_election.py      # Elección de líder
├── raft_replication.py   # Replicación de log y heartbeats
└── raft_consensus.py     # Orquestador principal
```

## 🎯 Componentes

### 1. `raft_state.py`
**Estructuras de datos fundamentales:**
- `NodeState`: Enum (FOLLOWER, CANDIDATE, LEADER)
- `RaftMessage`: Mensajes entre nodos
- `LogEntry`: Entradas del log replicado
- `RaftState`: Estado compartido de Raft
- `RaftConfig`: Configuración de timeouts

### 2. `raft_election.py`
**Elección de líder:**
- Election timer con timeout aleatorio
- RequestVote protocol
- Votación basada en term y log staleness
- Cálculo de quorum
- Transición automática a LEADER al ganar elección

### 3. `raft_replication.py`
**Replicación del log:**
- Heartbeat loop periódico
- AppendEntries protocol
- Verificación de consistencia del log
- Actualización de commit_index basada en quorum
- Replicación de comandos con garantía de mayoría

### 4. `raft_consensus.py`
**Orquestador principal:**
- Combina election + replication
- API unificada para consenso
- `replicate_command()`: Replicación de comandos
- `wait_for_leader_election()`: Esperar líder
- `get_stats()`: Estadísticas del consenso

## 🔧 Uso

```python
from consensus import RaftConsensus

# Inicializar
raft = RaftConsensus(
    node_id=1,
    all_node_ids={1, 2, 3},
    network=network_instance
)

# Iniciar consenso
await raft.start()

# Esperar líder
leader_id = await raft.wait_for_leader_election(timeout=10.0)

# Si soy líder, replicar comando
if raft.is_leader():
    success = await raft.replicate_command({
        "type": "add_document",
        "doc_id": "doc1",
        "content": "Hello World"
    })

# Detener
await raft.stop()
```

## 🎛️ Configuración

```python
from consensus.raft_state import RaftConfig

config = RaftConfig(
    ELECTION_TIMEOUT_RANGE=(3.0, 6.0),
    HEARTBEAT_INTERVAL=1.0
)

raft = RaftConsensus(..., config=config)
```

## 📊 Garantías

1. **Safety**: Solo un líder por term
2. **Log Matching**: Logs idénticos hasta commit_index
3. **Leader Completeness**: Líder tiene todas las entradas commiteadas
4. **State Machine Safety**: Misma secuencia de comandos

## 🔍 Estados del Nodo

```
FOLLOWER:
  - Espera heartbeats del líder
  - Si timeout → inicia elección

CANDIDATE:
  - Solicita votos (RequestVote)
  - Si mayoría → se convierte en LEADER
  - Si descubre nuevo líder → vuelve a FOLLOWER

LEADER:
  - Envía heartbeats periódicos
  - Replica comandos a followers
  - Avanza commit_index cuando mayoría confirma
```

## 📈 Métricas

```python
stats = raft.get_stats()
# {
#   "node_id": 1,
#   "state": "LEADER",
#   "term": 5,
#   "leader_id": 1,
#   "commit_index": 10,
#   "log_length": 12,
#   "running": True
# }
```

## ✅ Tests

El módulo está diseñado para ser testeado con:
- `tests/test_election.py`: Elecciones y timeouts
- `tests/test_integration.py`: Consenso completo

## 🚀 Mejoras Futuras

- [ ] Compactación de log (log compaction)
- [ ] Snapshots distribuidos
- [ ] Configuración dinámica de cluster
- [ ] Pre-vote optimization
- [ ] Transferencia de liderazgo
