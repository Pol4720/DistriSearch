# Arquitectura del Sistema

Esta sección describe en detalle la arquitectura técnica de DistriSearch, incluyendo componentes, flujos de datos y decisiones de diseño.

---

## 🏗️ Arquitectura General

```mermaid
graph TB
    subgraph "Capa de Presentación"
        UI[Streamlit Frontend]
    end
    
    subgraph "Capa de Aplicación"
        API[FastAPI Backend]
        AUTH[Autenticación]
        SEARCH[Search Service]
        INDEX[Index Service]
        NODE[Node Service]
        REP[Replication Service]
    end
    
    subgraph "Capa de Datos"
        DB[(SQLite DB)]
        CACHE[(Cache)]
    end
    
    subgraph "Nodos Distribuidos"
        A1[Agente 1]
        A2[Agente 2]
        AN[Agente N]
    end
    
    UI --> API
    API --> AUTH
    API --> SEARCH
    API --> INDEX
    API --> NODE
    API --> REP
    
    SEARCH --> DB
    INDEX --> DB
    NODE --> DB
    REP --> DB
    
    SEARCH -.->|Consulta| A1
    SEARCH -.->|Consulta| A2
    SEARCH -.->|Consulta| AN
    
    INDEX -.->|Indexación| A1
    INDEX -.->|Indexación| A2
    INDEX -.->|Indexación| AN
    
    style UI fill:#667eea
    style API fill:#764ba2
    style DB fill:#10b981
    style A1 fill:#f59e0b
    style A2 fill:#f59e0b
    style AN fill:#f59e0b
```

---

## 📦 Componentes Principales

### 1. Frontend (Streamlit)

**Responsabilidades**:

- Interfaz de usuario web
- Visualización de resultados
- Gestión de nodos
- Configuración del sistema

**Stack Tecnológico**:

```yaml
- Framework: Streamlit 1.32+
- Visualización: Plotly 5.18+
- HTTP Client: Requests
- Componentes: streamlit-extras, streamlit-option-menu
```

**Estructura**:

```
frontend/
├── app.py              # Página principal
├── pages/              # Sistema de páginas
│   ├── 01_🔍_Buscar.py
│   ├── 02_🌐_Nodos.py
│   ├── 03_🏢_Central.py
│   └── 04_📊_Estadísticas.py
├── components/         # Componentes reutilizables
│   ├── cards.py
│   └── styles.py
└── utils/             # Utilidades
    ├── api_client.py
    └── helpers.py
```

### 2. Backend (FastAPI)

**Responsabilidades**:

- API REST centralizada
- Coordinación de búsquedas
- Gestión de nodos
- Replicación de datos
- Modo centralizado

**Stack Tecnológico**:

```yaml
- Framework: FastAPI 0.109+
- ORM: SQLAlchemy 2.0+
- Validación: Pydantic 2.5+
- Base de Datos: SQLite
- ASGI Server: Uvicorn
```

**Estructura**:

```
backend/
├── main.py            # Punto de entrada
├── database.py        # Configuración BD
├── models.py          # Modelos SQLAlchemy
├── security.py        # Autenticación
├── routes/            # Endpoints
│   ├── search.py
│   ├── register.py
│   ├── download.py
│   └── central.py
├── services/          # Lógica de negocio
│   ├── index_service.py
│   ├── node_service.py
│   ├── central_service.py
│   └── replication_service.py
└── tests/            # Tests unitarios
```

### 3. Agente (Node Service)

**Responsabilidades**:

- Escaneo de carpetas locales
- Indexación de archivos
- API REST local
- Sincronización con backend

**Stack Tecnológico**:

```yaml
- Framework: FastAPI
- Scanner: watchdog (opcional)
- Hash: hashlib (SHA256)
- Threading: concurrent.futures
```

**Estructura**:

```
agent/
├── agent.py          # Orquestador principal
├── server.py         # API REST
├── scanner.py        # Escaneo de archivos
├── uploader.py       # Sincronización
└── config.yaml       # Configuración
```

---

## 🔄 Flujos de Datos

