# Configuración

Personaliza DistriSearch para adaptarlo a tus necesidades específicas.

---

## 📋 Archivos de Configuración

DistriSearch utiliza diferentes archivos de configuración según el componente:

| Componente | Archivo | Ubicación |
|------------|---------|-----------|
| **Backend** | `config.py` | `backend/config.py` |
| **Frontend** | `config.toml` | `frontend/.streamlit/config.toml` |
| **Agente** | `config.yaml` | `agent/config.yaml` |
| **Docker** | `.env` | `deploy/.env` |

---

## ⚙️ Configuración del Backend

### Archivo: `backend/config.py`

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Aplicación
    app_name: str = "DistriSearch"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Base de Datos
    database_url: str = "sqlite:///./distrisearch.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Seguridad
    secret_key: str = "your-secret-key-change-in-production"
    api_key_enabled: bool = False
    api_key: str = ""
    
    # CORS
    cors_origins: list = ["http://localhost:8501", "*"]
    cors_allow_credentials: bool = True
    
    # Búsqueda
    max_results_per_query: int = 100
    search_timeout: int = 30  # segundos
    parallel_searches: bool = True
    max_parallel_nodes: int = 10
    
    # BM25 Parameters
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    
    # Modo Central
    central_mode: bool = False
    central_storage_path: str = "./central_storage"
    replication_enabled: bool = False
    replication_strategy: str = "on_demand"  # on_demand, automatic
    
    # Health Check
    health_check_interval: int = 60  # segundos
    node_timeout: int = 5  # segundos
    
    # Logging
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_file: str = "logs/backend.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### Variables de Entorno

Crea un archivo `.env` en la raíz del backend:

```bash
# .env
APP_NAME=DistriSearch
DEBUG=false

# Base de Datos
DATABASE_URL=sqlite:///./distrisearch.db

# Seguridad
SECRET_KEY=supersecretkey123456789
API_KEY_ENABLED=true
API_KEY=my-api-key-12345

# CORS
CORS_ORIGINS=["http://localhost:8501","http://frontend:8501"]

# Búsqueda
MAX_RESULTS_PER_QUERY=50
SEARCH_TIMEOUT=20
PARALLEL_SEARCHES=true

# BM25
BM25_K1=1.5
BM25_B=0.75

# Modo Central
CENTRAL_MODE=false
REPLICATION_ENABLED=false

# Logging
LOG_LEVEL=INFO
```

### Configuración Avanzada

=== "Alta Disponibilidad"

    ```python
    # config.py para HA
    workers: int = 8
    db_pool_size: int = 20
    db_max_overflow: int = 40
    max_parallel_nodes: int = 50
    health_check_interval: int = 30
    ```

=== "Desarrollo"

    ```python
    # config.py para dev
    debug: bool = True
    workers: int = 1
    log_level: str = "DEBUG"
    cors_origins: list = ["*"]
    ```

=== "Producción Segura"

    ```python
    # config.py para producción
    debug: bool = False
    api_key_enabled: bool = True
    cors_origins: list = ["https://app.example.com"]
    secret_key: str = os.getenv("SECRET_KEY")
    log_level: str = "WARNING"
    ```

---

## 🎨 Configuración del Frontend

### Archivo: `frontend/.streamlit/config.toml`

```toml
[theme]
primaryColor = "#667eea"
backgroundColor = "#0f172a"
secondaryBackgroundColor = "#1e293b"
textColor = "#f1f5f9"
font = "sans serif"

[server]
port = 8501
headless = true
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
serverAddress = "localhost"
serverPort = 8501

[runner]
magicEnabled = true
installTracer = false
fixMatplotlib = true
postScriptGC = true

[client]
showErrorDetails = true
toolbarMode = "auto"

[logger]
level = "info"
messageFormat = "%(asctime)s %(message)s"

[deprecation]
showPyplotGlobalUse = false
```

### Personalización del Tema

