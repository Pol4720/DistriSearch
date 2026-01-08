# Estructura del Proyecto DistriSearch

## Organización del Código Fuente

---

## 1. Visión General de Directorios

```
DistriSearch/
│
├── 📁 backend/              # API REST Python (FastAPI)
├── 📁 frontend/             # Aplicación React + TypeScript
├── 📁 docker/               # Configuración de contenedores
├── 📁 shared/               # Código compartido entre componentes
├── 📁 tests/                # Tests (unit, integration, distributed)
├── 📁 scripts/              # Scripts de utilidad
├── 📁 control-center/       # Panel de administración
├── 📁 deploy/               # Guías y scripts de despliegue
├── 📁 docs/                 # Documentación técnica
│
├── pyproject.toml           # Configuración del proyecto Python
├── requirements-dev.txt     # Dependencias de desarrollo
├── pytest.ini               # Configuración de pytest
├── mypy.ini                 # Configuración de tipado estático
└── .pre-commit-config.yaml  # Hooks de pre-commit
```

---

## 2. Directorio `backend/`

El corazón del sistema: **API REST con FastAPI**.

```
backend/
├── .env                    # Variables de entorno (no commitear)
├── requirements.txt        # Dependencias Python
│
└── app/
    ├── __init__.py
    ├── main.py             # 🔴 Entry point de FastAPI
    ├── config.py           # 🔴 Configuración centralizada
    │
    ├── 📁 api/             # Capa de API REST
    │   ├── router.py       # Router principal
    │   ├── dependencies.py # Inyección de dependencias
    │   ├── websocket.py    # WebSocket para tiempo real
    │   └── v1/
    │       └── endpoints/
    │           ├── search.py     # POST /api/v1/search
    │           ├── documents.py  # CRUD documentos
    │           ├── upload.py     # POST /api/v1/upload
    │           ├── cluster.py    # Estado cluster
    │           └── health.py     # Health checks
    │
    ├── 📁 core/            # Lógica de negocio
    │   ├── vectorization/  # TF-IDF, MinHash, LDA
    │   ├── partitioning/   # VP-Tree, asignación
    │   ├── rebalancing/    # Rebalanceo activo
    │   ├── replication/    # Replicación con afinidad
    │   ├── recovery/       # Tolerancia a fallos
    │   └── search/         # Motor de búsqueda
    │
    ├── 📁 distributed/     # Componentes distribuidos
    │   ├── consensus/      # Implementación Raft
    │   ├── coordination/   # Coordinación cluster
    │   └── communication/  # gRPC, Gossip
    │
    ├── 📁 grpc/            # Definiciones gRPC
    │   └── protos/         # Archivos .proto
    │
    ├── 📁 middleware/      # Middlewares FastAPI
    │   ├── auth.py         # Autenticación JWT
    │   └── logging.py      # Logging estructurado
    │
    └── 📁 storage/         # Capa de datos
        ├── mongodb.py      # Cliente MongoDB
        ├── redis_cache.py  # Cliente Redis
        └── sqlite_users.py # SQLite para usuarios
```

### Archivos Clave del Backend

**`main.py`** - Punto de entrada:
```python
"""
DistriSearch Main Application
Architecture: AP (Available & Partition-tolerant)
"""
from fastapi import FastAPI
from .config import Settings, get_settings
from .api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DistriSearch...")
    await init_dependencies(settings)
    yield
    await shutdown_dependencies()

def create_application() -> FastAPI:
    app = FastAPI(
        title="DistriSearch API",
        version=settings.app_version,
        lifespan=lifespan
    )
    return app
```

**`config.py`** - Configuración:
```python
class Settings(BaseSettings):
    # Nodo
    node_id: str = Field(default="node-1", alias="NODE_ID")
    node_role: str = Field(default="slave", alias="NODE_ROLE")
    
    # Master
    master_host: str = Field(default="master", alias="MASTER_HOST")
    master_port: int = Field(default=8001, alias="MASTER_PORT")
    
    # MongoDB
    mongodb_uri: str = Field(default="mongodb://mongodb:27017/distrisearch")
    
    # Raft
    raft_election_timeout_min: int = 150
    raft_heartbeat_interval: int = 50
    
    # Rebalanceo
    rebalance_threshold: float = 0.8
    rebalance_batch_size: int = 50
```