### Flujo de Búsqueda Distribuida

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant F as Frontend
    participant B as Backend
    participant DB as Database
    participant N1 as Nodo 1
    participant N2 as Nodo 2
    
    U->>F: Ingresa "proyecto.pdf"
    F->>B: POST /search/?q=proyecto.pdf
    B->>DB: Obtiene nodos activos
    DB-->>B: [node1, node2]
    
    par Búsqueda Paralela
        B->>N1: GET /local/search?q=proyecto.pdf
        and
        B->>N2: GET /local/search?q=proyecto.pdf
    end
    
    N1-->>B: [{file1, score: 8.5}]
    N2-->>B: [{file2, score: 7.2}]
    
    B->>B: Agrega resultados
    B->>B: Aplica BM25 global
    B->>B: Ordena por score
    
    B-->>F: Resultados rankeados
    F->>F: Renderiza cards
    F-->>U: Muestra resultados
```

### Flujo de Indexación (Agente)

```mermaid
sequenceDiagram
    autonumber
    participant A as Agente
    participant FS as Filesystem
    participant DB as Local DB
    participant B as Backend
    
    loop Escaneo Periódico
        A->>FS: Escanear carpeta
        FS-->>A: Lista de archivos
        
        loop Por cada archivo
            A->>A: Calcular SHA256
            A->>A: Extraer metadatos
            A->>DB: Guardar en índice local
        end
        
        A->>B: POST /register/files
        B->>B: Actualiza índice central
        B-->>A: Confirmación
        
        A->>A: Espera intervalo
    end
```

### Flujo de Descarga

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant F as Frontend
    participant B as Backend
    participant N as Nodo
    
    U->>F: Click "Descargar"
    F->>B: POST /download/ {file_id}
    B->>B: Consulta BD por file_id
    B->>B: Obtiene nodo propietario
    
    alt Nodo Online
        B->>N: Verifica disponibilidad
        N-->>B: OK
        B-->>F: URL directa al nodo
        F-->>U: Redirige a nodo
        U->>N: GET /download/{file_id}
        N-->>U: Archivo descargado
    else Nodo Offline
        B->>B: Busca en central storage
        B-->>F: URL al backend
        F-->>U: Redirige al backend
        U->>B: GET /download/file/{file_id}
        B-->>U: Archivo desde central
    end
```

---

## 🗄️ Modelo de Datos

### Diagrama ER

```mermaid
erDiagram
    NODE ||--o{ FILE : tiene
    NODE {
        string node_id PK
        string name
        string ip_address
        int port
        enum status
        int shared_files_count
        datetime last_seen
    }
    
    FILE {
        string file_id PK
        string node_id FK
        string name
        string path
        int size
        string file_type
        string checksum
        datetime indexed_at
        datetime modified_at
    }
    
    FILE ||--o{ METADATA : tiene
    METADATA {
        int id PK
        string file_id FK
        string key
        string value
    }
```

### Modelos SQLAlchemy

=== "Node Model"

    ```python
    class Node(Base):
        __tablename__ = "nodes"
        
        node_id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        ip_address = Column(String, nullable=False)
        port = Column(Integer, nullable=False)
        status = Column(Enum(NodeStatus), default=NodeStatus.OFFLINE)
        shared_files_count = Column(Integer, default=0)
        last_seen = Column(DateTime, default=datetime.utcnow)
        
        # Relación con archivos
        files = relationship("File", back_populates="node", cascade="all, delete-orphan")
    ```

=== "File Model"

    ```python
    class File(Base):
        __tablename__ = "files"
        
        file_id = Column(String, primary_key=True)
        node_id = Column(String, ForeignKey("nodes.node_id"))
        name = Column(String, nullable=False, index=True)
        path = Column(String)
        size = Column(Integer)
        file_type = Column(Enum(FileType))
        checksum = Column(String)
        indexed_at = Column(DateTime, default=datetime.utcnow)
        modified_at = Column(DateTime)
        
        # Relación con nodo
        node = relationship("Node", back_populates="files")
        
        # Índice para búsquedas
        __table_args__ = (
            Index('idx_name_type', 'name', 'file_type'),
        )
    ```

---

## 🔌 API Design

### Principios REST

DistriSearch sigue los principios REST:

| Principio | Implementación |
|-----------|----------------|
| **Stateless** | No se mantiene estado de sesión |
| **Cacheable** | Headers Cache-Control apropiados |
| **Uniform Interface** | Uso consistente de HTTP verbs |
| **Layered System** | Arquitectura en capas clara |

### Versionado de API

```http
# Versión en URL (futuro)
GET /api/v1/search/
GET /api/v2/search/

# Versión en header (actual)
X-API-Version: 1.0
```

### Códigos de Estado HTTP

