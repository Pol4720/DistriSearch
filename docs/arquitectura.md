# Arquitectura del Sistema - DistriSearch

Esta sección describe la arquitectura técnica de DistriSearch basada en el modelo **Master-Slave** con ubicación semántica de recursos.

---

## 🏗️ Arquitectura General: Master-Slave

DistriSearch utiliza una arquitectura **Master-Slave distribuida** donde:

- **Cualquier nodo puede ser Master** (elección dinámica mediante algoritmo Bully)
- **Todos los nodos son Slaves** por defecto
- **El Master coordina** búsquedas, replicación y ubicación de recursos
- **Los Slaves almacenan** documentos y responden queries

```
┌─────────────────────────────────────────────────────────────────┐
│                        DistriSearch Cluster                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌──────────────┐                                             │
│    │   CoreDNS    │  ← Resolución DNS con failover              │
│    │  (DNS Round  │                                             │
│    │   Robin)     │                                             │
│    └──────┬───────┘                                             │
│           │                                                      │
│    ┌──────┴────────────────────────────────────────┐            │
│    │                                                │            │
│    ▼                    ▼                    ▼      │            │
│ ┌──────────┐      ┌──────────┐      ┌──────────┐   │            │
│ │  Node 1  │      │  Node 2  │      │  Node 3  │   │            │
│ │ (MASTER) │◄────►│ (SLAVE)  │◄────►│ (SLAVE)  │   │            │
│ │          │      │          │      │          │   │            │
│ │ Backend  │      │ Backend  │      │ Backend  │   │            │
│ │ Frontend │      │ Frontend │      │ Frontend │   │            │
│ │ MongoDB  │      │ MongoDB  │      │ MongoDB  │   │            │
│ └──────────┘      └──────────┘      └──────────┘   │            │
│       │                │                │           │            │
│       └────────────────┼────────────────┘           │            │
│                        │                            │            │
│              Heartbeats UDP (puerto 5000)           │            │
│              Elección Bully (puerto 5001)           │            │
│                                                     │            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Componentes Principales

### 1. Core (Código Compartido)

Módulos compartidos entre Master y Slaves:

```
core/
├── __init__.py
├── config.py      # ClusterConfig - Configuración del cluster
└── models.py      # NodeInfo, ClusterMessage, SlaveProfile, etc.
```

**Configuración del Nodo** (`core/config.py`):

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `node_id` | string | ID único del nodo |
| `node_role` | enum | "master" o "slave" |
| `master_candidate` | bool | ¿Puede ser elegido Master? |
| `heartbeat_interval` | int | Segundos entre heartbeats |
| `heartbeat_timeout` | int | Timeout para considerar nodo caído |
| `replication_factor` | int | Número de réplicas (K) |
| `embedding_model` | string | Modelo para embeddings semánticos |

### 2. Master (Lógica de Coordinación)

El Master coordina el cluster:

```
master/
├── __init__.py
├── embedding_service.py       # Generación de embeddings semánticos
├── location_index.py          # Índice de ubicación de documentos
├── load_balancer.py           # Balanceo de carga entre Slaves
├── query_router.py            # Enrutamiento de búsquedas
└── replication_coordinator.py # Coordinación de replicación
```

**Funcionalidades del Master**:

| Componente | Responsabilidad |
|------------|-----------------|
| `EmbeddingService` | Genera vectores semánticos de documentos/queries usando `sentence-transformers` |
| `SemanticLocationIndex` | Índice de ubicación por similitud semántica |
| `LoadBalancer` | Distribuye carga según afinidad y estado (weighted, round-robin, least-connections) |
| `QueryRouter` | Enruta queries a Slaves relevantes |
| `ReplicationCoordinator` | Coordina réplicas por afinidad semántica |

### 3. Backend (API y Servicios)

Cada nodo ejecuta un backend FastAPI:

```
backend/
├── main.py                 # Punto de entrada
├── database.py             # Conexión MongoDB
├── models.py               # Modelos Pydantic
├── routes/
│   ├── auth.py            # Autenticación JWT
│   ├── search.py          # Búsqueda distribuida
│   ├── register.py        # Registro de nodos y archivos
│   ├── download.py        # Descarga de archivos
│   ├── cluster.py         # Operaciones de cluster
│   └── health.py          # Health checks
└── services/
    ├── heartbeat.py       # Sistema de heartbeats UDP
    ├── election.py        # Algoritmo Bully para elección
    ├── node_service.py    # Gestión de nodos
    ├── replication_service.py
    ├── dynamic_replication.py
    └── reliability_metrics.py  # MTTR/MTBF
```

### 4. Frontend (Streamlit)

Interfaz web por nodo:

```
frontend/
├── app.py                 # Home con autenticación
├── pages/
│   ├── 01_🔍_Buscar.py   # Búsqueda distribuida
│   ├── 02_🌐_Nodos.py    # Gestión de nodos
│   ├── 03_📊_Estadísticas.py
│   └── 04_📤_Subir_Archivos.py
└── utils/
    └── api_client.py      # Cliente HTTP
```

### 5. DNS (CoreDNS)

Resolución DNS con failover automático:

```
dns/
├── Corefile    # Configuración CoreDNS
└── hosts       # Hosts dinámicos (se actualizan automáticamente)
```

---

## 🔄 Flujos de Datos

### Flujo de Búsqueda Distribuida

1. Usuario ingresa query en Frontend
2. Frontend envía `POST /search` al Backend local
3. Backend (si es Master o conoce al Master):
   - Genera embedding de la query
   - Identifica Slaves con contenido similar (ubicación semántica)
   - Envía query en paralelo a Slaves relevantes
4. Slaves buscan en su MongoDB local
5. Master agrega y rankea resultados
6. Resultados se devuelven al Frontend

### Flujo de Elección de Líder (Bully Algorithm)

```
1. Node_1 detecta que Master no responde (3 heartbeats fallidos)