---

## 3. Directorio `frontend/`

Aplicación **React + TypeScript** con Vite.

```
frontend/
├── index.html              # HTML base
├── package.json            # Dependencias npm
├── tsconfig.json           # Configuración TypeScript
├── vite.config.ts          # Configuración Vite
├── tailwind.config.js      # Configuración Tailwind CSS
├── postcss.config.js       # PostCSS para Tailwind
│
└── src/
    ├── main.tsx            # 🔴 Entry point React
    ├── App.tsx             # 🔴 Componente raíz
    ├── index.css           # Estilos globales (Tailwind)
    ├── vite-env.d.ts       # Tipos de Vite
    │
    ├── 📁 components/      # Componentes React
    │   ├── search/         # Componentes de búsqueda
    │   ├── upload/         # Componentes de subida
    │   ├── dashboard/      # Panel de control
    │   └── layout/         # Header, Sidebar, Footer
    │
    ├── 📁 pages/           # Páginas/Vistas
    │   ├── HomePage.tsx
    │   ├── SearchPage.tsx
    │   ├── UploadPage.tsx
    │   └── DashboardPage.tsx
    │
    ├── 📁 hooks/           # Custom hooks
    │   ├── useSearch.ts
    │   ├── useUpload.ts
    │   └── useClusterStatus.ts
    │
    ├── 📁 services/        # Servicios API
    │   └── api.ts          # Cliente HTTP
    │
    └── 📁 types/           # TypeScript types
        └── index.ts
```

### Archivos Clave del Frontend

**`package.json`**:
```json
{
  "name": "distrisearch-frontend",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.x"
  },
  "devDependencies": {
    "typescript": "^5.x",
    "vite": "^5.x",
    "@types/react": "^18.x",
    "tailwindcss": "^3.x"
  }
}
```

**`vite.config.ts`**:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

---

## 4. Directorio `docker/`

Configuración de **contenedores y orquestación**.

```
docker/
├── docker-compose.yml              # 🔴 Orquestación principal
├── docker-compose.local.yml        # Desarrollo local
├── docker-compose.distributed.yml  # Modo distribuido
├── docker-compose.swarm.yml        # Docker Swarm
├── docker-compose.test.yml         # Tests
│
├── 📁 load-balancer/
│   ├── Dockerfile
│   ├── nginx.conf                  # 🔴 Configuración Nginx
│   ├── supervisord-lb.conf
│   ├── update-upstreams.sh         # Script dinámico
│   └── conf.d/
│       └── upstreams/              # Upstreams generados
│
├── 📁 master/
│   ├── Dockerfile                  # 🔴 Imagen Master
│   └── entrypoint.sh
│
├── 📁 slave/
│   ├── Dockerfile                  # 🔴 Imagen Slave
│   ├── entrypoint.sh
│   ├── generate-ssl.sh             # Genera certificados
│   ├── nginx-frontend.conf         # Nginx para frontend
│   ├── nginx-https.conf            # HTTPS config
│   └── supervisord.conf            # Supervisor config
│
├── 📁 mongodb/
│   └── init-replica.js             # Inicializa replica set
│
├── 📁 coredns/
│   ├── Dockerfile
│   ├── Corefile                    # 🔴 Config CoreDNS
│   └── zones/
│       └── distrisearch.local.zone
│
└── 📁 dns-sync/
    ├── Dockerfile
    └── sync_dns_zone.py            # Sincroniza DNS
```

### Archivos Docker Clave

