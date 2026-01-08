# Visión del Sistema Master-Slave

## Patrón Arquitectónico de DistriSearch

---

## 1. ¿Qué es el Patrón Master-Slave?

El patrón **Master-Slave** (también llamado Primary-Replica) es una arquitectura donde:

- **Un nodo Master** coordina y toma decisiones globales
- **Múltiples nodos Slave** ejecutan el trabajo y almacenan datos
- El Master tiene **visión global** del sistema
- Los Slaves operan de forma **semi-autónoma**

```
                    ┌─────────────────────────┐
                    │        MASTER           │
                    │   (Coordinador Global)  │
                    │                         │
                    │  • Visión del cluster   │
                    │  • Toma de decisiones   │
                    │  • Rebalanceo           │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │    SLAVE 1    │   │    SLAVE 2    │   │    SLAVE N    │
    │               │   │               │   │               │
    │ • Autónomo    │   │ • Autónomo    │   │ • Autónomo    │
    │ • Datos local │   │ • Datos local │   │ • Datos local │
    │ • Búsquedas   │   │ • Búsquedas   │   │ • Búsquedas   │
    └───────────────┘   └───────────────┘   └───────────────┘
```

---

## 2. Rol del Master Node

### 2.1 Responsabilidades Principales

El Master en DistriSearch tiene las siguientes funciones:

| Responsabilidad | Descripción | Componente |
|-----------------|-------------|------------|
| **VP-Tree Global** | Mantiene el árbol de particionamiento semántico | `backend/app/core/partitioning/` |
| **Coordinación de Particiones** | Decide qué documentos van a qué nodos | `VPTreePartitioner` |
| **Consenso Raft** | Elección de líder y replicación de estado | `backend/app/distributed/consensus/` |
| **Rebalanceo Activo** | Redistribuye documentos cuando cambia la topología | `ActiveRebalancer` |
| **Registro de Nodos** | Mantiene el estado de todos los Slaves | `NodeRegistry` |

### 2.2 VP-Tree Global

El Master mantiene un **Vantage-Point Tree** que particiona el espacio vectorial:

```
                         [Centroide Global]
                               │
               ┌───────────────┼───────────────┐
               │               │               │
         [VP_Slave1]     [VP_Slave2]     [VP_Slave3]
         d < r₁          r₁ ≤ d < r₂     d ≥ r₂
               │               │               │
         ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
         │Documentos │   │Documentos │   │Documentos │
         │similares  │   │similares  │   │similares  │
         │al VP₁     │   │al VP₂     │   │al VP₃     │
         └───────────┘   └───────────┘   └───────────┘

VP = Vantage Point (punto de referencia)
d = distancia semántica del documento
r₁, r₂ = radios de cobertura
```

**¿Cómo funciona la asignación?**

```python
# Pseudocódigo del algoritmo de asignación (simplificado)
class VPTreePartitioner:
    def assign_document(self, doc_vector) -> str:
        """Encuentra el nodo más apropiado para un documento."""
        best_node = None
        best_distance = float('inf')
        
        for node_id, vantage_point in self.vantage_points.items():
            distance = doc_vector.compute_distance(vantage_point)
            if distance < best_distance:
                best_distance = distance
                best_node = node_id
        
        return best_node
```

### 2.3 Consenso Raft para Alta Disponibilidad

El Master utiliza **Raft** para garantizar que siempre haya un líder:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESTADOS DE RAFT                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│    ┌──────────┐    timeout    ┌──────────────┐                 │
│    │ FOLLOWER │──────────────►│  CANDIDATE   │                 │
│    │          │◄──────────────│              │                 │
│    └──────────┘  otro líder   └──────┬───────┘                 │
│         ▲                            │                          │
│         │                            │ mayoría                  │
│         │  pierde liderazgo          │ de votos                 │
│         │                            ▼                          │
│         │                     ┌──────────────┐                 │
│         └─────────────────────│    LEADER    │                 │
│                               │              │                 │
│                               └──────────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Configuración Raft en DistriSearch** (de `backend/app/config.py`):

```python
# Raft Consensus (milliseconds)
raft_election_timeout_min: int = 150   # Timeout mínimo para elección
raft_election_timeout_max: int = 300   # Timeout máximo para elección
raft_heartbeat_interval: int = 50      # Intervalo de heartbeat del líder
```

### 2.4 Rebalanceo Activo

Cuando un nodo se une o abandona el cluster:

