# Arquitectura de Software - DistriSearch

## Sistema de Búsqueda Distribuida con Balanceo de Carga

---

## 1. Visión General de la Arquitectura

DistriSearch implementa una arquitectura distribuida **Master-Slave con Load Balancer** que permite escalar horizontalmente tanto el frontend como el backend. El sistema utiliza vectorización adaptativa (TF-IDF + MinHash) para la búsqueda semántica sin depender de embeddings pre-entrenados.

```
                                    ┌─────────────────────┐
                                    │      CLIENTES       │
                                    │   (Navegadores)     │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │        LOAD BALANCER           │
                              │    (Nginx / HAProxy / Traefik) │
                              │                                │
                              │  - Round Robin / Least Conn    │
                              │  - Health Checks               │
                              │  - SSL Termination             │
                              └────────────────────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
        ┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
        │     SLAVE 1       │      │     SLAVE 2       │      │     SLAVE N       │
        │  ┌─────────────┐  │      │  ┌─────────────┐  │      │  ┌─────────────┐  │
        │  │  Frontend   │  │      │  │  Frontend   │  │      │  │  Frontend   │  │
        │  │   (React)   │  │      │  │   (React)   │  │      │  │   (React)   │  │
        │  └──────┬──────┘  │      │  └──────┬──────┘  │      │  └──────┬──────┘  │
        │         │         │      │         │         │      │         │         │
        │  ┌──────▼──────┐  │      │  ┌──────▼──────┐  │      │  ┌──────▼──────┐  │
        │  │  Backend    │  │      │  │  Backend    │  │      │  │  Backend    │  │
        │  │ (Python API)│  │      │  │ (Python API)│  │      │  │ (Python API)│  │
        │  └──────┬──────┘  │      │  └──────┬──────┘  │      │  └──────┬──────┘  │
        │         │         │      │         │         │      │         │         │
        │  ┌──────▼──────┐  │      │  ┌──────▼──────┐  │      │  ┌──────▼──────┐  │
        │  │  Índice     │  │      │  │  Índice     │  │      │  │  Índice     │  │
        │  │  Local      │  │      │  │  Local      │  │      │  │  Local      │  │
        │  └─────────────┘  │      │  └─────────────┘  │      │  └─────────────┘  │
        └─────────┬─────────┘      └─────────┬─────────┘      └─────────┬─────────┘
                  │                          │                          │
                  └──────────────────────────┼──────────────────────────┘
                                             │
                                             ▼
                              ┌────────────────────────────────┐
                              │         MASTER NODE            │
                              │                                │
                              │  - Coordinador de Particiones  │
                              │  - VP-Tree Global              │
                              │  - Elección de Líder (Raft)    │
                              │  - Rebalanceo Activo           │
                              └────────────────────────────────┘
                                             │
                                             ▼
                              ┌────────────────────────────────┐
                              │      ALMACENAMIENTO            │
                              │   (MongoDB / PostgreSQL)       │
                              │                                │
                              │  - Índice de Particiones       │
                              │  - Metadatos de Documentos     │
                              │  - Log de Operaciones          │
                              └────────────────────────────────┘
```

---

## 2. Componentes Principales

### 2.1 Load Balancer

**Responsabilidades:**
- Distribuir tráfico entrante entre los nodos slave
- Health checks periódicos para detectar nodos caídos
- Terminación SSL/TLS
- Rate limiting y protección DDoS básica

**Tecnologías recomendadas:**
- **Nginx** (simple, alto rendimiento)
- **HAProxy** (más features de balanceo)
- **Traefik** (ideal para Docker/Kubernetes)

### 2.2 Nodos Slave

Cada slave es una unidad autónoma que contiene:

| Componente | Tecnología | Puerto |
|------------|------------|--------|
| Frontend | React (Nginx serve) | 80/443 |
| Backend API | Python (FastAPI/Flask) | 8000 |
| Índice Local | VP-Tree + MinHash | - |
| Almacenamiento Local | Sistema de archivos | - |

### 2.3 Master Node

