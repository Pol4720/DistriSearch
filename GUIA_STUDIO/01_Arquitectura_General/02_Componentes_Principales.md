# Componentes Principales de DistriSearch

## Análisis Detallado de Cada Componente

---

## 1. Load Balancer (Nginx)

### 1.1 Propósito

El Load Balancer es el **punto de entrada** al sistema. Todas las peticiones de clientes pasan primero por él.

```
┌─────────────────────────────────────────────────────────────────┐
│                      LOAD BALANCER (NGINX)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ENTRADA                                                        │
│  ─────────────────────────────────────────────                 │
│  • Puerto 443 (HTTPS)                                          │
│  • Puerto 80 (HTTP → redirect a HTTPS)                         │
│                                                                 │
│  FUNCIONES                                                      │
│  ─────────────────────────────────────────────                 │
│  1. Terminación SSL/TLS                                        │
│  2. Distribución de tráfico (Round Robin / Least Connections)  │
│  3. Health Checks a backends                                   │
│  4. Rate Limiting (protección DDoS)                            │
│  5. Compresión Gzip                                            │
│  6. Caché de archivos estáticos                                │
│                                                                 │
│  SALIDA                                                         │
│  ─────────────────────────────────────────────                 │
│  • Backend API: proxy a slaves:8000                            │
│  • Frontend: archivos estáticos                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Configuración Principal

Del archivo `docker/load-balancer/nginx.conf`:

```nginx
# DNS interno de Docker para descubrimiento dinámico
resolver 127.0.0.11 valid=10s ipv6=off;
resolver_timeout 5s;

# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=10r/s;

# Upstream para el Master
upstream master_api {
    server master:8001 max_fails=3 fail_timeout=30s;
    keepalive 16;
}

# Compresión
gzip on;
gzip_comp_level 6;
gzip_types text/plain text/css application/json application/javascript;
```

### 1.3 Algoritmos de Balanceo

| Algoritmo | Descripción | Cuándo Usar |
|-----------|-------------|-------------|
| **Round Robin** | Rotación secuencial | Carga uniforme, nodos similares |
| **Least Connections** | Al nodo con menos conexiones activas | Requests de duración variable |
| **IP Hash** | Mismo cliente siempre al mismo nodo | Sesiones sticky |

```nginx
# Ejemplo: Least Connections
upstream backend_slaves {
    least_conn;
    server slave1:8000 weight=5;
    server slave2:8000 weight=5;
    server slave3:8000 weight=5;
}
```

### 1.4 Health Checks

```nginx
# Health check endpoint interno
server {
    listen 8080;
    server_name localhost;

    location /nginx_status {
        stub_status on;
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        deny all;
    }
}
```

---

## 2. Nodos Slave

### 2.1 Arquitectura Interna

Cada Slave combina **Frontend + Backend** en un solo contenedor:

```
┌─────────────────────────────────────────────────────────────────┐
│                         SLAVE NODE                              │
│                   (Contenedor Docker)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 SUPERVISOR (PID 1)                       │   │
│  │          Gestiona todos los procesos                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │              │              │                       │
│           ▼              ▼              ▼                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐   │
│  │   NGINX     │ │   UVICORN   │ │      SERVICIOS          │   │
│  │  (Frontend) │ │  (Backend)  │ │                         │   │
│  │             │ │             │ │  • MongoDB (opcional)   │   │
│  │  :443       │ │  :8000      │ │  • Redis (opcional)     │   │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Frontend (React + TypeScript)

**Tecnologías:**
- **React 18**: Librería de UI con hooks
- **TypeScript**: Tipado estático
- **Vite**: Bundler rápido para desarrollo y producción
- **Tailwind CSS**: Framework de estilos utility-first

**Estructura del Frontend** (`frontend/src/`):

