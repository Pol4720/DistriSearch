# Queries Optimizadas para Rellenar la Guía de Estudio

## Instrucciones de Uso
Adjuntar la carpeta `DistriSearch` completa al agente y ejecutar cada query por carpeta.

---

## 📁 00_Introduccion



## 📁 01_Arquitectura_General


---

## 📁 02_Vectorizacion_Busqueda



---

## 📁 03_Particionamiento


---

## 📁 04_Rebalanceo

```

```

---

## 📁 05_Replicacion

```
Analyze DistriSearch's replication strategy and fill 05_Replicacion folder with Spanish content:

**README.md**: Overview of semantic affinity-based replication

**01_Afinidad_Semantica.md**:
- Why semantic affinity matters for replication
- AffinityBasedReplicator class concept
- Replicas placed on nodes containing "neighbor" documents
- Benefits: faster related searches, better cache locality
- Reference docs/Soluciones de ubicacion y balanceo.md

**02_Grafo_Similaridad.md**:
- Similarity graph concept: documents as nodes, similarity as edges
- Building the graph from document vectors
- Using the graph for replica placement decisions
- Example: ventas_q1.xlsx → ventas_q2.xlsx → ingresos_2024.csv
- How graph structure influences fault tolerance

**03_Factor_Replicacion.md**:
- Replication factor configuration (default: 2)
- Trade-offs: storage cost vs fault tolerance
- Ensuring fault tolerance: replicas in different failure zones
- _ensures_fault_tolerance() logic: different racks/zones
- Completing with least-loaded nodes if affinity nodes unavailable

Include the replication assignment algorithm with code references.
```

---

## 📁 06_Tolerancia_Fallos

```
Analyze DistriSearch's fault tolerance mechanisms and fill 06_Tolerancia_Fallos folder with Spanish content:

**README.md**: Overview of failure detection and recovery

**01_Deteccion_Fallos.md**:
- Health check mechanisms in Docker Swarm
- Application-level health endpoints (/health)
- Failure detection timing and thresholds
- Types of failures: node crash, network partition, service failure
- Reference docker/ healthcheck configurations

**02_Re_Replicacion.md**:
- FailureRecoveryService class concept
- on_node_failure() process:
  1. Identify affected documents
  2. Classify by urgency: critical (only replica) vs degraded (below minimum)
  3. Recover critical from backup
  4. Re-replicate degraded maintaining semantic affinity
  5. Update VP-Tree without failed node
- Priority: critical documents first
- Reference implementation details

**03_Recuperacion_Nodos.md**:
- Node recovery process when failed node returns
- State synchronization with cluster
- Gossip protocol for eventual consistency
- Reintegration into VP-Tree partitioning
- Document redistribution after recovery
- Reference GUIA_DESPLIEGUE.md troubleshooting section
```

---

## 📁 07_Consenso_Raft

```
Analyze DistriSearch's Raft consensus implementation and fill 07_Consenso_Raft folder with Spanish content:

**README.md**: Overview of Raft consensus for distributed coordination

**01_Eleccion_Lider.md**:
- Raft leader election algorithm explained
- Terms, votes, and election timeouts
- How DistriSearch uses Raft for Master election
- Handling split-brain scenarios
- Reference backend/app/distributed/ Raft implementation
- RAFT_ENABLED environment variable from docker configurations

**02_Replicacion_Log.md**:
- Raft log replication mechanism
- Append entries and commit index
- How operations are replicated across nodes
- Consistency guarantees provided
- Log compaction and snapshots

**03_SQLite_Replicado.md**:
- SQLite with Raft replication for user data
- Why SQLite: lightweight, local, works during partitions
- What's stored: users, nodes, partitions metadata
- Replication flow: write → leader → replicate → commit
- Benefits for authentication during network partitions
- Reference GUIA_DESPLIEGUE.md architecture section

Include state machine diagrams for Raft states (Follower, Candidate, Leader).
```

---

## 📁 08_Docker_Swarm