**Responsabilidades:**
- Mantener el VP-Tree global de particiones
- Coordinar rebalanceo al añadir/remover nodos
- Gestionar replicación con afinidad semántica
- Consenso mediante Raft-Lite
- Persistir estado del cluster

### 2.4 Almacenamiento Centralizado

**MongoDB** para:
- Índice de particiones (qué documento está en qué nodo)
- Metadatos de documentos vectorizados
- Log de operaciones para recuperación
- Estado del cluster

---

## 3. Estructura de Archivos y Carpetas

```
DistriSearch/
│
├── 📁 docker/                          # Configuración de contenedores
│   ├── docker-compose.yml              # Orquestación completa
│   ├── docker-compose.dev.yml          # Desarrollo local
│   ├── docker-compose.prod.yml         # Producción
│   │
│   ├── 📁 load-balancer/
│   │   ├── Dockerfile
│   │   ├── nginx.conf                  # Configuración Nginx
│   │   ├── haproxy.cfg                 # Alternativa HAProxy
│   │   └── ssl/                        # Certificados SSL
│   │
│   ├── 📁 slave/
│   │   ├── Dockerfile                  # Imagen combinada frontend+backend
│   │   └── entrypoint.sh
│   │
│   └── 📁 master/
│       ├── Dockerfile
│       └── entrypoint.sh
│
├── 📁 frontend/                        # Aplicación React
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json                   # TypeScript config
│   ├── vite.config.ts                  # Vite como bundler
│   ├── .env.example
│   │
│   ├── 📁 public/
│   │   ├── index.html
│   │   ├── favicon.ico
│   │   └── 📁 assets/
│   │
│   └── 📁 src/
│       ├── main.tsx                    # Entry point
│       ├── App.tsx                     # Componente raíz
│       ├── index.css                   # Estilos globales
│       │
│       ├── 📁 components/              # Componentes React
│       │   ├── 📁 common/              # Componentes reutilizables
│       │   │   ├── Button.tsx
│       │   │   ├── Input.tsx
│       │   │   ├── Modal.tsx
│       │   │   ├── Spinner.tsx
│       │   │   └── Toast.tsx
│       │   │
│       │   ├── 📁 search/              # Búsqueda
│       │   │   ├── SearchBar.tsx
│       │   │   ├── SearchResults.tsx
│       │   │   ├── SearchFilters.tsx
│       │   │   └── ResultCard.tsx
│       │   │
│       │   ├── 📁 upload/              # Subida de archivos
│       │   │   ├── FileUploader.tsx
│       │   │   ├── DragDropZone.tsx
│       │   │   └── UploadProgress.tsx
│       │   │
│       │   ├── 📁 dashboard/           # Panel de control
│       │   │   ├── ClusterStatus.tsx
│       │   │   ├── NodeCard.tsx
│       │   │   ├── ReplicationStatus.tsx
│       │   │   └── SystemMetrics.tsx
│       │   │
│       │   └── 📁 layout/              # Layout
│       │       ├── Header.tsx
│       │       ├── Sidebar.tsx
│       │       └── Footer.tsx
│       │
│       ├── 📁 pages/                   # Páginas/Vistas
│       │   ├── HomePage.tsx
│       │   ├── SearchPage.tsx
│       │   ├── UploadPage.tsx
│       │   ├── DashboardPage.tsx
│       │   └── NotFoundPage.tsx
│       │
│       ├── 📁 hooks/                   # Custom hooks
│       │   ├── useSearch.ts
│       │   ├── useUpload.ts
│       │   ├── useClusterStatus.ts
│       │   └── useWebSocket.ts
│       │
│       ├── 📁 services/                # Servicios API
│       │   ├── api.ts                  # Cliente Axios/Fetch
│       │   ├── searchService.ts
│       │   ├── uploadService.ts
│       │   └── clusterService.ts
│       │
│       ├── 📁 store/                   # Estado global (Zustand/Redux)
│       │   ├── index.ts
│       │   ├── searchStore.ts
│       │   └── clusterStore.ts
│       │
│       ├── 📁 types/                   # TypeScript types
│       │   ├── index.ts
│       │   ├── search.types.ts
│       │   ├── document.types.ts
│       │   └── cluster.types.ts
│       │
│       └── 📁 utils/                   # Utilidades
│           ├── formatters.ts
│           ├── validators.ts
│           └── constants.ts
│
├── 📁 backend/                         # API REST Python
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── setup.py
│   ├── .env.example
│   │
│   ├── 📁 app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app entry
│   │   ├── config.py                   # Configuración
│   │   │
│   │   ├── 📁 api/                     # Endpoints REST
│   │   │   ├── __init__.py
│   │   │   ├── 📁 v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py           # Router principal v1
│   │   │   │   ├── 📁 endpoints/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── search.py       # POST /search
│   │   │   │   │   ├── documents.py    # CRUD documentos
│   │   │   │   │   ├── upload.py       # POST /upload
│   │   │   │   │   ├── cluster.py      # Estado del cluster
│   │   │   │   │   └── health.py       # Health checks
│   │   │   │   │
│   │   │   │   └── 📁 schemas/         # Pydantic schemas
│   │   │   │       ├── __init__.py
│   │   │   │       ├── search.py
│   │   │   │       ├── document.py
│   │   │   │       └── cluster.py
│   │   │   │
│   │   │   └── dependencies.py         # Dependencias inyectables
│   │   │
│   │   ├── 📁 core/                    # Núcleo de negocio
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── 📁 vectorization/       # Vectorización adaptativa
│   │   │   │   ├── __init__.py
│   │   │   │   ├── document_vectorizer.py
│   │   │   │   ├── tfidf_processor.py
│   │   │   │   ├── minhash_signature.py
│   │   │   │   ├── textrank_keywords.py
│   │   │   │   ├── lda_topics.py
│   │   │   │   └── char_ngrams.py
│   │   │   │
│   │   │   ├── 📁 partitioning/        # Partición VP-Tree
│   │   │   │   ├── __init__.py
│   │   │   │   ├── vp_tree.py
│   │   │   │   ├── partition_index.py
│   │   │   │   ├── distance_metrics.py
│   │   │   │   └── node_assignment.py
│   │   │   │
│   │   │   ├── 📁 rebalancing/         # Rebalanceo activo
│   │   │   │   ├── __init__.py
│   │   │   │   ├── active_rebalancer.py
│   │   │   │   ├── migration_handler.py
│   │   │   │   └── load_calculator.py
│   │   │   │
│   │   │   ├── 📁 replication/         # Replicación con afinidad
│   │   │   │   ├── __init__.py
│   │   │   │   ├── affinity_replicator.py
│   │   │   │   ├── similarity_graph.py
│   │   │   │   └── replica_tracker.py
│   │   │   │
│   │   │   ├── 📁 recovery/            # Recuperación ante fallos
│   │   │   │   ├── __init__.py
│   │   │   │   ├── failure_detector.py
│   │   │   │   ├── recovery_service.py
│   │   │   │   └── re_replication.py
│   │   │   │
│   │   │   └── 📁 search/              # Motor de búsqueda
│   │   │       ├── __init__.py
│   │   │       ├── search_engine.py
│   │   │       ├── query_processor.py
│   │   │       ├── result_aggregator.py
│   │   │       └── ranking.py
│   │   │
│   │   ├── 📁 distributed/             # Componentes distribuidos
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── 📁 consensus/           # Elección de líder
│   │   │   │   ├── __init__.py
│   │   │   │   ├── raft_lite.py
│   │   │   │   ├── leader_election.py
│   │   │   │   └── state_machine.py
│   │   │   │
│   │   │   ├── 📁 communication/       # Comunicación inter-nodos
│   │   │   │   ├── __init__.py
│   │   │   │   ├── grpc_client.py
│   │   │   │   ├── grpc_server.py
│   │   │   │   ├── message_broker.py
│   │   │   │   └── heartbeat.py
│   │   │   │
│   │   │   └── 📁 coordination/        # Coordinación
│   │   │       ├── __init__.py
│   │   │       ├── master_coordinator.py
│   │   │       ├── slave_handler.py
│   │   │       └── cluster_manager.py
│   │   │
│   │   ├── 📁 storage/                 # Capa de almacenamiento
│   │   │   ├── __init__.py
│   │   │   ├── 📁 database/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── mongodb_client.py
│   │   │   │   ├── models.py
│   │   │   │   └── repositories.py
│   │   │   │
│   │   │   ├── 📁 filesystem/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── file_handler.py
│   │   │   │   └── content_extractor.py
│   │   │   │
│   │   │   └── 📁 cache/
│   │   │       ├── __init__.py
│   │   │       └── redis_cache.py
│   │   │
│   │   ├── 📁 utils/                   # Utilidades
│   │   │   ├── __init__.py
│   │   │   ├── logging.py
│   │   │   ├── exceptions.py
│   │   │   ├── validators.py
│   │   │   └── helpers.py
│   │   │
│   │   └── 📁 middleware/              # Middleware
│   │       ├── __init__.py
│   │       ├── cors.py
│   │       ├── auth.py
│   │       └── rate_limiter.py
│   │
│   ├── 📁 protos/                      # gRPC Protocol Buffers
│   │   ├── cluster.proto
│   │   ├── search.proto
│   │   └── replication.proto
│   │
│   └── 📁 tests/                       # Tests
│       ├── __init__.py
│       ├── conftest.py
│       ├── 📁 unit/
│       │   ├── test_vectorization.py
│       │   ├── test_partitioning.py
│       │   └── test_search.py
│       │
│       ├── 📁 integration/
│       │   ├── test_api_endpoints.py
│       │   └── test_cluster_operations.py
│       │
│       └── 📁 e2e/
│           └── test_full_flow.py
│
├── 📁 master/                          # Código específico del Master
│   ├── requirements.txt
│   ├── 📁 app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── coordinator.py              # Coordinador principal
│   │   ├── vp_tree_manager.py          # Gestión VP-Tree global
│   │   ├── rebalance_orchestrator.py   # Orquestador de rebalanceo
│   │   └── failover_handler.py         # Manejo de failover
│   │
│   └── 📁 tests/
│       └── test_master.py
│
├── 📁 shared/                          # Código compartido
│   ├── __init__.py
│   ├── 📁 models/
│   │   ├── __init__.py
│   │   ├── document.py
│   │   ├── node.py
│   │   └── cluster.py
│   │
│   ├── 📁 protocols/
│   │   ├── __init__.py
│   │   ├── messages.py
│   │   └── events.py
│   │
│   └── 📁 constants/
│       ├── __init__.py
│       └── config.py
│
├── 📁 scripts/                         # Scripts de utilidad
│   ├── setup_cluster.sh                # Inicializar cluster
│   ├── add_node.sh                     # Añadir nodo
│   ├── remove_node.sh                  # Remover nodo
│   ├── backup.sh                       # Backup del índice
│   └── generate_protos.sh              # Generar código gRPC
│
├── 📁 config/                          # Configuraciones
│   ├── 📁 development/
│   │   ├── .env
│   │   └── config.yaml
│   │
│   ├── 📁 production/
│   │   ├── .env
│   │   └── config.yaml
│   │
│   └── 📁 testing/
│       ├── .env
│       └── config.yaml
│
├── 📁 docs/                            # Documentación
│   ├── mkdocs.yml
│   ├── 📁 docs/
│   │   ├── index.md
│   │   ├── arquitectura.md
│   │   ├── api-reference.md
│   │   ├── deployment.md
│   │   └── 📁 guides/
│   │       ├── getting-started.md
│   │       ├── configuration.md
│   │       └── troubleshooting.md
│   │
│   └── 📁 diagrams/
│       ├── architecture.drawio
│       ├── sequence-search.drawio
│       └── sequence-rebalance.drawio
│
├── 📁 monitoring/                      # Monitoreo
│   ├── 📁 prometheus/
│   │   └── prometheus.yml
│   │
│   ├── 📁 grafana/
│   │   └── 📁 dashboards/
│   │       ├── cluster-overview.json
│   │       └── node-metrics.json
│   │
│   └── 📁 alertmanager/
│       └── alertmanager.yml
│
├── .gitignore
├── README.md
├── LICENSE
└── Makefile                            # Comandos de desarrollo
```