```
frontend/src/
├── main.tsx              # Entry point
├── App.tsx               # Componente raíz
├── index.css             # Estilos globales (Tailwind)
│
├── components/           # Componentes React
│   ├── search/           # Búsqueda
│   ├── upload/           # Subida de archivos
│   ├── dashboard/        # Panel de control
│   └── layout/           # Layout (Header, Sidebar)
│
├── pages/                # Páginas/Vistas
│   ├── HomePage.tsx
│   ├── SearchPage.tsx
│   └── DashboardPage.tsx
│
├── hooks/                # Custom hooks
│   ├── useSearch.ts
│   └── useClusterStatus.ts
│
├── services/             # Servicios API
│   └── api.ts
│
└── types/                # TypeScript types
    └── index.ts
```

**Archivos de configuración:**

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "strict": true,
    "jsx": "react-jsx"
  }
}
```

### 2.3 Backend (FastAPI)

**Tecnologías:**
- **FastAPI**: Framework web asíncrono de alto rendimiento
- **Pydantic**: Validación de datos con tipos
- **Uvicorn**: Servidor ASGI
- **Motor**: Cliente async para MongoDB

**Estructura del Backend** (`backend/app/`):

```
backend/app/
├── main.py               # Entry point FastAPI
├── config.py             # Configuración (Pydantic Settings)
│
├── api/                  # Endpoints REST
│   ├── router.py         # Router principal
│   ├── dependencies.py   # Inyección de dependencias
│   ├── websocket.py      # WebSocket endpoints
│   └── v1/
│       └── endpoints/
│           ├── search.py     # POST /search
│           ├── documents.py  # CRUD documentos
│           ├── upload.py     # POST /upload
│           ├── cluster.py    # Estado del cluster
│           └── health.py     # Health checks
│
├── core/                 # Núcleo de negocio
│   ├── vectorization/    # TF-IDF, MinHash, LDA
│   ├── partitioning/     # VP-Tree, asignación
│   ├── rebalancing/      # Rebalanceo activo
│   ├── replication/      # Afinidad semántica
│   ├── recovery/         # Tolerancia a fallos
│   └── search/           # Motor de búsqueda
│
├── distributed/          # Componentes distribuidos
│   ├── consensus/        # Raft
│   ├── coordination/     # Coordinación cluster
│   └── communication/    # gRPC, Gossip
│
├── storage/              # Capa de datos
│   ├── mongodb.py        # Cliente MongoDB
│   ├── redis_cache.py    # Cliente Redis
│   └── sqlite_users.py   # SQLite para usuarios
│
└── middleware/           # Middlewares
    ├── auth.py           # Autenticación JWT
    └── logging.py        # Logging estructurado
```

**Entry Point** (`backend/app/main.py`):

```python
"""
DistriSearch Main Application
Architecture: AP (Available & Partition-tolerant)
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja startup y shutdown."""
    logger.info("Starting DistriSearch...")
    await init_dependencies(settings)
    yield
    await shutdown_dependencies()

def create_application() -> FastAPI:
    app = FastAPI(
        title="DistriSearch API",
        description="Distributed document search system",
        version=settings.app_version,
        lifespan=lifespan
    )
    configure_middleware(app, settings)
    return app