=== "Tema Oscuro (Predeterminado)"

    ```toml
    [theme]
    primaryColor = "#667eea"
    backgroundColor = "#0f172a"
    secondaryBackgroundColor = "#1e293b"
    textColor = "#f1f5f9"
    ```

=== "Tema Claro"

    ```toml
    [theme]
    primaryColor = "#667eea"
    backgroundColor = "#ffffff"
    secondaryBackgroundColor = "#f8fafc"
    textColor = "#0f172a"
    ```

=== "Tema Personalizado"

    ```toml
    [theme]
    primaryColor = "#10b981"  # Verde
    backgroundColor = "#1a1a2e"  # Azul oscuro
    secondaryBackgroundColor = "#16213e"
    textColor = "#eaeaea"
    font = "monospace"
    ```

### Variables de Aplicación

Crea `frontend/config.py`:

```python
# frontend/config.py
import os

class FrontendConfig:
    # Backend API
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
    API_KEY = os.getenv("API_KEY", "")
    
    # UI Settings
    PAGE_TITLE = "DistriSearch"
    PAGE_ICON = "🔍"
    LAYOUT = "wide"
    INITIAL_SIDEBAR_STATE = "expanded"
    
    # Search Settings
    DEFAULT_MAX_RESULTS = 50
    RESULTS_PER_PAGE = 10
    SHOW_THUMBNAILS = True
    SHOW_PREVIEWS = True
    
    # Cache Settings
    CACHE_TTL = 300  # 5 minutos
    ENABLE_CACHING = True
    
    # Performance
    PARALLEL_REQUESTS = True
    REQUEST_TIMEOUT = 30
    
    # Features
    ENABLE_ADVANCED_FILTERS = True
    ENABLE_STATISTICS = True
    ENABLE_NODE_MANAGEMENT = True
    ENABLE_CENTRAL_MODE = False

config = FrontendConfig()
```

---

## 🤖 Configuración del Agente

### Archivo: `agent/config.yaml`

```yaml
# agent/config.yaml

# Identificación del Nodo
agent:
  node_id: "node-001"  # ID único del nodo
  name: "Oficina Principal"  # Nombre descriptivo
  shared_folder: "/path/to/shared/folder"  # Carpeta a indexar
  port: 5001  # Puerto del servidor local

# Conexión con Backend
backend:
  url: "http://localhost:8000"
  register_on_start: true
  registration_retry_interval: 60  # segundos
  heartbeat_interval: 30  # segundos

# Configuración de Escaneo
scan:
  interval: 300  # Escaneo cada 5 minutos
  on_startup: true  # Escanear al iniciar
  
  # Tipos de archivo a indexar
  file_types:
    - ".pdf"
    - ".doc"
    - ".docx"
    - ".txt"
    - ".md"
    - ".xlsx"
    - ".xls"
    - ".pptx"
    - ".csv"
  
  # Patrones a ignorar (regex)
  ignore_patterns:
    - "^\\."  # Archivos ocultos
    - "~$"    # Archivos temporales
    - "\\.tmp$"
    - "\\.bak$"
  
  # Carpetas a ignorar
  ignore_folders:
    - ".git"
    - "node_modules"
    - "__pycache__"
    - ".vscode"
    - "venv"
  
  # Límites
  max_file_size: 104857600  # 100 MB
  max_files_per_scan: 10000
  
  # Checksum
  calculate_checksum: true
  checksum_algorithm: "sha256"

# Extracción de Metadatos
metadata:
  extract: true
  
  # PDF
  pdf_metadata:
    - title
    - author
    - subject
    - keywords
    - creator
    - producer
    - creation_date
    - modification_date
  
  # Documentos Office
  office_metadata:
    - title
    - author
    - subject
    - keywords
    - last_modified_by
    - created
    - modified
  
  # Full text search (requiere más recursos)
  full_text_indexing: false
  max_text_size: 1048576  # 1 MB

# Servidor Local
server:
  host: "0.0.0.0"
  workers: 2
  log_level: "INFO"
  
  # Límites de tasa
  rate_limit:
    enabled: true
    requests_per_minute: 100

# Caché Local
cache:
  enabled: true
  ttl: 3600  # 1 hora
  max_size: 1000  # entradas

# Monitoring
monitoring:
  enabled: true
  metrics_port: 9090
  prometheus_export: false

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "logs/agent.log"
  max_size: 10485760  # 10 MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Seguridad
security:
  require_api_key: false
  api_key: ""
  
  # TLS/SSL
  enable_tls: false
  cert_file: ""
  key_file: ""
```