---

## 4. Flujos de Datos Principales

### 4.1 Flujo de Búsqueda

```
┌─────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────────┐
│ Cliente │────▶│Load Balancer │────▶│  Slave N  │────▶│ Backend API  │
└─────────┘     └──────────────┘     └───────────┘     └──────┬───────┘
                                                              │
                                     ┌────────────────────────┘
                                     ▼
                              ┌─────────────┐
                              │   Master    │
                              │  (VP-Tree)  │
                              └──────┬──────┘
                                     │ Identificar nodos relevantes
                                     ▼
                    ┌────────────────┬────────────────┐
                    ▼                ▼                ▼
             ┌───────────┐    ┌───────────┐    ┌───────────┐
             │ Slave 1   │    │ Slave 2   │    │ Slave K   │
             │ (búsqueda │    │ (búsqueda │    │ (búsqueda │
             │  local)   │    │  local)   │    │  local)   │
             └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
                   │                │                │
                   └────────────────┼────────────────┘
                                    ▼
                           ┌────────────────┐
                           │   Agregación   │
                           │   y Ranking    │
                           └────────┬───────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  Resultados  │
                            │  al Cliente  │
                            └──────────────┘
```

### 4.2 Flujo de Subida de Documento

```
┌─────────┐     ┌──────────────┐     ┌───────────┐
│ Cliente │────▶│Load Balancer │────▶│  Slave N  │
│ (upload)│     └──────────────┘     └─────┬─────┘
└─────────┘                                │
                                           ▼
                                    ┌─────────────┐
                                    │Vectorización│
                                    │ Adaptativa  │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │   Master    │
                                    │ (asignar   │
                                    │   nodo)    │
                                    └──────┬──────┘
                                           │
                          ┌────────────────┴────────────────┐
                          ▼                                 ▼
                   ┌─────────────┐                  ┌─────────────┐
                   │Almacenar en │                  │  Replicar   │
                   │nodo primario│                  │ con afinidad│
                   └─────────────┘                  └─────────────┘
```