```
Analyze DistriSearch's Docker Swarm deployment and fill 08_Docker_Swarm folder with Spanish content:

**README.md**: Overview of Docker Swarm orchestration for DistriSearch

**01_Conceptos_Swarm.md**:
- What is Docker Swarm and why chosen over Kubernetes
- Manager nodes vs Worker nodes
- Swarm benefits for DistriSearch: DNS, routing mesh, rolling updates, self-healing, secrets
- Reference docs/ARQUITECTURA_DISTRIBUIDA.md section 2

**02_Overlay_Network.md**:
- Overlay networks explained: communication across physical hosts
- distrisearch-network configuration (10.0.10.0/24)
- How containers on different hosts communicate
- Network isolation and security
- Reference docker/docker-compose.swarm.yml or docker-compose.distributed.yml

**03_Servicios_Replicas.md**:
- Docker services vs containers
- Replica configuration for slaves (replicas: N)
- Endpoint modes: VIP vs DNSRR
- Placement constraints (e.g., master on manager nodes)
- Resource limits and reservations
- Reference actual docker-compose configurations

**04_Rolling_Updates.md**:
- Zero-downtime deployment strategy
- update_config: parallelism, delay, failure_action
- How DistriSearch handles updates without service interruption
- Rollback mechanisms

Include docker-compose.yml excerpts with explanations.
```

---

## 📁 09_DNS_Descubrimiento

```
Analyze DistriSearch's DNS and service discovery and fill 09_DNS_Descubrimiento folder with Spanish content:

**README.md**: Overview of service discovery mechanisms

**01_DNS_Interno_Docker.md**:
- Docker's internal DNS server (127.0.0.11)
- Service name resolution: "master" → IP address
- VIP resolution vs tasks.servicename for all replicas
- Container name resolution
- Reference docs/ARQUITECTURA_DISTRIBUIDA.md section 3

**02_CoreDNS_Backup.md**:
- Why backup DNS is needed (Docker DNS failures)
- CoreDNS configuration from docker/coredns/
- Corefile zones: distrisearch.local, services.local
- Fallback chain: Docker DNS → CoreDNS → Consul → local cache
- Zone file configuration from docker/coredns/zones/

**03_Service_Discovery.md**:
- DNS Resolver Client implementation concept
- Multi-level fallback strategy
- How slaves discover master service
- How services discover MongoDB
- DNS_BACKUP_ENABLED, DNS_BACKUP_HOST environment variables
- Reference docker/dns-sync/ for zone synchronization

Include DNS resolution flow diagrams and Corefile excerpts.
```

---

## 📁 10_Load_Balancer

```
Analyze DistriSearch's load balancing and fill 10_Load_Balancer folder with Spanish content:

**README.md**: Overview of load balancing strategy

**01_Nginx_Configuracion.md**:
- Nginx as primary load balancer
- Configuration from docker/load-balancer/nginx.conf
- Upstream configuration for backend services
- Location blocks and proxy settings
- Reference docker/load-balancer/ directory

**02_Routing_Mesh.md**:
- Docker Swarm's ingress routing mesh
- How external requests reach any node
- Internal load balancing via VIP
- Published ports and routing
- Combination with Nginx for fine-grained control

**03_Health_Checks.md**:
- Health check configuration in nginx
- Docker healthcheck directives
- Automatic removal of unhealthy backends
- Health check intervals and thresholds
- /health endpoint implementation in backend

**04_SSL_Termination.md**:
- SSL/TLS termination at load balancer
- Certificate configuration
- HTTPS_ENABLED environment variable
- Self-signed certificates for development (generate-ssl.sh)
- Reference docker/slave/generate-ssl.sh and nginx-https.conf

Include nginx.conf excerpts with detailed explanations.
```

---

## 📁 11_Almacenamiento