**`docker-compose.yml`** (simplificado):
```yaml
version: '3.8'

services:
  load-balancer:
    build: ./load-balancer
    ports:
      - "443:443"
    networks:
      - distrisearch-network

  master:
    build: ./master
    environment:
      - NODE_ROLE=master
    ports:
      - "8001:8001"

  slave:
    build: ./slave
    environment:
      - NODE_ROLE=slave
      - MASTER_HOST=master
    deploy:
      replicas: 3

  mongodb:
    image: mongo:6.0
    volumes:
      - mongodb-data:/data/db

  redis:
    image: redis:7-alpine

networks:
  distrisearch-network:
    driver: overlay

volumes:
  mongodb-data:
```

**`slave/Dockerfile`** (multi-stage):
```dockerfile
# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
COPY frontend/ ./
RUN npm ci && npm run build

# Stage 2: Build Backend
FROM python:3.11-slim AS backend-builder
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Stage 3: Runtime
FROM python:3.11-slim
RUN apt-get install -y nginx supervisor
COPY --from=frontend-builder /dist /var/www/html
COPY --from=backend-builder /opt/venv /opt/venv
COPY backend/ ./backend/
EXPOSE 443 8000
```

---

## 5. Directorio `shared/`

Código **compartido** entre componentes.

```
shared/
├── __init__.py
│
├── 📁 constants/
│   ├── __init__.py
│   └── config.py           # Constantes globales
│
├── 📁 models/
│   ├── __init__.py
│   ├── cluster.py          # 🔴 Modelo ClusterState
│   ├── document.py         # 🔴 Modelo Document
│   └── node.py             # 🔴 Modelo Node
│
└── 📁 protocols/
    ├── __init__.py
    ├── events.py           # Eventos del sistema
    └── messages.py         # Mensajes entre nodos
```

### Modelos Compartidos

**`node.py`**:
```python
class NodeRole(str, Enum):
    MASTER = "master"
    SLAVE = "slave"

class NodeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAINING = "draining"
    FAILED = "failed"

class Node(BaseModel):
    node_id: str
    role: NodeRole
    status: NodeStatus
    host: str
    port: int = 8000
```

**`document.py`**:
```python
class Document(BaseModel):
    doc_id: str
    filename: str
    owner_id: str
    node_id: str
    vectors: DocumentVectors
    created_at: datetime
```

---

## 6. Directorio `tests/`

Tests organizados por tipo.

```
tests/
├── __init__.py
│
├── 📁 unit/                # Tests unitarios
│   ├── test_vectorization.py
│   ├── test_vp_tree.py
│   └── test_minhash.py
│
├── 📁 integration/         # Tests de integración
│   ├── test_api_search.py
│   ├── test_api_upload.py
│   └── test_mongodb.py
│
└── 📁 distributed/         # Tests del sistema distribuido
    ├── test_consensus_leader_election.py  # 🔴 Test Raft
    ├── test_load_balancing.py             # 🔴 Test balanceo
    ├── test_replication.py
    └── test_partition_tolerance.py
```

### Configuración de Tests

**`pytest.ini`**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
asyncio_mode = auto
```

**`backend/tests/test_adaptive_cluster.py`**:
```python
"""Tests for adaptive cluster behavior."""

import pytest
from backend.app.distributed.coordination import ClusterCoordinator

@pytest.mark.asyncio
async def test_node_joins_cluster():
    coordinator = ClusterCoordinator()
    result = await coordinator.register_node(node_info)
    assert result.success
    assert node_info.node_id in coordinator.active_nodes
```

---

## 7. Directorio `scripts/`

Scripts de utilidad y automatización.

```
scripts/
├── benchmark.py            # Benchmark de rendimiento
├── deploy.sh               # Script de despliegue
├── healthcheck.py          # Verificación de salud
├── load_data.py            # Carga datos de prueba
├── migrate_data.py         # Migración de datos
├── setup_dev.ps1           # Setup Windows (PowerShell)
└── setup_dev.sh            # Setup Linux/Mac
```

**`healthcheck.py`**:
```python
"""Health check script for all nodes."""

async def check_node_health(node_url: str) -> bool:
    try:
        response = await client.get(f"{node_url}/api/v1/health")
        return response.status_code == 200
    except Exception:
        return False