### 4.3 Flujo de Rebalanceo (Nuevo Nodo)

```
┌──────────────┐
│ Nuevo Nodo   │
│ se une       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Master     │
│ detecta      │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│ 1. Recalcular VP-Tree                │
│ 2. Identificar docs a migrar         │
│    (Power of Two Choices)            │
│ 3. Ordenar por afinidad semántica    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Migración gradual en batches         │
│ (mantener réplica temporal)          │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Actualizar índice de particiones     │
│ y notificar a todos los nodos        │
└──────────────────────────────────────┘
```

---

## 5. API REST - Endpoints Principales

### 5.1 Búsqueda

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/search` | Búsqueda semántica |
| `GET` | `/api/v1/search/suggestions` | Autocompletado |

**Request Body (POST /search):**
```json
{
  "query": "reporte ventas Q1",
  "filters": {
    "extension": [".xlsx", ".pdf"],
    "date_range": {
      "from": "2024-01-01",
      "to": "2024-12-31"
    }
  },
  "limit": 20,
  "offset": 0
}
```

### 5.2 Documentos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/documents/upload` | Subir documento |
| `GET` | `/api/v1/documents/{id}` | Obtener documento |
| `DELETE` | `/api/v1/documents/{id}` | Eliminar documento |
| `GET` | `/api/v1/documents/{id}/download` | Descargar archivo |

