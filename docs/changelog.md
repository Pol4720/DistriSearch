# 📋 Changelog

<div style="padding: 1.5rem; background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); border-radius: 16px; margin-bottom: 2rem;">
  <p style="margin: 0;">Historial completo de versiones y cambios de DistriSearch. Seguimos <a href="https://semver.org/lang/es/">Semantic Versioning</a>.</p>
</div>

---

## [2.0.0] - 2025-12-06 🎉 {#v2.0.0}

<div style="display: flex; gap: 0.5rem; margin: 1rem 0; flex-wrap: wrap;">
  <span style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">🏆 Major Release</span>
  <span style="background: #10b981; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">Master-Slave</span>
  <span style="background: #3b82f6; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">Bully Election</span>
</div>

!!! success "Arquitectura Completamente Rediseñada"
    Esta versión representa una **reescritura completa** del sistema, migrando de una arquitectura centralizada a un modelo **Master-Slave distribuido** con elección dinámica de líder.

### 🏗️ Cambios de Arquitectura

| Componente | v1.x | v2.0 |
|------------|------|------|
| **Base de Datos** | SQLite | MongoDB |
| **Arquitectura** | Centralizada | Master-Slave |
| **Tolerancia a Fallos** | Manual | Algoritmo Bully |
| **Ubicación de Datos** | Por hash/ID | Semántica (embeddings) |
| **Comunicación** | HTTP REST | HTTP + UDP (Heartbeats) |
| **DNS** | N/A | CoreDNS integrado |

### ✨ Nuevas Características

#### 🧠 Sistema de Ubicación Semántica
- Embeddings con `sentence-transformers` (all-MiniLM-L6-v2)
- Vectores de 384 dimensiones
- Similitud coseno para búsqueda y ubicación
- Perfiles semánticos de nodos

#### 👑 Elección Dinámica de Líder
- Implementación del algoritmo **Bully**
- Elección automática en ~10-15 segundos
- Cualquier nodo puede ser Master
- Eliminación del punto único de fallo

#### 💓 Sistema de Heartbeats
```yaml
# Configuración de heartbeats
HEARTBEAT_PORT: 5000      # Puerto UDP
HEARTBEAT_INTERVAL: 5     # Segundos entre beats
HEARTBEAT_TIMEOUT: 15     # Timeout para offline
ELECTION_PORT: 5001       # Puerto para elección
```

#### 🔄 Replicación por Afinidad Semántica
- Réplicas en nodos con contenido similar
- Factor K=2 configurable
- Distribución inteligente basada en embeddings

#### 🌐 CoreDNS Integrado
- Resolución `distrisearch.local`
- Round-robin entre nodos saludables
- Failover automático

#### 📊 Métricas de Confiabilidad
- **MTTR** (Mean Time To Recovery)
- **MTBF** (Mean Time Between Failures)
- Disponibilidad calculada
- Historial de fallos

### 📦 Estructura del Proyecto

```
DistriSearch/
├── core/                    # 🔧 Código compartido
│   ├── config.py           # Configuración unificada
│   ├── models.py           # NodeInfo, ClusterMessage, etc.
│   └── messaging.py        # Serialización UDP
├── cluster/                 # 🔗 Coordinación
│   ├── heartbeat.py        # Sistema de heartbeats
│   ├── election.py         # Algoritmo Bully
│   ├── discovery.py        # Descubrimiento multicast
│   └── naming/             # Naming jerárquico
├── master/                  # 👑 Lógica del Master
│   ├── embedding_service.py
│   ├── location_index.py
│   └── replication_coordinator.py
├── slave/                   # 🖥️ Lógica del Slave
│   ├── api/                # FastAPI routes
│   ├── services/           # Servicios
│   └── scanner/            # Escaneo de archivos
├── backend/                 # 🔌 API REST
├── frontend/               # 🎨 Streamlit UI
└── deploy/                 # 🐳 Docker configs
```

### 🔧 Backend

