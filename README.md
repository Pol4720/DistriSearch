<p align="center">
  <img src="DistriSearch/assets/logo.png" alt="DistriSearch Logo" width="200"/>
</p>

# 🔍 DistriSearch - Sistema de Búsqueda Distribuida Master-Slave

Sistema de búsqueda distribuida de archivos con arquitectura **Master-Slave dinámico**, localización semántica, replicación por afinidad y tolerancia a fallos.

![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![MongoDB](https://img.shields.io/badge/mongodb-6.0-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

---

## 📑 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Tolerancia a Fallos](#-tolerancia-a-fallos)
- [Coordinación Distribuida](#-coordinación-distribuida)
- [Sistema de Nombres](#-sistema-de-nombres)
- [Replicación y Consistencia](#-replicación-y-consistencia)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [API Endpoints](#-api-endpoints)
- [Testing](#-testing)
- [Documentación](#-documentación)

---

## ✨ Características Principales

### 🎯 Funcionalidades Core

| Característica | Descripción | Estado |
|----------------|-------------|--------|
| **Búsqueda Semántica** | Embeddings con sentence-transformers (384 dims) | ✅ Completo |
| **Arquitectura Master-Slave** | Líder dinámico con elección Bully | ✅ Completo |
| **Localización Semántica** | Índice vectorial distribuido por afinidad | ✅ Completo |
| **Replicación Dinámica** | Factor configurable con afinidad semántica | ✅ Completo |
| **Tolerancia a Fallos** | Heartbeat UDP + elección automática | ✅ Completo |
| **Naming Jerárquico** | Rutas estilo Unix con aliases | ✅ Completo |
| **Descubrimiento Automático** | Multicast UDP para detección de nodos | ✅ Completo |
| **Consistencia Eventual** | Replicación asíncrona coordinada | ✅ Completo |

---

## 🏗️ Arquitectura del Sistema

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Streamlit)                      │
│  • Interfaz de usuario                                      │
│  • Búsqueda interactiva                                     │
│  • Gestión de nodos                                         │
│  • Visualización de cluster                                 │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────────────────────────┐
│                    BACKEND (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ API Layer (routes/)                                   │  │
│  │  • /search    - Búsqueda semántica                   │  │
│  │  • /register  - Gestión de nodos y archivos          │  │
│  │  • /download  - Descarga de archivos                 │  │
│  │  • /cluster   - Estado del cluster                   │  │
│  │  • /naming    - Sistema de nombres jerárquico        │  │
│  │  • /health    - Health checks                        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Services Layer (services/)                            │  │
│  │  • DynamicReplicationService                         │  │
│  │  • NodeService                                       │  │
│  │  • ClusterInitializer                                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    CLUSTER MODULE                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • HeartbeatService   - Monitoreo UDP (puerto 5000)  │  │
│  │  • BullyElection      - Elección líder (puerto 5001) │  │
│  │  • MulticastDiscovery - Descubrimiento automático    │  │
│  │  • HierarchicalNaming - Sistema de nombres           │  │
│  │  • IPCache            - Cache LRU de nodos           │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    MASTER MODULE                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • EmbeddingService        - Generación embeddings   │  │
│  │  • LocationIndex           - Índice vectorial        │  │
│  │  • QueryRouter             - Enrutamiento consultas  │  │
│  │  • ReplicationCoordinator  - Coordinador réplicas    │  │
│  │  • LoadBalancer            - Balanceo de carga       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    CORE MODULE                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • models.py  - Modelos unificados (Enums, Pydantic) │  │
│  │  • config.py  - Configuración centralizada           │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    MONGODB                                   │
│  Collections: files, nodes, file_contents, replications     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura del Proyecto

```
DistriSearch/
├── core/                    # Módulo central
│   ├── __init__.py
│   ├── models.py           # Modelos unificados (Enums, Dataclasses, Pydantic)
│   └── config.py           # Configuración centralizada
│
├── cluster/                 # Módulo de cluster (comunicación entre nodos)
│   ├── __init__.py
│   ├── heartbeat.py        # Servicio de heartbeat UDP
│   ├── election.py         # Algoritmo Bully para elección de líder
│   ├── discovery.py        # Descubrimiento multicast UDP
│   └── naming/             # Sistema de nombres
│       ├── hierarchical.py # Namespace jerárquico
│       └── ip_cache.py     # Cache LRU de IPs
│
├── master/                  # Módulo Master (localización semántica)
│   ├── __init__.py
│   ├── embedding_service.py    # Generación de embeddings
│   ├── location_index.py       # Índice vectorial distribuido
│   ├── query_router.py         # Enrutamiento de consultas
│   ├── replication_coordinator.py  # Coordinador de réplicas
│   └── load_balancer.py        # Balanceo de carga
│
├── backend/                 # API REST (FastAPI)
│   ├── main.py             # Punto de entrada
│   ├── database.py         # Conexión MongoDB
│   ├── models.py           # Re-exports de core/models.py
│   ├── routes/             # Endpoints REST
│   │   ├── search.py
│   │   ├── register.py
│   │   ├── download.py
│   │   ├── cluster.py
│   │   └── naming.py
│   └── services/           # Servicios de negocio
│       ├── node_service.py
│       ├── replication_service.py
│       └── dynamic_replication.py
│
├── frontend/                # UI (Streamlit)
│   ├── app.py
│   ├── pages/
│   └── components/
│
├── deploy/                  # Configuración Docker
│   ├── docker-compose.yml          # Desarrollo local
│   └── docker-compose.cluster.yml  # Cluster multi-nodo
│
├── tests/                   # Tests
│   ├── unit/
│   └── integration/
│
└── docs/                    # Documentación MkDocs
```

---

┌─────────────────────────────────────────────────────────────┐
│                    AGENTES (Nodos P2P)                       │
│  • Registro automático                                      │
│  • Escaneo de archivos local                                │
│  • Servidor de archivos HTTP                                │
│  • Heartbeat periódico                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Tolerancia a Fallos

### Arquitectura de Alta Disponibilidad

DistriSearch implementa un sistema **Master-Slave dinámico** donde cualquier nodo puede convertirse en Master mediante el algoritmo de elección Bully.

### 🔄 Mecanismos de Tolerancia

| Mecanismo | Implementación | Módulo |
|-----------|----------------|--------|
| **Heartbeat UDP** | PING/PONG cada 5s, timeout 15s | `cluster/heartbeat.py` |
| **Elección Bully** | Nodo con mayor ID gana | `cluster/election.py` |
| **Replicación** | Factor k=3 por defecto | `backend/services/dynamic_replication.py` |
| **Descubrimiento** | Multicast UDP 239.255.0.1:5353 | `cluster/discovery.py` |

### 📡 Protocolo de Heartbeat

```
   Slave A                     Slave B                     Master
      │                          │                           │
      │◄────────── PING ─────────│                           │
      │─────────── PONG ─────────►                           │
      │                          │◄──────── PING ────────────│
      │                          │───────── PONG ────────────►
      │                          │                           │
      │    [Master timeout - 15s sin respuesta]              │
      │                          │                           X
      │◄─────── ELECTION ────────│                           
      │──────── ELECTION_OK ─────►                           
      │                          │─── (Mayor ID, se proclama)
      │◄────── COORDINATOR ──────│                           
      │                          │ [Nuevo Master]            
```

### 🎯 Proceso de Elección (Algoritmo Bully)

1. **Detección**: Heartbeat timeout detecta Master caído
2. **Inicio**: Nodo envía ELECTION a todos con ID mayor
3. **Respuesta**: Nodos con ID mayor responden ELECTION_OK
4. **Proclamación**: Si no hay respuesta, se proclama COORDINATOR
5. **Notificación**: Nuevo Master envía COORDINATOR a todos

---

## 🎛️ Coordinación Distribuida

### Elección de Líder (Algoritmo Bully)

**Algoritmo:** Bully Election - El nodo con mayor ID siempre gana

**Tipos de Mensajes:**

| Mensaje | Descripción |
|---------|-------------|
| `ELECTION` | Solicitud de elección enviada a nodos con ID mayor |
| `ELECTION_OK` | Respuesta indicando que el nodo participará |
| `COORDINATOR` | Anuncio del nuevo líder a todos los nodos |

**Código de ejemplo:**

```python
from cluster import BullyElection, HeartbeatService

# Crear servicios
heartbeat = HeartbeatService(
    node_id="node_1",
    port=5000,
    on_master_down=lambda: election.start_election()
)

election = BullyElection(
    node_id="node_1", 
    port=5001,
    on_become_master=lambda: print("¡Soy el nuevo Master!"),
    on_new_master=lambda master_id: print(f"Nuevo master: {master_id}")
)

# Añadir peers
election.add_peer("node_2", "192.168.1.2", 5001, can_be_master=True)
election.add_peer("node_3", "192.168.1.3", 5001, can_be_master=True)

# Iniciar
await heartbeat.start()
await election.start()
```

### 🔄 Configuración de Cluster

Variables de entorno:

```bash
# Identificación
NODE_ID=node_1
NODE_ROLE=slave          # slave | master (inicial)
MASTER_CANDIDATE=true    # Puede ser elegido Master

# Comunicación
HEARTBEAT_PORT=5000      # Puerto UDP para heartbeats
ELECTION_PORT=5001       # Puerto UDP para elección
HEARTBEAT_INTERVAL=5     # Segundos entre PINGs
HEARTBEAT_TIMEOUT=15     # Segundos para detectar falla

# Peers
CLUSTER_PEERS=node_2:192.168.1.2:8000:5000:5001,node_3:192.168.1.3:8000:5000:5001

# Endpoints
POST /coordination/election/start  # Iniciar elección
GET /coordination/status           # Estado actual
```

**Ventajas:**
- ✅ Sin punto central de falla
- ✅ Resistente a ataques Sybil
- ✅ Elección justa basada en capacidad computacional

### Exclusión Mutua Distribuida

**Algoritmo:** Ricart-Agrawala modificado

**Características:**
- Relojes lógicos de Lamport para ordenamiento
- Confirmación de todos los nodos antes de acceso
- Diferimiento de replies para evitar deadlock

```python
# Adquirir bloqueo
POST /coordination/lock/acquire
{
  "resource_id": "file_123"
}

# Liberar bloqueo
POST /coordination/lock/release
{
  "resource_id": "file_123"
}
```

**Casos de uso:**
- Escrituras concurrentes en el mismo archivo
- Actualización de metadata compartida
- Operaciones de checkpoint coordinado

### Sincronización con Relojes de Lamport

```python
class LamportClock:
    def increment(self) -> int:
        """Incrementar en evento local"""
        self.counter += 1
        return self.counter
    
    def update(self, received_time: int) -> int:
        """Actualizar al recibir mensaje"""
        self.counter = max(self.counter, received_time) + 1
        return self.counter
```

**Propiedades garantizadas:**
- Si evento `a` ocurre antes que `b`, entonces `L(a) < L(b)`
- Orden total de eventos en el sistema
- Resolución de conflictos determinista

---

## 📛 Sistema de Nombres

### Naming Jerárquico

**Inspiración:** Unix Filesystem + DNS

**Estructura:**

```
/                               # Raíz
├── proyectos/                  # Directorio
│   ├── distrisearch/          
│   │   ├── docs/
│   │   │   └── readme.md      # Archivo
│   │   └── src/
│   │       └── main.py
│   └── otro_proyecto/
└── compartido/
    └── datos.csv
```

**Operaciones:**

```python
# Registrar archivo en path
POST /naming/register_path
{
  "path": "/proyectos/distrisearch/docs/readme.md",
  "file_id": "abc123",
  "metadata": {"size": 1024, "type": "document"}
}

# Resolver path
GET /naming/resolve?path=/proyectos/distrisearch/docs/readme.md

# Listar directorio
GET /naming/list?path=/proyectos/distrisearch

# Crear alias (symbolic link)
POST /naming/alias
{
  "alias_path": "/docs/manual.pdf",
  "real_path": "/proyectos/distrisearch/docs/manual.pdf"
}

# Búsqueda con wildcards
GET /naming/search?pattern=/proyectos/**/readme.md
```

**Características:**
- ✅ Navegación estilo Unix
- ✅ Aliases (symbolic links)
- ✅ Búsqueda por patrón (wildcards)
- ✅ Persistencia en MongoDB
- ✅ Cache en memoria para performance

### Descubrimiento de Nodos (Multicast)

**Protocolo:** UDP Multicast (similar a mDNS)

**Configuración:**

```bash
MULTICAST_GROUP=239.255.0.1
MULTICAST_PORT=5353
DISCOVERY_INTERVAL=30  # segundos
```

**Mensajes:**

```json
// Anuncio de nodo
{
  "type": "node_announce",
  "node_id": "agent_01",
  "ip_address": "192.168.1.100",
  "port": 8080,
  "timestamp": "2024-01-15T10:00:00Z"
}

// Query de nodos
{
  "type": "node_query",
  "requesting_node": "central"
}

// Respuesta
{
  "type": "node_response",
  "node_id": "agent_02",
  "ip_address": "192.168.1.101",
  "port": 8081
}
```

**Ventajas:**
- ✅ Zero-configuration networking
- ✅ Descubrimiento automático en LAN
- ✅ Detección de nodos caídos (timeout 3x interval)
- ✅ Bajo overhead de red

### IP Cache

**Propósito:** Reducir latencia de consultas a MongoDB

```python
class IPCache:
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.ttl = 300  # 5 minutos
    
    def get(self, node_id: str) -> Optional[Dict]:
        """Obtener con validación de TTL"""
        if node_id in self.cache:
            cached = self.cache[node_id]
            if (datetime.now() - cached['cached_at']).seconds < self.ttl:
                return cached['data']
        return None
```

**Estrategia:**
- Cache miss → Query a MongoDB → Cache en memoria
- Invalidación en actualización de nodo
- TTL de 5 minutos para evitar datos obsoletos

---

## 🔄 Replicación y Consistencia

### Modelo de Consistencia

**Teorema CAP:** DistriSearch elige **CP** (Consistencia + Tolerancia a Particiones)

| Propiedad | Elección | Justificación |
|-----------|----------|---------------|
| **C**onsistencia | ✅ **Eventual** | Sincronización cada 60s |
| **A**vailability | ⚠️ Parcial | Requiere mayoría online |
| **P**artition Tolerance | ✅ Completo | Sigue operando con particiones |

### Protocolo de Replicación

**Estrategia:** Escritura Local + Propagación Asíncrona

**Pasos:**

1. **Escritura local**: Usuario sube archivo al nodo más cercano
2. **Registro en DB**: MongoDB registra metadata
3. **Selección de réplicas**: Hash consistente selecciona k=3 nodos
4. **Replicación paralela**: Transferencia HTTP a nodos destino
5. **Confirmación**: Actualización de estado en MongoDB

**Código:**

```python
async def replicate_file(self, file_meta: Dict, source_node_id: str) -> Dict:
    """Replica archivo a k nodos"""
    file_id = file_meta['file_id']
    
    # Seleccionar nodos con hash consistente
    target_nodes = self.get_replication_nodes(file_id, exclude_nodes={source_node_id})
    
    # Replicar en paralelo
    tasks = [
        self._replicate_to_node(file_meta, source_node_id, node)
        for node in target_nodes
    ]
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        "file_id": file_id,
        "replicated_to": [r['node_id'] for r in responses if r['status'] == 'success'],
        "failed": [r['node_id'] for r in responses if r['status'] == 'failed']
    }
```

### Sincronización de Consistencia Eventual

**Loop de sincronización:**

```python
async def synchronize_eventual_consistency(self):
    """Ejecutado cada 60 segundos"""
    # 1. Detectar archivos con múltiples versiones
    pipeline = [
        {"$group": {
            "_id": "$file_id",
            "versions": {"$push": {
                "node_id": "$node_id",
                "last_updated": "$last_updated",
                "content_hash": "$content_hash"
            }}
        }}
    ]
    
    files_versions = list(self.db.files.aggregate(pipeline))
    
    # 2. Resolver conflictos (last-write-wins)
    for file_group in files_versions:
        versions = file_group['versions']
        
        if len(versions) > 1:
            canonical = max(versions, key=lambda v: v['last_updated'])
            
            # 3. Propagar versión canónica
            await self._propagate_canonical_version(
                file_group['_id'],
                canonical,
                versions
            )
```

### Resolución de Conflictos

**Estrategias soportadas:**

| Estrategia | Descripción | Configuración |
|------------|-------------|---------------|
| **last-write-wins** | Última escritura prevalece | `CONFLICT_RESOLUTION=last_write_wins` |
| **first-write-wins** | Primera escritura prevalece | `CONFLICT_RESOLUTION=first_write_wins` |
| **manual** | Requiere intervención humana | `CONFLICT_RESOLUTION=manual` |

**Detección de conflictos:**

```python
# Archivo con mismo file_id pero diferente content_hash
conflict = self.db.files.aggregate([
    {"$group": {
        "_id": "$file_id",
        "hashes": {"$addToSet": "$content_hash"},
        "count": {"$sum": 1}
    }},
    {"$match": {"count": {"$gt": 1}}}
])
```

---

## 📋 Requisitos

### Software

| Componente | Versión Mínima | Recomendada |
|------------|----------------|-------------|
| **Python** | 3.10 | 3.12 |
| **MongoDB** | 5.0 | 6.0 |
| **Docker** | 20.10 | 24.0 |
| **Docker Compose** | 2.0 | 2.24 |

### Hardware

**Backend:**
- CPU: 2 cores
- RAM: 2 GB
- Disco: 10 GB

**Agente:**
- CPU: 1 core
- RAM: 512 MB
- Disco: 5 GB

**Producción (recomendado):**
- CPU: 4 cores
- RAM: 8 GB
- Disco: 50 GB SSD

---

## 🚀 Instalación

### Opción 1: Docker Compose (Recomendado)

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/distrisearch.git
cd distrisearch/DistriSearch

# 2. Configurar variables de entorno
cp deploy/.env.example deploy/.env
nano deploy/.env  # Editar configuración

# 3. Iniciar sistema completo
cd deploy
docker-compose up -d

# 4. Verificar servicios
docker-compose ps
```

**Servicios levantados:**
- Backend: http://localhost:8000
- Frontend: http://localhost:8501
- MongoDB: localhost:27017
- Agente: http://localhost:8080

### Opción 2: Manual (Desarrollo)

```bash
# Backend
cd DistriSearch/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Frontend (otra terminal)
cd DistriSearch/frontend
pip install -r requirements.txt
streamlit run app.py

# Agente (otra terminal)
cd DistriSearch/agent
pip install -r requirements.txt
python agent_dynamic.py
```

---

## ⚙️ Configuración

### Variables de Entorno

#### Backend (`backend/.env`)

```bash
# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DBNAME=distrisearch
GRIDFS_THRESHOLD_BYTES=200000  # 200 KB

# Servidor
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
NODE_ID=central
EXTERNAL_IP=192.168.1.100  # Tu IP en LAN

# Seguridad
ADMIN_API_KEY=tu_api_key_secreta_aqui
SECRET_KEY=tu_secret_key_jwt_aqui

# SSL (opcional)
ENABLE_SSL=false
SSL_CERT_FILE=../certs/distrisearch.crt
SSL_KEY_FILE=../certs/distrisearch.key

# Replicación
REPLICATION_ENABLED=true
REPLICATION_FACTOR=3
CONSISTENCY_MODEL=eventual
CONFLICT_RESOLUTION=last_write_wins
SYNC_INTERVAL_SECONDS=60

# Mantenimiento
MAINTENANCE_INTERVAL_SECONDS=300  # 5 min
NODE_DISCOVERY_INTERVAL=30

# Checkpoints
CHECKPOINT_INTERVAL_SECONDS=300  # 5 min

# Coordinación
POW_DIFFICULTY=4  # Dificultad PoW

# Multicast
MULTICAST_GROUP=239.255.0.1
MULTICAST_PORT=5353
DISCOVERY_INTERVAL=30

# Timeouts
NODE_TIMEOUT_MINUTES=5
```

#### Frontend (`frontend/.env`)

```bash
DISTRISEARCH_BACKEND_URL=http://localhost:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=http://192.168.1.100:8000
DISTRISEARCH_ADMIN_API_KEY=tu_api_key_secreta_aqui
```

#### Agente (`agent/.env`)

```bash
NODE_ID=agent_01
BACKEND_URL=http://localhost:8000
ADMIN_API_KEY=tu_api_key_secreta_aqui

FILE_SERVER_PORT=8080
SHARED_FOLDER=./shared
SCAN_INTERVAL=300  # 5 min
```

### Configuración de Replicación

**Escenarios:**

```bash
# Alta disponibilidad (recomendado)
REPLICATION_FACTOR=3
SYNC_INTERVAL_SECONDS=60
CHECKPOINT_INTERVAL_SECONDS=300

# Ahorro de espacio
REPLICATION_FACTOR=2
SYNC_INTERVAL_SECONDS=120

# Máxima redundancia
REPLICATION_FACTOR=5
SYNC_INTERVAL_SECONDS=30
CHECKPOINT_INTERVAL_SECONDS=180
```

---

## 📖 Uso

### 1. Subir Archivos

**Desde Frontend:**

1. Acceder a http://localhost:8501
2. Iniciar sesión (o registrarse)
3. Ir a **"📤 Subir Archivos"**
4. Seleccionar archivos
5. Elegir nodo destino
6. Hacer clic en **"Subir"**

**Desde API:**

```bash
curl -X POST http://localhost:8000/register/upload \
  -H "X-API-KEY: tu_api_key" \
  -F "file=@documento.pdf" \
  -F "node_id=central"
```

### 2. Buscar Archivos

**Desde Frontend:**

1. Ir a **"🔍 Buscar"**
2. Ingresar términos de búsqueda
3. Filtrar por tipo (opcional)
4. Hacer clic en **"Buscar"**

**Desde API:**

```bash
curl "http://localhost:8000/search/?q=documento&file_type=document&max_results=50" \
  -H "Authorization: Bearer tu_token_jwt"
```

**Con BM25 score:**

```bash
curl "http://localhost:8000/search/?q=importante&include_score=true"
```

### 3. Descargar Archivos

**Desde Frontend:**

- Hacer clic en **"📥 Descargar"** en resultados de búsqueda

**Desde API:**

```bash
# Obtener URL de descarga
curl -X POST http://localhost:8000/download/ \
  -H "Authorization: Bearer tu_token" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123"}'

# Descarga directa
curl http://localhost:8000/download/file/abc123 -o archivo.pdf
```

### 4. Gestionar Nodos

**Registrar nodo manualmente:**

```bash
curl -X POST http://localhost:8000/register/node \
  -H "X-API-KEY: tu_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "agent_02",
    "name": "Agente 02",
    "ip_address": "192.168.1.101",
    "port": 8080,
    "status": "online"
  }'
```

**Verificar nodos online:**

```bash
curl http://localhost:8000/search/nodes
```

**Eliminar nodo:**

```bash
curl -X DELETE "http://localhost:8000/register/node/agent_02?delete_files=true" \
  -H "X-API-KEY: tu_api_key"
```

### 5. Iniciar Elección de Líder

```bash
curl -X POST http://localhost:8000/coordination/election/start \
  -H "X-API-KEY: tu_api_key" \
  -d '{"reason": "manual"}'
```

### 6. Crear Checkpoint

```bash
curl -X POST http://localhost:8000/fault_tolerance/checkpoint/create \
  -H "X-API-KEY: tu_api_key"
```

### 7. Ver Métricas de Confiabilidad

```bash
# Métricas de un nodo
curl http://localhost:8000/fault_tolerance/metrics/node/agent_01

# Métricas del sistema
curl http://localhost:8000/fault_tolerance/metrics/system
```

---

## 🔌 API Endpoints

### Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/register` | Registrar usuario |
| POST | `/auth/token` | Obtener token JWT |
| GET | `/auth/me` | Obtener usuario actual |

### Búsqueda

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/search/` | Buscar archivos |
| GET | `/search/stats` | Estadísticas del sistema |
| GET | `/search/nodes` | Listar nodos |

### Registro

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/register/node` | Registrar nodo |
| POST | `/register/files` | Registrar archivos |
| POST | `/register/heartbeat/{node_id}` | Heartbeat |
| DELETE | `/register/node/{node_id}` | Eliminar nodo |
| POST | `/register/upload` | Subir archivo |
| POST | `/register/upload/bulk` | Subir múltiples archivos |

### Descarga

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/download/` | Obtener URL de descarga |
| GET | `/download/file/{file_id}` | Descargar archivo |
| GET | `/download/direct/{file_id}` | Redirección directa |

### Coordinación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/coordination/election/start` | Iniciar elección |
| POST | `/coordination/election` | Recibir notificación de elección |
| POST | `/coordination/leader` | Recibir anuncio de líder |
| GET | `/coordination/status` | Estado de coordinación |
| POST | `/coordination/lock/acquire` | Adquirir mutex |
| POST | `/coordination/lock/release` | Liberar mutex |

### Naming

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/naming/register_path` | Registrar path jerárquico |
| GET | `/naming/resolve` | Resolver path a archivo |
| GET | `/naming/list` | Listar directorio |
| POST | `/naming/alias` | Crear alias |
| GET | `/naming/search` | Buscar por patrón |
| GET | `/naming/tree` | Obtener estructura de árbol |

### Tolerancia a Fallos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/fault_tolerance/checkpoint/create` | Crear checkpoint |
| POST | `/fault_tolerance/checkpoint/restore/{id}` | Restaurar checkpoint |
| GET | `/fault_tolerance/metrics/node/{id}` | Métricas de nodo |
| GET | `/fault_tolerance/metrics/system` | Métricas del sistema |
| GET | `/fault_tolerance/replication/status` | Estado de replicación |

---

## 📊 Métricas y Monitoreo

### Dashboard de Estadísticas

**Frontend → Pestaña "📊 Estadísticas"**

Muestra:
- Total de archivos
- Nodos online/offline
- Distribución por tipo de archivo
- Indicador de salud del sistema (gauge)
- Gráficos interactivos con Plotly

### Métricas de Confiabilidad

**Endpoint:** `GET /fault_tolerance/metrics/node/{node_id}`

**Respuesta:**

```json
{
  "node_id": "agent_01",
  "mttf": 86400.0,
  "mttr": 120.0,
  "mtbf": 86520.0,
  "availability": 0.9986,
  "failures_count": 3,
  "window_days": 30,
  "calculated_at": "2024-01-15T10:00:00Z"
}
```

**Interpretación:**

- **MTTF = 86400s (24h)**: El nodo funciona 24h en promedio antes de fallar
- **MTTR = 120s (2 min)**: La recuperación toma 2 minutos
- **Disponibilidad = 99.86%**: El nodo está online el 99.86% del tiempo

### Logs Estructurados

**Configuración de logging:**

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('distrisearch.log'),
        logging.StreamHandler()
    ]
)
```

**Eventos importantes:**

```
✅ Nodo registrado: agent_01 (192.168.1.100:8080)
🔄 Iniciando replicación de archivo abc123 a 3 nodos
✅ Archivo abc123 replicado a agent_01
⚠️ Detectados 1 nodos caídos - Iniciando recuperación
📊 Recuperación de agent_02: recovered=15, failed=0
👑 Nuevo líder elegido: agent_01 (Término: 5)
✅ Checkpoint coordinado creado: checkpoint_xyz
```

---

## 🧪 Testing

### Tests Unitarios

```bash
cd DistriSearch/backend

# Ejecutar todos los tests
pytest

# Tests específicos
pytest tests/test_search.py
pytest tests/test_register.py
pytest tests/test_download.py
```

### Tests de Integración

```bash
# Test end-to-end
pytest test/test_end_to_end.py -v

# Test de robustez (tolerancia a fallos)
pytest test/test_fault_tolerance.py -v

# Test de consistencia de replicación
pytest test/test_replication_consistency.py -v
```

### Escenarios de Prueba

#### 1. Tolerancia a Fallos

```bash
# Iniciar sistema con 3 nodos
docker-compose up -d

# Simular caída de nodo
docker-compose stop agent

# Verificar que el sistema sigue funcionando
curl http://localhost:8000/search/stats

# Esperar recuperación automática (5 min)
# Verificar que archivos se replicaron
curl http://localhost:8000/fault_tolerance/replication/status
```

#### 2. Replicación Dinámica

```bash
# Subir archivo
curl -X POST http://localhost:8000/register/upload \
  -H "X-API-KEY: test_key" \
  -F "file=@test.pdf"

# Verificar que se replicó a k=3 nodos
curl http://localhost:8000/search/?q=test.pdf | jq '.nodes_available | length'
# Debería devolver 3
```

#### 3. Elección de Líder

```bash
# Forzar nueva elección
curl -X POST http://localhost:8000/coordination/election/start \
  -H "X-API-KEY: test_key"

# Verificar líder elegido
curl http://localhost:8000/coordination/status | jq '.current_leader'
```

---

## 🔧 Troubleshooting

### Problemas Comunes

#### 1. MongoDB Connection Error

**Síntoma:**

```
❌ Error conectando a MongoDB: ServerSelectionTimeoutError
```

**Solución:**

```bash
# Verificar que MongoDB está corriendo
docker ps | grep mongo

# Si no está, iniciarlo
docker-compose up -d mongo

# Verificar logs
docker-compose logs mongo
```

#### 2. Nodo no se auto-registra

**Síntoma:** Agente no aparece en lista de nodos

**Solución:**

```bash
# Verificar que el agente puede conectar al backend
docker-compose logs agent | grep "Registrado exitosamente"

# Verificar variables de entorno
docker-compose exec agent env | grep BACKEND_URL

# Registro manual
curl -X POST http://localhost:8000/register/node/dynamic \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "agent_01",
    "port": 8080,
    "auto_scan": true
  }'
```

#### 3. Replicación no funciona

**Síntoma:** Archivos no se replican a k nodos

**Diagnóstico:**

```bash
# Verificar configuración
curl http://localhost:8000/fault_tolerance/replication/status

# Verificar nodos online
curl http://localhost:8000/search/nodes | jq '.[] | select(.status=="online")'

# Ver logs de replicación
docker-compose logs backend | grep "Replicación"
```

**Solución:**

```bash
# Asegurar al menos k nodos online
docker-compose up -d --scale agent=3

# Forzar sincronización
curl -X POST http://localhost:8000/fault_tolerance/checkpoint/create
```

#### 4. Búsqueda no encuentra archivos

**Síntoma:** Query retorna 0 resultados

**Diagnóstico:**

```bash
# Verificar que archivos están indexados
mongo distrisearch --eval "db.files.countDocuments({})"

# Verificar índice full-text
mongo distrisearch --eval "db.file_contents.getIndexes()"
```

**Solución:**

```bash
# Re-indexar archivos
curl -X POST http://localhost:8000/register/node/{node_id}/sync \
  -H "X-API-KEY: test_key"
```

#### 5. Multicast discovery no funciona

**Síntoma:** Nodos no se descubren automáticamente

**Solución:**

```bash
# Verificar firewall permite UDP multicast
sudo ufw allow 5353/udp

# Windows: Permitir en firewall
netsh advfirewall firewall add rule name="DistriSearch Multicast" dir=in action=allow protocol=UDP localport=5353

# Verificar que red Docker permite multicast
docker network inspect distrisearch_network | jq '.[0].Options'
```

### Logs de Debugging

```bash
# Backend
docker-compose logs -f backend

# Agente
docker-compose logs -f agent

# MongoDB
docker-compose logs -f mongo

# Todos
docker-compose logs -f
```

---

## 🤝 Contribución

### Guía de Contribución

1. **Fork** el repositorio
2. **Crear** rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. **Commit** cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. **Push** a rama (`git push origin feature/nueva-funcionalidad`)
5. **Crear** Pull Request

### Estándares de Código

```bash
# Formatear código
black backend/ frontend/ agent/

# Linting
flake8 backend/ --max-line-length=120

# Type checking
mypy backend/
```

### Checklist de PR

- [ ] Tests pasan (`pytest`)
- [ ] Código formateado (`black`)
- [ ] Documentación actualizada
- [ ] Changelog actualizado
- [ ] Sin warnings de linting

---

## 📄 Licencia

MIT License - Ver [LICENSE](LICENSE) para más detalles

---

## 👥 Autores

- **Tu Nombre** - *Desarrollo Principal* - [GitHub](https://github.com/tu-usuario)

---

## 🙏 Agradecimientos

- **Andrew Tanenbaum** - "Distributed Systems: Principles and Paradigms" (teoría base)
- **MongoDB** - Base de datos NoSQL escalable
- **FastAPI** - Framework web moderno
- **Streamlit** - Framework de frontend rápido

---

## 📞 Soporte

- **Documentación completa**: [docs/index.md](docs/index.md)
- **Issues**: https://github.com/tu-usuario/distrisearch/issues
- **Email**: soporte@distrisearch.com

---

## 🗺️ Roadmap

### v2.1.0 (Q2 2024)

- [ ] Mejoras en el balanceo de carga del Master
- [ ] Algoritmo de consenso Raft como alternativa a Bully
- [ ] Replicación geográfica con awareness de latencia
- [ ] Compresión de archivos en tránsito
- [ ] Deduplicación a nivel de bloque

### v2.2.0 (Q3 2024)

- [ ] WebRTC para transferencias P2P directas
- [ ] Cifrado end-to-end opcional
- [ ] Cliente móvil (Android/iOS)
- [ ] Plugin para integraciones (Google Drive, Dropbox)
- [ ] Machine Learning para relevancia de búsqueda

### v3.0.0 (Q4 2024)

- [ ] Blockchain para audit trail inmutable
- [ ] IPFS integration
- [ ] GraphQL API
- [ ] Multi-tenancy
- [ ] Kubernetes Operator

---

## 📊 Estadísticas del Proyecto

```
Backend:
  - Lines of Code: ~5,000
  - Files: 25
  - Tests: 50+
  - Coverage: 85%

Frontend:
  - Components: 15
  - Pages: 4
  - UI Framework: Streamlit

Database:
  - Collections: 12
  - Indexes: 20+
  - Estimated Scale: 100K+ files
```

---

## 🎓 Referencias Académicas

1. Tanenbaum, A. S., & Van Steen, M. (2017). *Distributed systems: principles and paradigms*. Prentice-Hall.

2. Lamport, L. (1978). *Time, clocks, and the ordering of events in a distributed system*. Communications of the ACM, 21(7), 558-565.

3. Ricart, G., & Agrawala, A. K. (1981). *An optimal algorithm for mutual exclusion in computer networks*. Communications of the ACM, 24(1), 9-17.

4. Nakamoto, S. (2008). *Bitcoin: A peer-to-peer electronic cash system*.

5. Brewer, E. A. (2000). *Towards robust distributed systems*. PODC.

---

## 🏆 Features Destacadas

### ✨ Lo que hace único a DistriSearch:

1. **Verdadera Arquitectura P2P**: No hay servidor central, cualquier nodo puede ser líder
2. **Tolerancia a Fallos Certificada**: Basado en teoría académica probada
3. **Replicación Inteligente**: Hash consistente para distribución uniforme
4. **Consistencia Eventual**: Sincronización automática cada 60 segundos
5. **Zero-Configuration**: Nodos se autodescubren en LAN
6. **Métricas Académicas**: MTTF, MTTR, MTBF tracking real
7. **Checkpoints Coordinados**: Snapshots consistentes del sistema completo
8. **Naming Jerárquico**: Organización estilo Unix filesystem

---

**¿Listo para distribuir tu búsqueda? 🚀**

```bash
git clone https://github.com/tu-usuario/distrisearch.git
cd distrisearch/DistriSearch/deploy
docker-compose up -d
```

**¡Disfruta de DistriSearch!** 🔍✨