```
┌──────────────────────────────────────────────────────────────────┐
│                 PROCESO DE REBALANCEO                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DETECCIÓN: Nuevo nodo N₄ se une al cluster                  │
│                                                                  │
│  2. ANÁLISIS: Master calcula carga actual                       │
│     Slave1: 45% ████████░░░░░░                                  │
│     Slave2: 80% ████████████████░░░                             │
│     Slave3: 75% ███████████████░░░░                             │
│     Slave4: 0%  ░░░░░░░░░░░░░░░░░░░ (nuevo)                     │
│                                                                  │
│  3. SELECCIÓN: Identificar documentos a migrar                  │
│     - Docs en nodos sobrecargados (>70%)                        │
│     - Docs cuyo VP más cercano ahora es N₄                      │
│                                                                  │
│  4. MIGRACIÓN GRADUAL:                                          │
│     - Transferir en batches de 50 documentos                    │
│     - Rate limiting: 1 segundo entre batches                    │
│     - Mantener réplica temporal hasta confirmar                 │
│                                                                  │
│  5. ACTUALIZACIÓN: Recalcular VP-Tree                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Rol de los Nodos Slave

### 3.1 Arquitectura de un Slave

Cada Slave es una **unidad autónoma** que contiene todo lo necesario:

```
┌─────────────────────────────────────────────────────────────────┐
│                        SLAVE NODE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    NGINX (puerto 443)                    │   │
│  │  • Sirve Frontend estático                               │   │
│  │  • Proxy reverso al Backend                              │   │
│  │  • SSL/TLS                                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              FRONTEND (React + TypeScript)               │   │
│  │  • Archivos estáticos servidos por Nginx                 │   │
│  │  • SPA (Single Page Application)                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              BACKEND (FastAPI - puerto 8000)             │   │
│  │                                                          │   │
│  │  • API REST                                              │   │
│  │  • Motor de vectorización (TF-IDF + MinHash)            │   │
│  │  • Índice VP-Tree local                                  │   │
│  │  • WebSocket para updates en tiempo real                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐            │
│         │                    │                    │            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│  │  MongoDB    │     │   Redis     │     │   SQLite    │      │
│  │  (docs)     │     │  (cache)    │     │  (users)    │      │
│  │             │     │             │     │  +Raft      │      │
│  └─────────────┘     └─────────────┘     └─────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Operación Autónoma

Los Slaves pueden funcionar **independientemente** del Master:

| Operación | ¿Requiere Master? | Motivo |
|-----------|-------------------|--------|
| Autenticación de usuarios | ❌ No | SQLite local con Raft |
| Búsqueda en documentos locales | ❌ No | MongoDB e índice local |
| Consultar caché | ❌ No | Redis local |
| Subir nuevo documento | ✅ Sí | Master asigna nodo destino |
| Búsqueda distribuida | ✅ Sí | Master coordina agregación |
| Ver estado del cluster | ✅ Sí | Master tiene visión global |

### 3.3 Dockerfile del Slave

El Slave se construye en **multi-stage** para optimizar tamaño:

```dockerfile
# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Backend Dependencies
FROM python:3.11-slim AS backend-builder
WORKDIR /app
RUN python -m venv /opt/venv
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Final Runtime Image
FROM python:3.11-slim
RUN apt-get install -y nginx supervisor curl openssl
COPY --from=frontend-builder /app/frontend/dist /var/www/html
COPY --from=backend-builder /opt/venv /opt/venv
COPY backend/ ./backend/
EXPOSE 443 8000
```

---

## 4. Comunicación entre Nodos

### 4.1 Protocolos de Comunicación

```
┌─────────────────────────────────────────────────────────────────┐
│               PROTOCOLOS DE COMUNICACIÓN                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐         HTTP/REST          ┌─────────┐            │
│  │ Cliente │ ─────────────────────────► │  Slave  │            │
│  └─────────┘                            └─────────┘            │
│                                              │                  │
│                                              │ gRPC             │
│                                              ▼                  │
│                                         ┌─────────┐            │
│                                         │ Master  │            │
│                                         └─────────┘            │
│                                              │                  │
│                               ┌──────────────┼──────────────┐  │
│                               │              │              │  │
│                               ▼              ▼              ▼  │
│                          ┌─────────┐   ┌─────────┐   ┌─────────┐
│                          │ Slave 1 │◄─►│ Slave 2 │◄─►│ Slave N │
│                          └─────────┘   └─────────┘   └─────────┘
│                               │              │              │  │
│                               └──────────────┴──────────────┘  │
│                                     Gossip Protocol            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Resumen:
• Cliente → Slave: HTTP/REST (puerto 8000 o 443)
• Slave → Master: gRPC (puerto 50051)
• Slave ↔ Slave: Gossip Protocol (UDP)
```

### 4.2 Flujo de una Búsqueda Distribuida

```
┌──────┐    ┌────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐
│Client│    │  LB    │    │ Slave-A │    │  Master  │    │Slaves   │
└──┬───┘    └───┬────┘    └────┬────┘    └────┬─────┘    └────┬────┘
   │            │              │              │               │
   │  search    │              │              │               │
   │ ──────────►│              │              │               │
   │            │   forward    │              │               │
   │            │ ────────────►│              │               │
   │            │              │              │               │
   │            │              │  get_nodes   │               │
   │            │              │ ────────────►│               │
   │            │              │              │               │
   │            │              │  node_list   │               │
   │            │              │ ◄────────────│               │
   │            │              │              │               │
   │            │              │         parallel_search      │
   │            │              │ ─────────────────────────────►
   │            │              │              │               │
   │            │              │         partial_results      │
   │            │              │ ◄─────────────────────────────
   │            │              │              │               │
   │            │   aggregate  │              │               │
   │            │   & rank     │              │               │
   │            │              │              │               │
   │            │   results    │              │               │
   │            │ ◄────────────│              │               │
   │  results   │              │              │               │
   │ ◄──────────│              │              │               │
   │            │              │              │               │
```