- ✅ Migración completa a **MongoDB**
- ✅ Endpoints de cluster: `/cluster/nodes`, `/cluster/master`
- ✅ Health checks Kubernetes-ready: `/health/live`, `/health/ready`
- ✅ Rutas de tolerancia a fallos: `/fault-tolerance/metrics`
- ✅ Sistema de naming jerárquico

### 🎨 Frontend

- ✅ Página de **Nodos** con estado del cluster
- ✅ Página de **Estadísticas** con métricas en tiempo real
- ✅ Visualización de Master actual
- ✅ Indicadores de salud por nodo

### 🐳 Deployment

- ✅ `docker-compose.cluster.yml` para 3 nodos
- ✅ CoreDNS preconfigurado
- ✅ MongoDB por nodo
- ✅ **Guía Docker Swarm** para multi-host
- ✅ Redes overlay configuradas

### ✅ Testing

- ✅ Tests unitarios: `test_heartbeat.py`, `test_election.py`
- ✅ Tests de integración: `test_master_slave_integration.py`
- ✅ Tests E2E: `test_cluster_e2e.py`
- ✅ Cobertura >80%

### 📚 Documentación

- ✅ Documentación MkDocs completamente renovada
- ✅ Diagramas Mermaid actualizados
- ✅ Guía de despliegue Docker Swarm
- ✅ API Reference completa
- ✅ FAQ actualizado

### 🐛 Bug Fixes

- 🔧 Eliminación de código legacy SQLite
- 🔧 Limpieza de carpetas obsoletas
- 🔧 Corrección de imports circulares
- 🔧 Fix de timeouts en búsquedas distribuidas

### ⚠️ Breaking Changes

!!! warning "Migración desde v1.x"
    - SQLite ha sido **eliminado completamente**
    - Se requiere MongoDB 6.0+
    - Nuevas variables de entorno requeridas
    - Estructura de carpetas reorganizada

---

## [1.0.0] - 2024-01-15 {#v1.0.0}

### ✨ Características Principales

#### Backend
- ✅ API REST con FastAPI
- ✅ Base de datos SQLite con SQLAlchemy ORM
- ✅ Algoritmo de búsqueda BM25
- ✅ Búsqueda distribuida paralela con `asyncio`
- ✅ Gestión de nodos (registro, heartbeat, health check)
- ✅ Indexación de archivos con metadatos
- ✅ Sistema de descarga directa desde nodos
- ✅ Modo centralizado con replicación
- ✅ Documentación interactiva con Swagger/ReDoc
- ✅ CORS configurable
- ✅ Health checks y monitoreo

#### Frontend
- ✅ Interfaz web con Streamlit 1.32+
- ✅ Diseño moderno con glassmorphism
- ✅ Sistema de páginas auto-descubierto
- ✅ Tema claro/oscuro
- ✅ Componentes reutilizables personalizados
- ✅ Búsqueda con filtros avanzados
- ✅ Gestión de nodos con estadísticas
- ✅ Dashboard de estadísticas con Plotly
- ✅ Modo centralizado con subida de archivos
- ✅ Animaciones y transiciones CSS

#### Agente
- ✅ Escaneo automático de carpetas
- ✅ Indexación local con caché
- ✅ API REST local para búsquedas
- ✅ Registro automático con backend
- ✅ Heartbeat para keep-alive
- ✅ Cálculo de checksum SHA256
- ✅ Extracción de metadatos de archivos
- ✅ Configuración YAML flexible
- ✅ Soporte multi-formato (.pdf, .docx, .xlsx, etc.)

#### Deployment
- ✅ Docker Compose para desarrollo
- ✅ Docker Swarm para producción
- ✅ Kubernetes manifiestos
- ✅ Variables de entorno configurables
- ✅ Healthchecks en contenedores