### 5.3 Cluster

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/cluster/status` | Estado del cluster |
| `GET` | `/api/v1/cluster/nodes` | Lista de nodos |
| `POST` | `/api/v1/cluster/rebalance` | Forzar rebalanceo |
| `GET` | `/api/v1/cluster/metrics` | Métricas del sistema |

### 5.4 Health

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Health check básico |
| `GET` | `/health/ready` | Readiness check |
| `GET` | `/health/live` | Liveness check |

---

## 6. Tecnologías Recomendadas

### Frontend
| Categoría | Tecnología | Justificación |
|-----------|------------|---------------|
| Framework | React 18+ | Ecosistema maduro, hooks |
| Lenguaje | TypeScript | Tipado estático |
| Bundler | Vite | Rápido, HMR |
| Estado | Zustand | Simple, performante |
| HTTP Client | Axios / TanStack Query | Caching, retry |
| UI Components | Tailwind CSS + Headless UI | Flexible, accesible |
| Testing | Vitest + React Testing Library | Rápido, compatible |

### Backend
| Categoría | Tecnología | Justificación |
|-----------|------------|---------------|
| Framework | FastAPI | Async, OpenAPI auto |
| Lenguaje | Python 3.11+ | Tipado, ML libs |
| ASGI Server | Uvicorn | Alto rendimiento |
| Comunicación | gRPC | Eficiente inter-nodos |
| Base de Datos | MongoDB | Flexible, escalable |
| Cache | Redis | Rápido, pub/sub |
| Testing | pytest + pytest-asyncio | Completo |

### Infraestructura
| Categoría | Tecnología | Justificación |
|-----------|------------|---------------|
| Contenedores | Docker | Estándar |
| Orquestación | Docker Swarm / K8s | Escalabilidad |
| Load Balancer | Nginx / Traefik | Probado, configurable |
| Monitoreo | Prometheus + Grafana | Estándar industria |
| Logs | ELK Stack / Loki | Centralizado |

---

## 7. Consideraciones de Escalabilidad

### 7.1 Escalado Horizontal

```
                    Carga Baja              Carga Media             Carga Alta
                    ──────────              ───────────             ──────────
                    