### Configuraciones por Tipo de Nodo

=== "Nodo Ligero (Laptop)"

    ```yaml
    scan:
      interval: 600  # 10 minutos
      max_file_size: 52428800  # 50 MB
      max_files_per_scan: 5000
    
    server:
      workers: 1
    
    cache:
      max_size: 500
    
    metadata:
      full_text_indexing: false
    ```

=== "Nodo Estándar (Desktop)"

    ```yaml
    scan:
      interval: 300  # 5 minutos
      max_file_size: 104857600  # 100 MB
      max_files_per_scan: 10000
    
    server:
      workers: 2
    
    cache:
      max_size: 1000
    
    metadata:
      full_text_indexing: false
    ```

=== "Nodo Potente (Server)"

    ```yaml
    scan:
      interval: 120  # 2 minutos
      max_file_size: 524288000  # 500 MB
      max_files_per_scan: 50000
    
    server:
      workers: 4
    
    cache:
      max_size: 5000
    
    metadata:
      full_text_indexing: true
    ```

---

## 🐳 Configuración Docker

### Archivo: `deploy/.env`

```bash
# Backend
BACKEND_IMAGE=distrisearch/backend:latest
BACKEND_PORT=8000
BACKEND_WORKERS=4

# Frontend
FRONTEND_IMAGE=distrisearch/frontend:latest
FRONTEND_PORT=8501

# Agente 1
AGENT1_IMAGE=distrisearch/agent:latest
AGENT1_PORT=5001
AGENT1_NODE_ID=agent-1
AGENT1_NAME=Nodo 1
AGENT1_SHARED_FOLDER=./shared_folders/agent1

# Agente 2
AGENT2_PORT=5002
AGENT2_NODE_ID=agent-2
AGENT2_NAME=Nodo 2
AGENT2_SHARED_FOLDER=./shared_folders/agent2

# Red
NETWORK_NAME=distrisearch-net

# Volúmenes
BACKEND_DB_VOLUME=backend-db
AGENT1_VOLUME=agent1-data
AGENT2_VOLUME=agent2-data

# Logging
LOG_LEVEL=INFO
```

### Archivo: `deploy/docker-compose.yml`

```yaml
version: "3.8"

services:
  backend:
    image: ${BACKEND_IMAGE}
    container_name: distrisearch-backend
    ports:
      - "${BACKEND_PORT}:8000"
    environment:
      - WORKERS=${BACKEND_WORKERS}
      - LOG_LEVEL=${LOG_LEVEL}
    volumes:
      - ${BACKEND_DB_VOLUME}:/app/data
    networks:
      - distrisearch-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    image: ${FRONTEND_IMAGE}
    container_name: distrisearch-frontend
    ports:
      - "${FRONTEND_PORT}:8501"
    environment:
      - BACKEND_URL=http://backend:8000
    networks:
      - distrisearch-net
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  agent1:
    image: ${AGENT1_IMAGE}
    container_name: distrisearch-agent1
    ports:
      - "${AGENT1_PORT}:5001"
    environment:
      - NODE_ID=${AGENT1_NODE_ID}
      - NODE_NAME=${AGENT1_NAME}
      - BACKEND_URL=http://backend:8000
      - SHARED_FOLDER=/app/shared
    volumes:
      - ${AGENT1_SHARED_FOLDER}:/app/shared:ro
      - ${AGENT1_VOLUME}:/app/data
    networks:
      - distrisearch-net
    depends_on:
      - backend
    restart: unless-stopped

  agent2:
    image: ${AGENT1_IMAGE}
    container_name: distrisearch-agent2
    ports:
      - "${AGENT2_PORT}:5001"
    environment:
      - NODE_ID=${AGENT2_NODE_ID}
      - NODE_NAME=${AGENT2_NAME}
      - BACKEND_URL=http://backend:8000
      - SHARED_FOLDER=/app/shared
    volumes:
      - ${AGENT2_SHARED_FOLDER}:/app/shared:ro
      - ${AGENT2_VOLUME}:/app/data
    networks:
      - distrisearch-net
    depends_on:
      - backend
    restart: unless-stopped

networks:
  distrisearch-net:
    driver: bridge

volumes:
  backend-db:
  agent1-data:
  agent2-data:
```