#### Documentación
- ✅ MkDocs con Material theme
- ✅ Documentación completa en español
- ✅ Guías de instalación multi-plataforma
- ✅ Tutoriales paso a paso
- ✅ Referencia completa de API
- ✅ Casos de uso reales
- ✅ FAQ exhaustivo
- ✅ Diagramas de arquitectura con Mermaid
- ✅ Código de ejemplo
- ✅ Troubleshooting

### 🐛 Bug Fixes

- 🔧 Corrección de timeout en búsquedas largas
- 🔧 Fix de race condition en registro de nodos
- 🔧 Mejora en manejo de nodos offline
- 🔧 Corrección de encoding UTF-8 en nombres de archivo
- 🔧 Fix de memory leak en escaneos largos

### 🚀 Mejoras de Rendimiento

- ⚡ Búsquedas paralelas en todos los nodos
- ⚡ Caché de resultados en frontend
- ⚡ Índices de base de datos optimizados
- ⚡ Pool de conexiones HTTP
- ⚡ Compresión gzip en respuestas

### 📝 Cambios

- 📦 Actualización a Streamlit 1.32.0
- 📦 Actualización a FastAPI 0.109.0
- 📦 Actualización a SQLAlchemy 2.0.25
- 📦 Migración a Pydantic v2

---

## [0.9.0-beta] - 2024-01-05

### ✨ Nuevas Características

- ✅ Modo centralizado con replicación
- ✅ Dashboard de estadísticas
- ✅ Página de gestión de nodos
- ✅ Soporte para metadatos PDF

### 🐛 Bug Fixes

- 🔧 Fix de búsqueda con caracteres especiales
- 🔧 Corrección de timezone en timestamps

### 🚀 Mejoras

- ⚡ Optimización de queries SQL
- ⚡ Reducción de tiempo de escaneo en 40%

---

## [0.8.0-beta] - 2023-12-20

### ✨ Nuevas Características

- ✅ Frontend con Streamlit
- ✅ Sistema de componentes reutilizables
- ✅ Tema personalizable
- ✅ Filtros de búsqueda

### 🐛 Bug Fixes

- 🔧 Fix de conexión WebSocket en Streamlit

---

## [0.7.0-alpha] - 2023-12-10

### ✨ Nuevas Características

- ✅ Algoritmo BM25 para ranking
- ✅ Búsqueda distribuida paralela
- ✅ Health check de nodos

### 🚀 Mejoras

- ⚡ Mejora de velocidad en búsquedas (2x más rápido)

---

## [0.6.0-alpha] - 2023-12-01

### ✨ Nuevas Características

- ✅ Sistema de descarga de archivos
- ✅ Checksum SHA256
- ✅ Detección de duplicados

---

## [0.5.0-alpha] - 2023-11-20

### ✨ Nuevas Características

- ✅ Agente con escaneo automático
- ✅ Configuración YAML
- ✅ Registro automático de nodos

---

## [0.4.0-alpha] - 2023-11-10

### ✨ Nuevas Características

- ✅ API REST con FastAPI
- ✅ Endpoints de búsqueda y registro
- ✅ SQLite como base de datos

---

## [0.3.0-alpha] - 2023-11-01

### ✨ Nuevas Características

- ✅ Modelos SQLAlchemy
- ✅ Búsqueda básica por nombre

---

## [0.2.0-alpha] - 2023-10-20

### ✨ Nuevas Características

- ✅ Arquitectura distribuida definida
- ✅ Protocolo de comunicación

---

## [0.1.0-alpha] - 2023-10-10

### ✨ Primera Versión

- ✅ Concepto inicial
- ✅ Prueba de concepto

---

## 🔮 Próximas Versiones

### [1.1.0] - Q1 2024 (Planeado)

#### Características Planeadas

- 🔄 Replicación automática inteligente
- 🔍 Búsqueda semántica con embeddings
- 📊 Métricas avanzadas con Prometheus
- 🔐 Autenticación OAuth2
- 📱 API GraphQL (complementaria)
- 🌐 Soporte i18n (inglés, español)

#### Mejoras Planeadas