2. Node_1 inicia elección:
   Node_1 ────ELECTION────► Node_2 (ID mayor)
   Node_1 ────ELECTION────► Node_3 (ID mayor)

3. Nodos con ID mayor responden:
   Node_2 ────ELECTION_OK──► Node_1
   Node_3 ────ELECTION_OK──► Node_1

4. Node_1 espera... Node_3 (mayor ID) debe proclamarse

5. Node_3 gana y se proclama:
   Node_3 ────COORDINATOR──► Node_1
   Node_3 ────COORDINATOR──► Node_2

6. Todos reconocen a Node_3 como nuevo Master
```

### Flujo de Replicación por Afinidad Semántica

1. Usuario sube documento a Node_1
2. Node_1 notifica al Master
3. Master genera embedding del documento
4. Master selecciona Slaves con contenido semánticamente similar
5. Master coordina replicación a nodos seleccionados
6. Se mantiene factor de replicación K=2

---

## 🌐 Topología de Red

### Configuración Docker

```yaml
networks:
  distrisearch_cluster:
    subnet: 172.20.0.0/24

# IPs Fijas:
# DNS:     172.20.0.2
# Node_1:  172.20.0.11 (backend), 172.20.0.12 (frontend)
# Node_2:  172.20.0.21 (backend), 172.20.0.22 (frontend)
# Node_3:  172.20.0.31 (backend), 172.20.0.32 (frontend)
```

### Puertos

| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 8000 | HTTP | API Backend |
| 8443 | HTTPS | API Backend (SSL) |
| 8501 | HTTP | Frontend Streamlit |
| 5000 | UDP | Heartbeats |
| 5001 | UDP | Elección de líder |
| 27017 | TCP | MongoDB |
| 53 | UDP/TCP | DNS |

---

## 🛡️ Tolerancia a Fallos

### Sistema de Heartbeats

- **Protocolo**: UDP
- **Intervalo**: 5 segundos
- **Timeout**: 15 segundos (3 beats fallidos)
- **Acción**: Marcar nodo como `offline`, iniciar recuperación de réplicas

### Elección de Líder

- **Algoritmo**: Bully
- **Trigger**: Master no responde a 3 heartbeats consecutivos
- **Criterio**: Gana el nodo con mayor `node_id` (lexicográfico)
- **Tiempo de elección**: ~10-15 segundos

### Replicación

- **Factor por defecto**: K=2
- **Criterio de selección**: Afinidad semántica (nodos con contenido similar)
- **Modelo de consistencia**: Eventual (Last-Write-Wins)
- **Recuperación**: Automática ante fallo de Slave

---

## 📊 Métricas de Confiabilidad

El sistema registra automáticamente:

- **MTTR** (Mean Time To Recovery): Tiempo promedio de recuperación
- **MTBF** (Mean Time Between Failures): Tiempo entre fallos
- **Disponibilidad**: `MTBF / (MTBF + MTTR)`

Endpoint: `GET /health/cluster`

---

## 🔧 Configuración por Variables de Entorno

```bash
# Identificación
NODE_ID=node_1
NODE_ROLE=slave
MASTER_CANDIDATE=true

# Red
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
EXTERNAL_IP=172.20.0.11

# Cluster
CLUSTER_PEERS=node_2:172.20.0.21:8000:5000:5001,node_3:172.20.0.31:8000:5000:5001
HEARTBEAT_INTERVAL=5
HEARTBEAT_TIMEOUT=15

# Replicación
REPLICATION_FACTOR=2
CONSISTENCY_MODEL=eventual

# Base de datos
MONGO_URI=mongodb://localhost:27017
MONGO_DBNAME=distrisearch

# Embeddings (ubicación semántica)
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

---

## 🚀 Despliegue

### Docker Compose (Cluster de 3 nodos)

```bash
cd DistriSearch/deploy
docker-compose -f docker-compose.cluster.yml up -d
```

Esto levanta:
- 1 servidor DNS (CoreDNS)
- 3 nodos completos (backend + frontend + MongoDB cada uno)

### URLs de Acceso

| Componente | URL |
|------------|-----|
| Frontend Node 1 | http://localhost:8511 |
| Frontend Node 2 | http://localhost:8512 |
| Frontend Node 3 | http://localhost:8513 |
| API Node 1 | http://localhost:8001 |
| API Node 2 | http://localhost:8002 |
| API Node 3 | http://localhost:8003 |

---

## 🔌 API Endpoints Principales

### Health Checks

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Check básico |
| `GET /health/detailed` | Métricas del sistema |
| `GET /health/cluster` | Estado del cluster |
| `GET /health/ready` | Readiness probe |
| `GET /health/live` | Liveness probe |

### Búsqueda

| Endpoint | Descripción |
|----------|-------------|
| `GET /search/?q={query}` | Búsqueda distribuida |
| `GET /search/nodes` | Lista de nodos |

### Registro

| Endpoint | Descripción |
|----------|-------------|
| `POST /register/node` | Registrar nodo |
| `POST /register/files` | Registrar archivos |
| `POST /register/upload` | Subir archivo |

### Cluster

| Endpoint | Descripción |
|----------|-------------|
| `GET /cluster/status` | Estado del cluster |
| `POST /cluster/election` | Forzar elección |

---

[:octicons-arrow-left-24: Volver](index.md){ .md-button }
[:octicons-arrow-right-24: Características](caracteristicas.md){ .md-button .md-button--primary }