---

## 🔐 Configuración de Seguridad

### Habilitar API Key

1. **Backend**: Editar `.env`
   ```bash
   API_KEY_ENABLED=true
   API_KEY=your-super-secret-key-here
   ```

2. **Frontend**: Editar `config.py`
   ```python
   API_KEY = "your-super-secret-key-here"
   ```

3. **Agente**: Editar `config.yaml`
   ```yaml
   security:
     require_api_key: true
     api_key: "your-super-secret-key-here"
   ```

### Habilitar HTTPS

1. Generar certificado:
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   ```

2. Configurar backend:
   ```python
   # main.py
   import uvicorn
   
   if __name__ == "__main__":
       uvicorn.run(
           "main:app",
           host="0.0.0.0",
           port=8443,
           ssl_keyfile="./key.pem",
           ssl_certfile="./cert.pem"
       )
   ```

3. Actualizar URLs:
   ```yaml
   # agent/config.yaml
   backend:
     url: "https://backend.example.com:8443"
   ```

---

## 📊 Configuración de Logging

### Backend Logging

```python
# backend/logging_config.py
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_level="INFO", log_file="logs/backend.log"):
    # Crear directorio de logs
    os.makedirs("logs", exist_ok=True)
    
    # Configurar handler de archivo
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    
    # Configurar handler de consola
    console_handler = logging.StreamHandler()
    
    # Formato
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Configurar logger raíz
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

### Niveles de Log Recomendados

| Entorno | Backend | Frontend | Agente |
|---------|---------|----------|--------|
| **Desarrollo** | DEBUG | DEBUG | DEBUG |
| **Testing** | INFO | INFO | INFO |
| **Producción** | WARNING | WARNING | INFO |

---

## 🎯 Casos de Configuración Comunes

### Configuración Mínima (Testing)

```yaml
# Agente minimalista
agent:
  node_id: "test-node"
  shared_folder: "./test_files"
  port: 5001

backend:
  url: "http://localhost:8000"

scan:
  interval: 600
  file_types: [".txt"]
```

### Configuración Empresarial

```yaml
# Agente producción
agent:
  node_id: "prod-office-bcn"
  name: "Oficina Barcelona - Producción"
  shared_folder: "/mnt/shared/documents"
  port: 5001

backend:
  url: "https://distrisearch.company.com"
  heartbeat_interval: 30

scan:
  interval: 180  # 3 minutos
  file_types: [".pdf", ".docx", ".xlsx"]
  max_file_size: 524288000  # 500 MB

security:
  require_api_key: true
  api_key: "${API_KEY_FROM_ENV}"
  enable_tls: true

monitoring:
  enabled: true
  prometheus_export: true
```

---

[:octicons-arrow-left-24: Volver a Instalación](instalacion.md){ .md-button }
[:octicons-arrow-right-24: Ver API](../api/index.md){ .md-button .md-button--primary }