```
Analyze DistriSearch's storage architecture and fill 11_Almacenamiento folder with Spanish content:

**README.md**: Overview of multi-tier storage strategy

**01_MongoDB_Local.md**:
- MongoDB per slave node (not centralized)
- Why local: partition tolerance, no single point of failure
- What's stored: documents, vectors, content
- Connection configuration: MONGODB_URI environment variable
- Reference docker-compose configurations for MongoDB setup
- init-replica.js for replica set initialization

**02_Redis_Cache.md**:
- Redis for local caching per node
- Cache strategies: search results, frequent queries
- Cache invalidation policies
- Benefits for search performance
- Configuration and integration

**03_SQLite_Usuarios.md**:
- SQLite for user authentication data
- Local storage with Raft replication
- Why SQLite: works during network partitions
- Schema: users, sessions, permissions
- Reference backend storage implementation

**04_UserDocumentRegistry.md**:
- Gossip-based user→documents mapping
- Why not in MongoDB: needs cross-partition access
- Eventual consistency via Gossip protocol
- Registry synchronization across nodes
- Reference shared/models/ for data structures

Include storage architecture diagram showing data flow.
```

---

## 📁 12_Gossip_Protocol

```
Analyze DistriSearch's Gossip protocol usage and fill 12_Gossip_Protocol folder with Spanish content:

**README.md**: Overview of Gossip-based synchronization

**01_Consistencia_Eventual.md**:
- What is eventual consistency
- CAP theorem trade-off in DistriSearch (AP system)
- How Gossip achieves eventual consistency
- Consistency guarantees and limitations
- When eventual consistency is acceptable vs not

**02_Sincronizacion_Registry.md**:
- UserDocumentRegistry synchronization via Gossip
- Gossip protocol mechanics: periodic exchange with random peers
- Conflict resolution: last-write-wins or vector clocks
- Convergence time and factors affecting it
- Implementation references from backend/app/distributed/
- Reference shared/protocols/ for message definitions

Include Gossip protocol flow diagrams and timing analysis.
```

---

## 📁 13_CAP_Theorem

```
Analyze DistriSearch's CAP theorem trade-offs and fill 13_CAP_Theorem folder with Spanish content:

**README.md**: Overview of CAP theorem application in DistriSearch

**01_Availability_Partition_Tolerance.md**:
- CAP theorem explained: Consistency, Availability, Partition Tolerance
- DistriSearch choice: AP (Available & Partition-tolerant)
- Why this choice for a search system
- Reference GUIA_DESPLIEGUE.md architecture section
- Comparison with CP systems (e.g., traditional databases)

**02_Trade_offs_DistriSearch.md**:
- Specific trade-offs in DistriSearch design:
  - Authentication during partitions: SQLite local
  - Document search: eventual consistency acceptable
  - User registry: Gossip-based, eventually consistent
- How the system handles network partitions
- Degraded mode operation
- Consistency vs availability decisions per component
- Recovery after partition heals

Include diagrams showing partition scenarios and system behavior.
```

---

## 📁 14_Despliegue

```
Analyze DistriSearch's deployment process and fill 14_Despliegue folder with Spanish content:

**README.md**: Overview of deployment process

**01_Preparacion_Imagenes.md**:
- Building Docker images from Dockerfiles
- docker/master/Dockerfile and docker/slave/Dockerfile analysis
- Image tagging and versioning
- Transferring images to cluster nodes
- Reference deploy/manual-swarm/GUIA_DESPLIEGUE.md PASO 1

**02_Inicializacion_Swarm.md**:
- docker swarm init command and options
- Advertise address configuration
- Join tokens for workers and managers
- Adding manager nodes for HA
- Reference GUIA_DESPLIEGUE.md PASO 2-3

**03_Despliegue_Nodos.md**:
- Creating overlay network
- Deploying MongoDB per node
- Deploying Master service
- Deploying Slave services
- Environment variables configuration
- Reference GUIA_DESPLIEGUE.md PASO 4-7

**04_Verificacion_Cluster.md**:
- Verifying deployment: docker node ls, docker service ls
- Testing health endpoints
- Testing distributed search
- Troubleshooting common issues
- Reference GUIA_DESPLIEGUE.md PASO 9-10 and Troubleshooting

Include actual commands from GUIA_DESPLIEGUE.md with explanations.
```