### 4.3 Flujo de Subida de Documento

```
┌──────┐    ┌────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐
│Client│    │  LB    │    │ Slave-A │    │  Master  │    │Slave-B  │
└──┬───┘    └───┬────┘    └────┬────┘    └────┬─────┘    └────┬────┘
   │            │              │              │               │
   │  upload    │              │              │               │
   │ ──────────►│              │              │               │
   │            │   forward    │              │               │
   │            │ ────────────►│              │               │
   │            │              │              │               │
   │            │              │  vectorize   │               │
   │            │              │  document    │               │
   │            │              │              │               │
   │            │              │  assign_node │               │
   │            │              │ ────────────►│               │
   │            │              │              │               │
   │            │              │  target:     │               │
   │            │              │  Slave-B     │               │
   │            │              │ ◄────────────│               │
   │            │              │              │               │
   │            │              │       store_document         │
   │            │              │ ─────────────────────────────►
   │            │              │              │               │
   │            │              │          ack                 │
   │            │              │ ◄─────────────────────────────
   │            │              │              │               │
   │            │   success    │              │               │
   │            │ ◄────────────│              │               │
   │  success   │              │              │               │
   │ ◄──────────│              │              │               │
```

---

## 5. Diseño AP (Available & Partition-tolerant)

### 5.1 Arquitectura que Tolera Particiones

DistriSearch implementa el modelo **AP** del teorema CAP:

```
┌─────────────────────────────────────────────────────────────────┐
│            ESCENARIO: PARTICIÓN DE RED                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│     Partición A                    │      Partición B           │
│                                    │                            │
│  ┌──────────┐   ┌──────────┐      │   ┌──────────┐             │
│  │  Master  │   │ Slave-1  │      │   │ Slave-2  │             │
│  │          │◄─►│          │      │   │          │             │
│  └──────────┘   └──────────┘      │   └──────────┘             │
│                                    │        │                   │
│  ✅ Búsquedas coordinadas         │   ✅ Búsquedas locales     │
│  ✅ Nuevas escrituras              │   ✅ Autenticación         │
│  ✅ Estado completo                │   ⚠️ Sin escrituras       │
│                                    │   ⚠️ Datos parciales      │
│                                    │                            │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Componentes por Tipo de Consistencia

| Componente | Tipo | Consistencia | Motivo |
|------------|------|--------------|--------|
| **SQLite (Raft)** | Usuarios, nodos | Fuerte (Raft) | Autenticación requiere consistencia |
| **MongoDB** | Documentos | Local por nodo | Cada slave es autónomo |
| **Redis** | Caché | Local | No requiere consistencia |
| **UserDocumentRegistry** | Mapeo user→docs | Eventual (Gossip) | Tolera inconsistencias temporales |

### 5.3 Configuración de Replicación

Del archivo `backend/app/config.py`:

```python
# Replicación
replication_factor: int = 2        # Número de copias por documento
min_replicas_for_write: int = 1    # Mínimo para confirmar escritura

# Heartbeat (detección de fallos)
heartbeat_interval: int = 5        # Segundos entre heartbeats
heartbeat_timeout: int = 15        # Timeout para marcar nodo como fallido
max_heartbeat_failures: int = 3    # Fallos antes de declarar nodo muerto
```

---

## 6. Resumen: Master vs Slave

| Aspecto | Master | Slave |
|---------|--------|-------|
| **Cantidad** | 1-2 (activo + standby) | N (escalable) |
| **Función principal** | Coordinar | Almacenar y servir |
| **Datos** | Metadatos del cluster | Documentos reales |
| **Estado durante partición** | Degrada el cluster | Opera autónomamente |
| **Puerto API** | 8001 | 8000 |
| **Puerto gRPC** | 50051 | 50051 |
| **Almacenamiento** | SQLite (Raft) | MongoDB + Redis + SQLite |

---

## Referencias del Código

```python
# Modelo de Nodo (shared/models/node.py)
class NodeRole(str, Enum):
    MASTER = "master"
    SLAVE = "slave"

class NodeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAINING = "draining"    # Siendo removido
    FAILED = "failed"
    STARTING = "starting"
    SYNCING = "syncing"      # Sincronizando después de recuperación
```

```python
# Configuración de nodo (backend/app/config.py)
node_id: str = Field(default="node-1", alias="NODE_ID")
node_role: str = Field(default="slave", alias="NODE_ROLE")
master_host: str = Field(default="master", alias="MASTER_HOST")
master_port: int = Field(default=8001, alias="MASTER_PORT")
```

---

> **Siguiente**: [02_Componentes_Principales.md](02_Componentes_Principales.md) para detalles de cada componente técnico.