```

---

## 8. Directorio `control-center/`

**Panel de administración** con Streamlit.

```
control-center/
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.backend
├── Dockerfile.frontend
├── README.md
│
├── 📁 backend/
│   ├── main.py             # API del panel
│   ├── requirements.txt
│   ├── routers/            # Endpoints
│   └── services/           # Lógica de negocio
│
└── 📁 frontend/
    ├── 🏠_Panel_Principal.py  # 🔴 Página principal Streamlit
    ├── requirements.txt
    ├── .streamlit/
    │   └── config.toml
    └── pages/
        ├── 1_📊_Cluster.py
        ├── 2_📁_Documents.py
        └── 3_⚙️_Settings.py
```

---

## 9. Directorio `deploy/`

Guías y scripts de **despliegue**.

```
deploy/
└── manual-swarm/
    ├── GUIA_DESPLIEGUE.md  # 🔴 Guía paso a paso
    └── scripts/
        ├── 01-prepare-node.sh
        ├── 02-init-swarm.sh
        ├── 03-join-swarm.sh
        ├── 04-deploy-mongodb.sh
        ├── 05-deploy-master.sh
        ├── 06-deploy-slave.sh
        └── 07-verify-cluster.sh
```

---

## 10. Archivos de Configuración Raíz

| Archivo | Propósito |
|---------|-----------|
| `pyproject.toml` | Configuración del proyecto Python (black, isort, etc.) |
| `requirements-dev.txt` | Dependencias de desarrollo |
| `pytest.ini` | Configuración de pytest |
| `mypy.ini` | Configuración de tipado estático |
| `.pre-commit-config.yaml` | Hooks de pre-commit |
| `.flake8` | Configuración de linter |

**`pyproject.toml`**:
```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
strict = true
```

---

## 11. Flujo de Interacción entre Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                   FLUJO DE COMPONENTES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  frontend/src/services/api.ts                                   │
│         │                                                       │
│         │ HTTP Request                                          │
│         ▼                                                       │
│  docker/load-balancer/nginx.conf                                │
│         │                                                       │
│         │ Proxy Pass                                            │
│         ▼                                                       │
│  backend/app/api/v1/endpoints/*.py                              │
│         │                                                       │
│         │ Lógica de negocio                                     │
│         ▼                                                       │
│  backend/app/core/search/search_engine.py                       │
│         │                                                       │
│         │ Vectorización                                         │
│         ▼                                                       │
│  backend/app/core/vectorization/document_vectorizer.py          │
│         │                                                       │
│         │ Almacenamiento                                        │
│         ▼                                                       │
│  backend/app/storage/mongodb.py                                 │
│         │                                                       │
│         │ Coordinación                                          │
│         ▼                                                       │
│  backend/app/distributed/coordination/cluster_coordinator.py    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Comandos Útiles para Desarrollo

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Docker (desarrollo local)
docker-compose -f docker/docker-compose.local.yml up -d

# Tests
pytest tests/ -v

# Linting
black backend/
isort backend/
mypy backend/
flake8 backend/
```

---

## 13. Resumen de Archivos Críticos

| Archivo | Descripción | Importancia |
|---------|-------------|-------------|
| `backend/app/main.py` | Entry point de FastAPI | 🔴 Crítico |
| `backend/app/config.py` | Toda la configuración | 🔴 Crítico |
| `docker/docker-compose.yml` | Orquestación | 🔴 Crítico |
| `docker/slave/Dockerfile` | Imagen del Slave | 🔴 Crítico |
| `docker/master/Dockerfile` | Imagen del Master | 🔴 Crítico |
| `docker/load-balancer/nginx.conf` | Config Nginx | 🟡 Importante |
| `shared/models/node.py` | Modelo de nodo | 🟡 Importante |
| `frontend/src/App.tsx` | Componente raíz React | 🟡 Importante |

---

> **Anterior**: [02_Componentes_Principales.md](02_Componentes_Principales.md)
> 
> **Siguiente sección**: [../02_Vectorizacion_Busqueda/README.md](../02_Vectorizacion_Busqueda/README.md) para entender el sistema de vectorización.