---

## 📁 15_API_Backend

```
Analyze DistriSearch's backend API and fill 15_API_Backend folder with Spanish content:

**README.md**: Overview of backend API architecture

**01_FastAPI_Estructura.md**:
- FastAPI framework choice and benefits
- Project structure: backend/app/
- Main application entry: backend/app/main.py
- Configuration: backend/app/config.py
- Middleware setup from backend/app/middleware/
- Reference actual code structure

**02_Endpoints_Principales.md**:
- API routes from backend/app/api/
- Document endpoints: upload, search, delete
- Cluster management endpoints
- Health check endpoint
- Search types: hybrid, semantic, keyword
- Request/response models from shared/models/

**03_Autenticacion.md**:
- Authentication mechanism
- JWT tokens or session-based auth
- User management
- How auth works during network partitions (SQLite local)
- Reference backend implementation

Include API endpoint documentation with examples.
```

---

## 📁 16_Frontend

```
Analyze DistriSearch's frontend and fill 16_Frontend folder with Spanish content:

**README.md**: Overview of frontend architecture

**01_React_TypeScript.md**:
- React with TypeScript setup
- Vite as build tool (vite.config.ts)
- Project structure: frontend/src/
- TypeScript configuration (tsconfig.json)
- Tailwind CSS for styling (tailwind.config.js)

**02_Componentes_Principales.md**:
- Main components from frontend/src/components/
- Page components from frontend/src/pages/
- App.tsx main component structure
- Component hierarchy and data flow

**03_Servicios_API.md**:
- API service layer from frontend/src/services/
- HTTP client configuration
- Type definitions from frontend/src/types/
- Custom hooks from frontend/src/hooks/
- Error handling and loading states

Include component diagrams and code excerpts.
```

---

## 📁 17_Testing

```
Analyze DistriSearch's testing strategy and fill 17_Testing folder with Spanish content:

**README.md**: Overview of testing approach

**01_Tests_Unitarios.md**:
- Unit testing setup with pytest
- Test structure: tests/unit/
- Mocking strategies
- Running tests: pytest commands
- Reference pytest.ini and test files

**02_Tests_Integracion.md**:
- Integration tests: tests/integration/
- Testing API endpoints
- Database integration tests
- Docker test environment (docker-compose.test.yml)

**03_Tests_Distribuidos.md**:
- Distributed system testing: tests/distributed/
- Testing cluster behavior
- Adaptive cluster tests: backend/tests/test_adaptive_cluster.py
- Testing failure scenarios
- Testing rebalancing and replication

Include test examples and coverage requirements.
```

---

## 📁 18_Control_Center

```
Analyze DistriSearch's Control Center and fill 18_Control_Center folder with Spanish content:

**README.md**: Overview of administration interface

**01_Panel_Administracion.md**:
- Control Center purpose and architecture
- Streamlit frontend: control-center/frontend/
- Panel Principal: 🏠_Panel_Principal.py
- Additional pages from control-center/frontend/pages/
- Backend API: control-center/backend/

**02_Monitoreo_Cluster.md**:
- Cluster monitoring features
- Node status visualization
- Document distribution view
- Rebalancing triggers
- Health dashboards
- Reference control-center/backend/routers/ and services/

Include screenshots descriptions and feature explanations.
```

---

## 🎯 Notas para el Agente

1. **Idioma**: Todo el contenido debe estar en **español**
2. **Formato**: Markdown con headers, bullet points, code blocks, y diagramas ASCII
3. **Referencias**: Incluir rutas a archivos del proyecto cuando sea relevante
4. **Nivel**: Estudiantes de Sistemas Distribuidos, explicar conceptos desde cero pero con profundidad técnica
5. **Código**: Incluir snippets relevantes del proyecto real
6. **Diagramas**: Usar ASCII art o describir diagramas conceptuales
7. **LaTeX**: Usar $formula$ para matemáticas inline, $$formula$$ para bloques
8. **Longitud**: Cada archivo debe ser completo y autocontenido (1000-2000 palabras aprox)