Load Balancer       [LB]                    [LB]                    [LB] [LB]
                      │                       │                       │    │
                      │                   ┌───┴───┐               ┌───┴────┴───┐
                      │                   │       │               │    │    │  │
Slaves              [S1]               [S1]    [S2]           [S1] [S2] [S3] [S4]
                      │                   │       │               │    │    │   │
Master              [M]                  [M]     [M]             [M1] [M2*] │   │
                                        (réplica)               (Raft consensus)
```

### 7.2 Criterios de Auto-escalado

| Métrica | Umbral Scale-Up | Umbral Scale-Down |
|---------|-----------------|-------------------|
| CPU | > 70% por 5 min | < 30% por 15 min |
| Memoria | > 80% | < 40% |
| Latencia p99 | > 500ms | < 100ms |
| Cola de rebalanceo | > 1000 docs | < 100 docs |

---

## 8. Seguridad

### 8.1 Capas de Seguridad

```
┌────────────────────────────────────────────────────────┐
│                    CAPA EXTERNA                        │
│  - SSL/TLS termination en Load Balancer               │
│  - Rate limiting (100 req/min por IP)                 │
│  - WAF básico (OWASP rules)                           │
└────────────────────────────────────────────────────────┘
                           │
┌────────────────────────────────────────────────────────┐
│                    CAPA API                            │
│  - JWT Authentication                                  │
│  - CORS configurado                                   │
│  - Input validation (Pydantic)                        │
│  - SQL/NoSQL injection prevention                     │
└────────────────────────────────────────────────────────┘
                           │
┌────────────────────────────────────────────────────────┐
│                    CAPA INTERNA                        │
│  - mTLS entre nodos                                   │
│  - Network policies (solo puertos necesarios)         │
│  - Secrets management (HashiCorp Vault)               │
└────────────────────────────────────────────────────────┘
```

---

## 9. Resumen

Esta arquitectura proporciona:

✅ **Alta disponibilidad**: Múltiples slaves, replicación con afinidad  
✅ **Escalabilidad horizontal**: Añadir nodos con rebalanceo automático  
✅ **Búsqueda semántica**: Sin embeddings pre-entrenados (TF-IDF + MinHash + LDA)  
✅ **Tolerancia a fallos**: Re-replicación automática, consenso Raft  
✅ **Separación de responsabilidades**: Frontend React + Backend Python API  
✅ **Observabilidad**: Métricas, logs centralizados, health checks  
✅ **Seguridad**: SSL, JWT, rate limiting, validación  

La estructura de carpetas propuesta permite desarrollo modular, testing aislado y despliegue independiente de cada componente.