| Código | Uso | Ejemplo |
|--------|-----|---------|
| `200` | Success | Búsqueda exitosa |
| `201` | Created | Nodo registrado |
| `400` | Bad Request | Parámetros inválidos |
| `401` | Unauthorized | API key inválida |
| `404` | Not Found | Archivo no encontrado |
| `500` | Server Error | Error interno |
| `503` | Service Unavailable | Nodo offline |

---

## 🔐 Seguridad en Capas

```mermaid
graph TD
    A[Request] --> B{CORS Check}
    B -->|Fail| C[403 Forbidden]
    B -->|Pass| D{Auth Check}
    D -->|Fail| E[401 Unauthorized]
    D -->|Pass| F{Rate Limit}
    F -->|Exceeded| G[429 Too Many Requests]
    F -->|OK| H{Validation}
    H -->|Fail| I[400 Bad Request]
    H -->|Pass| J[Process Request]
    J --> K[Response]
    
    style A fill:#667eea
    style K fill:#10b981
    style C fill:#ef4444
    style E fill:#ef4444
    style G fill:#f59e0b
    style I fill:#ef4444
```

### Capas de Seguridad

1. **CORS**: Valida origen de peticiones
2. **Autenticación**: Verifica API key (opcional)
3. **Rate Limiting**: Previene abuso
4. **Validación**: Pydantic valida datos
5. **Sanitización**: Limpia inputs peligrosos

---

## 📡 Comunicación Entre Componentes

### Protocolo HTTP/REST

Toda la comunicación usa HTTP/REST:

```python
# Frontend → Backend
response = requests.post(
    "http://backend:8000/search/",
    json={"q": "documento"},
    headers={"X-API-KEY": api_key}
)

# Backend → Agente
response = requests.get(
    f"http://{node.ip_address}:{node.port}/local/search",
    params={"q": "documento"}
)
```

### Formato de Mensajes

Todos los mensajes usan **JSON**:

```json
{
  "status": "success",
  "data": {
    "files": [...],
    "total": 10,
    "query_time_ms": 150
  },
  "error": null
}
```

---

## ⚡ Optimizaciones de Rendimiento

### 1. Índices de Base de Datos

```sql
-- Índice en file_id para búsquedas rápidas
CREATE INDEX idx_file_id ON files(file_id);

-- Índice compuesto para filtros
CREATE INDEX idx_name_type ON files(name, file_type);

-- Índice en checksum para duplicados
CREATE INDEX idx_checksum ON files(checksum);
```

### 2. Búsquedas Asíncronas

```python
import asyncio
import aiohttp

async def search_node(session, node, query):
    url = f"http://{node.ip}:{node.port}/local/search"
    async with session.get(url, params={"q": query}) as response:
        return await response.json()

async def search_all_nodes(nodes, query):
    async with aiohttp.ClientSession() as session:
        tasks = [search_node(session, node, query) for node in nodes]
        return await asyncio.gather(*tasks)
```

### 3. Cache de Resultados

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_node_info(node_id: str):
    return db.query(Node).filter_by(node_id=node_id).first()
```

### 4. Paginación

```python
# Limitar resultados por defecto
@router.get("/search/")
async def search(
    q: str,
    max_results: int = Query(default=50, le=200)
):
    # ...
```

---

## 🧩 Patrones de Diseño Utilizados

| Patrón | Aplicación | Beneficio |
|--------|------------|-----------|
| **Repository** | `services/` | Abstracción de datos |
| **Singleton** | API Client | Única instancia |
| **Factory** | File scanners | Creación flexible |
| **Observer** | File watcher | Eventos de cambio |
| **Strategy** | Search algorithms | Algoritmos intercambiables |

---

## 🔮 Escalabilidad

### Escalado Horizontal

```mermaid
graph LR
    LB[Load Balancer]
    LB --> B1[Backend 1]
    LB --> B2[Backend 2]
    LB --> B3[Backend 3]
    
    B1 --> DB[(Shared DB)]
    B2 --> DB
    B3 --> DB
    
    style LB fill:#667eea
    style DB fill:#10b981
```

### Escalado de Nodos

Sin límite teórico de nodos:

- ✅ Cada nodo es independiente
- ✅ Búsqueda en paralelo
- ✅ Sin cuello de botella centralizado

---

[:octicons-arrow-left-24: Volver a Características](caracteristicas.md){ .md-button }
[:octicons-arrow-right-24: Comenzar Instalación](getting-started/instalacion.md){ .md-button .md-button--primary }