```

### 2.4 Índice Local (VP-Tree + MinHash)

Cada Slave mantiene un **índice local** de sus documentos:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ÍNDICE LOCAL DEL SLAVE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    VP-TREE LOCAL                         │   │
│  │                                                          │   │
│  │         [Centroide]                                      │   │
│  │            /    \                                        │   │
│  │      [VP₁]      [VP₂]                                   │   │
│  │      / \        / \                                      │   │
│  │   [D₁][D₂]   [D₃][D₄]                                   │   │
│  │                                                          │   │
│  │  Permite búsqueda O(log n) en documentos locales        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   MINHASH INDEX                          │   │
│  │                                                          │   │
│  │  Doc1: [0.23, 0.45, 0.12, ...]  (signature)             │   │
│  │  Doc2: [0.34, 0.56, 0.23, ...]                          │   │
│  │  Doc3: [0.45, 0.67, 0.34, ...]                          │   │
│  │                                                          │   │
│  │  Permite estimar similaridad Jaccard O(1)               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Nodo Master

### 3.1 Responsabilidades

```
┌─────────────────────────────────────────────────────────────────┐
│                       MASTER NODE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              COORDINACIÓN DEL CLUSTER                    │   │
│  │                                                          │   │
│  │  • Registro de nodos activos                            │   │
│  │  • Monitoreo de health (heartbeats)                     │   │
│  │  • Detección de fallos                                  │   │
│  │  • Asignación de documentos a nodos                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   VP-TREE GLOBAL                         │   │
│  │                                                          │   │
│  │  • Mantiene particionamiento del espacio vectorial      │   │
│  │  • Vantage points por cada nodo                         │   │
│  │  • Decide ubicación de nuevos documentos                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  CONSENSO RAFT                           │   │
│  │                                                          │   │
│  │  • Elección de líder                                    │   │
│  │  • Replicación de estado crítico                        │   │
│  │  • Tolerancia a fallos del Master                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               REBALANCEO ACTIVO                          │   │
│  │                                                          │   │
│  │  • Detecta nodos sobrecargados                          │   │
│  │  • Planifica migración de documentos                    │   │
│  │  • Ejecuta rebalanceo gradual                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Dockerfile del Master

```dockerfile
# docker/master/Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl

WORKDIR /app

# Dependencias Python
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY backend/ ./backend/
COPY shared/ ./shared/

# Variables de entorno
ENV NODE_ROLE=master \
    API_PORT=8001

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8001/api/v1/health/live || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", "--port", "8001"]
```

### 3.3 API del Master

Endpoints específicos del Master:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/cluster/nodes` | GET | Lista de nodos activos |
| `/api/v1/cluster/status` | GET | Estado del cluster |
| `/api/v1/cluster/assign` | POST | Asignar documento a nodo |
| `/api/v1/cluster/rebalance` | POST | Iniciar rebalanceo |
| `/api/v1/health/live` | GET | Liveness check |
| `/api/v1/health/ready` | GET | Readiness check |

---

## 4. Almacenamiento

### 4.1 Arquitectura de Almacenamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                ESTRATEGIA DE ALMACENAMIENTO                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    MongoDB      │  │     Redis       │  │    SQLite       │ │
│  │   (Documentos)  │  │    (Caché)      │  │   (Usuarios)    │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
│  • LOCAL por nodo     • LOCAL por nodo     • Replicado (Raft) │
│  • Datos principales  • Resultados search  • Autenticación    │
│  • Vectores TF-IDF   • Sesiones           • Metadatos cluster │
│  • MinHash sigs      • Rate limiting      • Nodos registrados │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 MongoDB (Documentos)

**Propósito**: Almacenar documentos y sus vectores

```python
# Esquema del documento en MongoDB
{
    "_id": ObjectId("..."),
    "doc_id": "uuid-string",
    "filename": "reporte_ventas_2024.pdf",
    "content_hash": "sha256:...",
    "created_at": ISODate("2024-01-15T10:30:00Z"),
    "updated_at": ISODate("2024-01-15T10:30:00Z"),
    "owner_id": "user-uuid",
    "node_id": "slave-1",
    
    # Vectores
    "vectors": {
        "name_tfidf": [...],           # Vector TF-IDF del nombre
        "content_minhash": [...],      # Signatures MinHash
        "topic_distribution": [...],   # Distribución LDA
    },
    
    # Metadatos
    "metadata": {
        "size_bytes": 1024000,
        "mime_type": "application/pdf",
        "pages": 15
    }
}
```

**Configuración** (de `backend/app/config.py`):

```python
mongodb_uri: str = Field(
    default="mongodb://mongodb:27017/distrisearch",
    alias="MONGODB_URI"
)
mongodb_database: str = Field(default="distrisearch")
mongodb_max_pool_size: int = Field(default=50)
```

### 4.3 Redis (Caché)

**Propósito**: Caché de búsquedas frecuentes y sesiones

```python
# Ejemplo de uso de caché
cache_key = f"search:{query_hash}"
cached_result = await redis.get(cache_key)

if cached_result:
    return json.loads(cached_result)