- ⚡ Caché distribuido con Redis
- ⚡ Indexación incremental
- ⚡ Optimización de memoria en agentes

---

### [1.2.0] - Q2 2024 (Planeado)

#### Características Planeadas

- 🤖 Interfaz de chat con LLM
- 🔍 Búsqueda con operadores booleanos (AND, OR, NOT)
- 📋 Filtros avanzados (fecha, tamaño, autor)
- 🎨 Editor de temas en UI
- 📊 Dashboard analytics con ML insights

#### Mejoras Planeadas

- ⚡ Soporte para PostgreSQL/MySQL nativo
- ⚡ Compresión de índices
- ⚡ WebSocket para actualizaciones en tiempo real

---

### [2.0.0] - Q3-Q4 2024 (Planeado)

#### Características Major

- 🚀 **Arquitectura híbrida**: P2P + cliente-servidor
- 🔍 **Búsqueda federada**: Conectar múltiples clusters DistriSearch
- 🤖 **AI-powered search**: Ranking con machine learning
- 📱 **App móvil**: iOS y Android
- 🌐 **Multi-tenancy**: Soporte para múltiples organizaciones
- 🔐 **E2E encryption**: Encriptación total

#### Breaking Changes

- ⚠️ Nueva API v2 (v1 deprecated)
- ⚠️ Migración de configuración YAML a TOML
- ⚠️ Cambios en esquema de base de datos

---

## 📊 Estadísticas del Proyecto

### Líneas de Código

| Componente | Líneas | Archivos |
|------------|--------|----------|
| Backend | ~2,500 | 15 |
| Frontend | ~1,800 | 12 |
| Agente | ~1,200 | 5 |
| Tests | ~800 | 8 |
| Docs | ~5,000 | 30+ |
| **Total** | **~11,300** | **70+** |

### Commits por Versión

- v1.0.0: 250+ commits
- v0.9.0: 80 commits
- v0.8.0: 60 commits
- Versiones anteriores: 110 commits

### Contributors

- **Pol4720** - Desarrollador principal
- **Abel** - Contribuidor
- Comunidad - Bug reports y sugerencias

---

## 🏆 Hitos del Proyecto

- **Oct 2023**: 🎯 Inicio del proyecto
- **Nov 2023**: 🚀 Primera versión funcional (v0.4.0)
- **Dec 2023**: 🎨 Frontend con Streamlit (v0.8.0)
- **Jan 2024**: 🎉 **Lanzamiento v1.0.0**
- **Q1 2024**: 🔮 Búsqueda semántica (planeado)
- **Q4 2024**: 🚀 **v2.0.0 con AI** (planeado)

---

## 📝 Formato de Versiones

Seguimos [Semantic Versioning](https://semver.org/):

```
MAJOR.MINOR.PATCH

Ejemplo: 1.2.3
```

- **MAJOR**: Cambios incompatibles de API
- **MINOR**: Nuevas funcionalidades compatibles
- **PATCH**: Bug fixes compatibles

### Sufijos

- `alpha`: Versión muy temprana, inestable
- `beta`: Versión de prueba, casi estable
- `rc`: Release Candidate, candidata a producción
- Sin sufijo: Versión estable de producción

---

## 🔗 Enlaces

| Recurso | URL |
|---------|-----|
| **Repositorio** | [github.com/Pol4720/DS-Project](https://github.com/Pol4720/DS-Project) |
| **Issues** | [GitHub Issues](https://github.com/Pol4720/DS-Project/issues) |
| **Releases** | [GitHub Releases](https://github.com/Pol4720/DS-Project/releases) |
| **Documentación** | [docs.distrisearch.com](https://docs.distrisearch.com) |

---

## 📜 Licencia

DistriSearch está licenciado bajo MIT License.

---

[:octicons-arrow-left-24: Volver](index.md){ .md-button }
[:octicons-mark-github-24: Ver Releases](https://github.com/Pol4720/DS-Project/releases){ .md-button .md-button--primary }