# Ejecutar búsqueda
result = await search_engine.search(query)

# Guardar en caché (TTL: 5 minutos)
await redis.setex(cache_key, 300, json.dumps(result))
```

**Configuración**:

```python
redis_url: str = Field(default="redis://redis:6379")
redis_max_connections: int = Field(default=20)
```

### 4.4 SQLite con Raft (Usuarios)

**Propósito**: Datos críticos que requieren consistencia durante particiones

```
┌─────────────────────────────────────────────────────────────────┐
│                SQLite + RAFT REPLICATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐     Raft Log     ┌─────────┐     ┌─────────┐     │
│  │ SQLite  │◄────────────────►│ SQLite  │◄───►│ SQLite  │     │
│  │ Slave-1 │                  │ Slave-2 │     │ Slave-3 │     │
│  └─────────┘                  └─────────┘     └─────────┘     │
│                                                                 │
│  Tablas replicadas:                                            │
│  ─────────────────                                             │
│  • users          (autenticación)                              │
│  • nodes          (registro de nodos)                          │
│  • partitions     (mapeo documento → nodo)                     │
│  • sessions       (sesiones activas)                           │
│                                                                 │
│  Beneficio: Autenticación funciona durante particiones         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Modelos Compartidos

### 5.1 Modelos de Datos

Del directorio `shared/models/`:

```python
# shared/models/node.py
class NodeRole(str, Enum):
    MASTER = "master"
    SLAVE = "slave"

class NodeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAINING = "draining"
    FAILED = "failed"
    STARTING = "starting"
    SYNCING = "syncing"

class Node(BaseModel):
    node_id: str
    role: NodeRole = NodeRole.SLAVE
    status: NodeStatus = NodeStatus.STARTING
    host: str
    port: int = 8000
    grpc_port: int = 50051
    cluster_id: Optional[str] = None
    joined_at: Optional[datetime] = None
```

```python
# shared/models/document.py
class Document(BaseModel):
    doc_id: str
    filename: str
    content_hash: str
    owner_id: str
    node_id: str
    vectors: DocumentVectors
    metadata: DocumentMetadata
    created_at: datetime
```

```python
# shared/models/cluster.py
class ClusterState(BaseModel):
    cluster_id: str
    leader_id: Optional[str]
    nodes: List[Node]
    total_documents: int
    healthy: bool
```

---

## 6. Resumen de Componentes

| Componente | Tecnología | Puerto | Propósito |
|------------|------------|--------|-----------|
| **Load Balancer** | Nginx | 443/80 | Entrada, SSL, balanceo |
| **Frontend** | React + TS | (Nginx) | UI de usuario |
| **Backend** | FastAPI | 8000 | API REST |
| **Master API** | FastAPI | 8001 | Coordinación |
| **gRPC** | grpcio | 50051 | Comunicación interna |
| **MongoDB** | MongoDB 6.0 | 27017 | Documentos |
| **Redis** | Redis 7 | 6379 | Caché |
| **SQLite** | SQLite + Raft | (file) | Usuarios |

---

## 7. Configuración Docker Compose

Archivo `docker/docker-compose.yml`:

```yaml
version: '3.8'

services:
  load-balancer:
    build: ./load-balancer
    ports:
      - "443:443"
      - "80:80"
    depends_on:
      - slave

  master:
    build: ./master
    environment:
      - NODE_ROLE=master
      - RAFT_PEERS=master
    ports:
      - "8001:8001"

  slave:
    build: ./slave
    environment:
      - NODE_ROLE=slave
      - MASTER_HOST=master
      - MONGODB_URI=mongodb://mongodb:27017/distrisearch
    deploy:
      replicas: 3

  mongodb:
    image: mongo:6.0
    volumes:
      - mongodb-data:/data/db

  redis:
    image: redis:7-alpine

networks:
  default:
    driver: overlay
    attachable: true

volumes:
  mongodb-data:
```

---

> **Siguiente**: [03_Estructura_Proyecto.md](03_Estructura_Proyecto.md) para ver la organización completa del código fuente.