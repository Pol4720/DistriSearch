# 🐳 Despliegue con Docker Swarm en Múltiples Máquinas Linux

Esta guía explica cómo desplegar DistriSearch en un cluster real usando **Docker Swarm** con varias máquinas Linux (físicas o VMs).

---

## 📋 Tabla de Contenidos

1. [Prerrequisitos](#prerrequisitos)
2. [Arquitectura del Despliegue](#arquitectura-del-despliegue)
3. [Paso 1: Preparar las Máquinas](#paso-1-preparar-las-maquinas)
4. [Paso 2: Inicializar Docker Swarm](#paso-2-inicializar-docker-swarm)
5. [Paso 3: Preparar las Imágenes](#paso-3-preparar-las-imagenes)
6. [Paso 4: Crear el Stack de Swarm](#paso-4-crear-el-stack-de-swarm)
7. [Paso 5: Desplegar el Stack](#paso-5-desplegar-el-stack)
8. [Paso 6: Acceder a la Aplicación](#paso-6-acceder-a-la-aplicacion)
9. [Paso 7: Operaciones Comunes](#paso-7-operaciones-comunes)
10. [Paso 8: Monitoreo y Troubleshooting](#paso-8-monitoreo-y-troubleshooting)
11. [Paso 9: Alta Disponibilidad](#paso-9-alta-disponibilidad)

---

## 📋 Prerrequisitos

### Hardware Mínimo (por nodo)

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| **CPU** | 2 cores | 4 cores |
| **RAM** | 4 GB | 8 GB |
| **Disco** | 20 GB | 50 GB SSD |
| **Red** | 100 Mbps | 1 Gbps |

### Software Requerido

- Ubuntu 22.04 LTS (o cualquier distribución Linux moderna)
- Docker Engine 24.0+
- Docker Compose v2
- Git

### Puertos Requeridos

| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 2377 | TCP | Gestión del cluster Swarm |
| 7946 | TCP/UDP | Comunicación entre nodos |
| 4789 | UDP | Overlay network (VXLAN) |
| 8000 | TCP | Backend API |
| 8501 | TCP | Frontend Streamlit |
| 5000 | UDP | Heartbeat |
| 5001 | UDP | Elección de líder |
| 5353 | UDP | Multicast Discovery |
| 27017 | TCP | MongoDB (interno) |

---

## 🏗️ Arquitectura del Despliegue

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOCKER SWARM CLUSTER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐    │
│   │      Node 1       │   │      Node 2       │   │      Node 3       │    │
│   │    (Manager)      │   │     (Worker)      │   │     (Worker)      │    │
│   │  192.168.1.101    │   │  192.168.1.102    │   │  192.168.1.103    │    │
│   │                   │   │                   │   │                   │    │
│   │ ┌───────────────┐ │   │ ┌───────────────┐ │   │ ┌───────────────┐ │    │
│   │ │   Backend     │ │   │ │   Backend     │ │   │ │   Backend     │ │    │
│   │ │   (Slave)     │◄├───┼─┤   (Slave)     │◄├───┼─┤   (Slave)     │ │    │
│   │ │   :8000       │ │   │ │   :8000       │ │   │ │   :8000       │ │    │
│   │ └───────┬───────┘ │   │ └───────┬───────┘ │   │ └───────┬───────┘ │    │
│   │         │         │   │         │         │   │         │         │    │
│   │ ┌───────▼───────┐ │   │ ┌───────▼───────┐ │   │ ┌───────▼───────┐ │    │
│   │ │   MongoDB     │ │   │ │   MongoDB     │ │   │ │   MongoDB     │ │    │
│   │ │   :27017      │ │   │ │   :27017      │ │   │ │   :27017      │ │    │
│   │ └───────────────┘ │   │ └───────────────┘ │   │ └───────────────┘ │    │
│   │                   │   │                   │   │                   │    │
│   │ ┌───────────────┐ │   │ ┌───────────────┐ │   │ ┌───────────────┐ │    │
│   │ │   Frontend    │ │   │ │   Frontend    │ │   │ │   Frontend    │ │    │
│   │ │   :8501       │ │   │ │   :8501       │ │   │ │   :8501       │ │    │
│   │ └───────────────┘ │   │ └───────────────┘ │   │ └───────────────┘ │    │
│   └───────────────────┘   └───────────────────┘   └───────────────────┘    │
│             │                       │                       │              │
│             └───────────────────────┴───────────────────────┘              │
│                          Overlay Network                                   │
│                      (distrisearch_overlay)                                │
│                                                                            │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │                    Comunicación UDP                               │    │
│   │  Heartbeat (:5000) ◄──────────────────────────────► Election (:5001)  │
│   └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Elección Dinámica de Master

DistriSearch usa el **algoritmo Bully** para elegir automáticamente un Master:

1. Todos los nodos inician como **Slave**
2. Mediante heartbeats UDP detectan otros nodos
3. El nodo con ID más alto que esté disponible se convierte en **Master**
4. Si el Master cae, se inicia una nueva elección automáticamente

---

## 🚀 Paso 1: Preparar las Máquinas

### 1.1 Instalar Docker en Cada Nodo

Ejecutar en **todas las máquinas** (Node 1, Node 2, Node 3):

```bash
#!/bin/bash
# Script: install-docker.sh

# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Añadir clave GPG oficial de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Añadir repositorio estable
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Añadir usuario actual al grupo docker
sudo usermod -aG docker $USER

# Habilitar Docker al inicio
sudo systemctl enable docker
sudo systemctl start docker

# Verificar instalación
echo "=== Verificando instalación ==="
docker --version
docker compose version

echo "✅ Docker instalado. Cierra sesión y vuelve a entrar para aplicar permisos."
```

Guardar como `install-docker.sh` y ejecutar:

```bash
chmod +x install-docker.sh
./install-docker.sh
# Cerrar sesión y volver a entrar
exit
```

### 1.2 Configurar Firewall

Ejecutar en **todas las máquinas**:

```bash
#!/bin/bash
# Script: configure-firewall.sh

# Puertos de Docker Swarm
sudo ufw allow 2377/tcp comment 'Docker Swarm cluster management'
sudo ufw allow 7946/tcp comment 'Docker Swarm node communication'
sudo ufw allow 7946/udp comment 'Docker Swarm node communication'
sudo ufw allow 4789/udp comment 'Docker Swarm overlay network'

# Puertos de DistriSearch
sudo ufw allow 8000/tcp comment 'DistriSearch Backend API'
sudo ufw allow 8501/tcp comment 'DistriSearch Frontend'
sudo ufw allow 5000/udp comment 'DistriSearch Heartbeat'
sudo ufw allow 5001/udp comment 'DistriSearch Election'
sudo ufw allow 5353/udp comment 'DistriSearch Multicast Discovery'

# MongoDB (solo desde red interna)
sudo ufw allow from 10.0.0.0/8 to any port 27017 comment 'MongoDB internal'
sudo ufw allow from 172.16.0.0/12 to any port 27017 comment 'MongoDB Docker'
sudo ufw allow from 192.168.0.0/16 to any port 27017 comment 'MongoDB LAN'

# Activar firewall
sudo ufw --force enable
sudo ufw status verbose

echo "✅ Firewall configurado"
```

### 1.3 Configurar Hostnames y /etc/hosts

En **cada máquina**, editar `/etc/hosts`:

```bash
# Reemplaza las IPs con las de tu red
sudo tee -a /etc/hosts << 'EOF'

# DistriSearch Cluster
192.168.1.101   node1 manager distrisearch-manager
192.168.1.102   node2 worker1 distrisearch-worker1
192.168.1.103   node3 worker2 distrisearch-worker2
EOF
```

Verificar conectividad:

```bash
ping -c 3 node1
ping -c 3 node2
ping -c 3 node3
```

### 1.4 Sincronizar Hora (Importante para Cluster)

```bash
# En todas las máquinas
sudo apt install -y chrony
sudo systemctl enable chrony
sudo systemctl start chrony

# Verificar sincronización
chronyc tracking
```

---

## 🐝 Paso 2: Inicializar Docker Swarm

### 2.1 Inicializar el Swarm (Solo en Node 1 - Manager)

```bash
# En Node 1 (manager) - Reemplaza con tu IP real
docker swarm init --advertise-addr 192.168.1.101
```

Salida esperada:
```
Swarm initialized: current node (abc123xyz) is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join --token SWMTKN-1-0abc123...xyz 192.168.1.101:2377

To add a manager to this swarm, run 'docker swarm join-token manager' and follow the instructions.
```

**⚠️ IMPORTANTE:** Guarda el token que aparece. Lo necesitarás para los workers.

### 2.2 Obtener Tokens (Si los Perdiste)

```bash
# En el manager
docker swarm join-token worker   # Token para workers
docker swarm join-token manager  # Token para managers adicionales
```

### 2.3 Unir Workers al Swarm

Ejecutar en **Node 2**:

```bash
docker swarm join --token SWMTKN-1-0abc123...xyz 192.168.1.101:2377
```

Ejecutar en **Node 3**:

```bash
docker swarm join --token SWMTKN-1-0abc123...xyz 192.168.1.101:2377
```

### 2.4 Verificar el Cluster

En el **manager (Node 1)**:

```bash
docker node ls
```

Salida esperada:
```
ID                            HOSTNAME   STATUS    AVAILABILITY   MANAGER STATUS   ENGINE VERSION
abc123xyz *                   node1      Ready     Active         Leader           24.0.7
def456uvw                     node2      Ready     Active                          24.0.7
ghi789rst                     node3      Ready     Active                          24.0.7
```

### 2.5 Etiquetar Nodos

```bash
# En el manager - Etiquetar para constraints de despliegue
docker node update --label-add type=backend node1
docker node update --label-add type=backend node2
docker node update --label-add type=backend node3

# Verificar etiquetas
docker node inspect node1 --format '{{ .Spec.Labels }}'
```

---

## 📦 Paso 3: Preparar las Imágenes

### 3.1 Clonar el Repositorio (en Manager)

```bash
cd ~
git clone https://github.com/Pol4720/DS-Project.git
cd DS-Project/DistriSearch
```

### 3.2 Opción A: Registry Local (Recomendado para Desarrollo)

El Registry local permite distribuir imágenes a todos los nodos sin necesidad de Docker Hub.

```bash
# En el manager - Crear servicio de registry
docker service create \
    --name registry \
    --publish published=5000,target=5000 \
    --constraint 'node.role == manager' \
    registry:2

# Verificar que está corriendo
docker service ls | grep registry
```

### 3.3 Construir y Subir Imágenes

```bash
cd ~/DS-Project/DistriSearch

# Construir imagen del backend
docker build -t localhost:5000/distrisearch-backend:latest \
    -f backend/Dockerfile .

# Construir imagen del frontend  
docker build -t localhost:5000/distrisearch-frontend:latest \
    -f frontend/Dockerfile frontend/

# Subir al registry local
docker push localhost:5000/distrisearch-backend:latest
docker push localhost:5000/distrisearch-frontend:latest

# Verificar imágenes en registry
curl http://localhost:5000/v2/_catalog
```

### 3.4 Opción B: Docker Hub (Para Producción)

```bash
# Login a Docker Hub
docker login

# Etiquetar imágenes
docker tag localhost:5000/distrisearch-backend:latest \
    tuusuario/distrisearch-backend:latest
docker tag localhost:5000/distrisearch-frontend:latest \
    tuusuario/distrisearch-frontend:latest

# Subir a Docker Hub
docker push tuusuario/distrisearch-backend:latest
docker push tuusuario/distrisearch-frontend:latest
```

---

## 📝 Paso 4: Crear el Stack de Swarm

### 4.1 Crear Directorio de Trabajo

```bash
sudo mkdir -p /opt/distrisearch
sudo chown $USER:$USER /opt/distrisearch
cd /opt/distrisearch
```

### 4.2 Crear docker-stack.yml

```bash
cat > docker-stack.yml << 'EOF'
# =============================================================================
# DistriSearch - Docker Swarm Stack
# =============================================================================
# Arquitectura Master-Slave con elección dinámica de líder
# =============================================================================

version: '3.8'

networks:
  distrisearch_net:
    driver: overlay
    attachable: true

volumes:
  mongo_node1_data:
  mongo_node2_data:
  mongo_node3_data:
  uploads_node1:
  uploads_node2:
  uploads_node3:

services:
  # ===========================================================================
  # MongoDB - Una instancia por nodo
  # ===========================================================================
  mongo_node1:
    image: mongo:6.0
    hostname: mongo_node1
    command: ["mongod", "--bind_ip_all"]
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node1
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 10s
    volumes:
      - mongo_node1_data:/data/db
    networks:
      - distrisearch_net
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

  mongo_node2:
    image: mongo:6.0
    hostname: mongo_node2
    command: ["mongod", "--bind_ip_all"]
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node2
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 10s
    volumes:
      - mongo_node2_data:/data/db
    networks:
      - distrisearch_net
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

  mongo_node3:
    image: mongo:6.0
    hostname: mongo_node3
    command: ["mongod", "--bind_ip_all"]
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node3
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 10s
    volumes:
      - mongo_node3_data:/data/db
    networks:
      - distrisearch_net
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ===========================================================================
  # Backend Node 1
  # ===========================================================================
  backend_node1:
    image: 127.0.0.1:5000/distrisearch-backend:latest
    hostname: backend_node1
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node1
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
      update_config:
        parallelism: 1
        delay: 30s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 3
    ports:
      - target: 8000
        published: 8001
        protocol: tcp
        mode: host
      - target: 5000
        published: 5001
        protocol: udp
        mode: host
      - target: 5001
        published: 5011
        protocol: udp
        mode: host
    volumes:
      - uploads_node1:/app/uploads
    environment:
      - NODE_ID=node_1
      - NODE_ROLE=slave
      - MASTER_CANDIDATE=true
      - EXTERNAL_IP=192.168.1.101
      - BACKEND_PORT=8000
      - CLUSTER_PEERS=node_2:192.168.1.102:8002:5002:5012,node_3:192.168.1.103:8003:5003:5013
      - MONGO_URI=mongodb://mongo_node1:27017
      - MONGO_DBNAME=distrisearch
      - HEARTBEAT_PORT=5000
      - ELECTION_PORT=5001
      - HEARTBEAT_INTERVAL=5
      - HEARTBEAT_TIMEOUT=15
      - REPLICATION_ENABLED=true
      - REPLICATION_FACTOR=2
      - CONSISTENCY_MODEL=eventual
      - MULTICAST_GROUP=239.255.0.1
      - MULTICAST_PORT=5353
      - DISCOVERY_INTERVAL=30
      - ENVIRONMENT=production
      - PYTHONPATH=/app
      - EMBEDDING_MODEL=all-MiniLM-L6-v2
    networks:
      - distrisearch_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # ===========================================================================
  # Backend Node 2
  # ===========================================================================
  backend_node2:
    image: 127.0.0.1:5000/distrisearch-backend:latest
    hostname: backend_node2
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node2
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
      update_config:
        parallelism: 1
        delay: 30s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 3
    ports:
      - target: 8000
        published: 8002
        protocol: tcp
        mode: host
      - target: 5000
        published: 5002
        protocol: udp
        mode: host
      - target: 5001
        published: 5012
        protocol: udp
        mode: host
    volumes:
      - uploads_node2:/app/uploads
    environment:
      - NODE_ID=node_2
      - NODE_ROLE=slave
      - MASTER_CANDIDATE=true
      - EXTERNAL_IP=192.168.1.102
      - BACKEND_PORT=8000
      - CLUSTER_PEERS=node_1:192.168.1.101:8001:5001:5011,node_3:192.168.1.103:8003:5003:5013
      - MONGO_URI=mongodb://mongo_node2:27017
      - MONGO_DBNAME=distrisearch
      - HEARTBEAT_PORT=5000
      - ELECTION_PORT=5001
      - HEARTBEAT_INTERVAL=5
      - HEARTBEAT_TIMEOUT=15
      - REPLICATION_ENABLED=true
      - REPLICATION_FACTOR=2
      - CONSISTENCY_MODEL=eventual
      - MULTICAST_GROUP=239.255.0.1
      - MULTICAST_PORT=5353
      - DISCOVERY_INTERVAL=30
      - ENVIRONMENT=production
      - PYTHONPATH=/app
      - EMBEDDING_MODEL=all-MiniLM-L6-v2
    networks:
      - distrisearch_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # ===========================================================================
  # Backend Node 3
  # ===========================================================================
  backend_node3:
    image: 127.0.0.1:5000/distrisearch-backend:latest
    hostname: backend_node3
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node3
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
      update_config:
        parallelism: 1
        delay: 30s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 3
    ports:
      - target: 8000
        published: 8003
        protocol: tcp
        mode: host
      - target: 5000
        published: 5003
        protocol: udp
        mode: host
      - target: 5001
        published: 5013
        protocol: udp
        mode: host
    volumes:
      - uploads_node3:/app/uploads
    environment:
      - NODE_ID=node_3
      - NODE_ROLE=slave
      - MASTER_CANDIDATE=true
      - EXTERNAL_IP=192.168.1.103
      - BACKEND_PORT=8000
      - CLUSTER_PEERS=node_1:192.168.1.101:8001:5001:5011,node_2:192.168.1.102:8002:5002:5012
      - MONGO_URI=mongodb://mongo_node3:27017
      - MONGO_DBNAME=distrisearch
      - HEARTBEAT_PORT=5000
      - ELECTION_PORT=5001
      - HEARTBEAT_INTERVAL=5
      - HEARTBEAT_TIMEOUT=15
      - REPLICATION_ENABLED=true
      - REPLICATION_FACTOR=2
      - CONSISTENCY_MODEL=eventual
      - MULTICAST_GROUP=239.255.0.1
      - MULTICAST_PORT=5353
      - DISCOVERY_INTERVAL=30
      - ENVIRONMENT=production
      - PYTHONPATH=/app
      - EMBEDDING_MODEL=all-MiniLM-L6-v2
    networks:
      - distrisearch_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # ===========================================================================
  # Frontend Node 1
  # ===========================================================================
  frontend_node1:
    image: 127.0.0.1:5000/distrisearch-frontend:latest
    hostname: frontend_node1
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node1
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 5s
    ports:
      - target: 8501
        published: 8511
        protocol: tcp
        mode: host
    environment:
      - NODE_ID=node_1
      - DISTRISEARCH_BACKEND_URL=http://backend_node1:8000
      - DISTRISEARCH_BACKEND_PUBLIC_URL=http://192.168.1.101:8001
    networks:
      - distrisearch_net

  # ===========================================================================
  # Frontend Node 2
  # ===========================================================================
  frontend_node2:
    image: 127.0.0.1:5000/distrisearch-frontend:latest
    hostname: frontend_node2
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node2
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 5s
    ports:
      - target: 8501
        published: 8512
        protocol: tcp
        mode: host
    environment:
      - NODE_ID=node_2
      - DISTRISEARCH_BACKEND_URL=http://backend_node2:8000
      - DISTRISEARCH_BACKEND_PUBLIC_URL=http://192.168.1.102:8002
    networks:
      - distrisearch_net

  # ===========================================================================
  # Frontend Node 3
  # ===========================================================================
  frontend_node3:
    image: 127.0.0.1:5000/distrisearch-frontend:latest
    hostname: frontend_node3
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == node3
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 5s
    ports:
      - target: 8501
        published: 8513
        protocol: tcp
        mode: host
    environment:
      - NODE_ID=node_3
      - DISTRISEARCH_BACKEND_URL=http://backend_node3:8000
      - DISTRISEARCH_BACKEND_PUBLIC_URL=http://192.168.1.103:8003
    networks:
      - distrisearch_net
EOF
```

### 4.3 Crear Script de Variables

```bash
cat > .env << 'EOF'
# Configuración del cluster - Ajustar según tu red
MANAGER_IP=192.168.1.101
WORKER1_IP=192.168.1.102
WORKER2_IP=192.168.1.103

# Registry
REGISTRY_HOST=127.0.0.1:5000

# Replicación
REPLICATION_FACTOR=2
EOF
```

---

## 🚀 Paso 5: Desplegar el Stack

### 5.1 Desplegar

```bash
cd /opt/distrisearch
docker stack deploy -c docker-stack.yml distrisearch
```

### 5.2 Verificar Despliegue

```bash
# Ver estado de servicios
docker stack services distrisearch

# Salida esperada:
# ID             NAME                         MODE         REPLICAS   IMAGE
# abc123         distrisearch_mongo_node1     replicated   1/1        mongo:6.0
# def456         distrisearch_mongo_node2     replicated   1/1        mongo:6.0
# ghi789         distrisearch_mongo_node3     replicated   1/1        mongo:6.0
# jkl012         distrisearch_backend_node1   replicated   1/1        127.0.0.1:5000/distrisearch-backend:latest
# mno345         distrisearch_backend_node2   replicated   1/1        127.0.0.1:5000/distrisearch-backend:latest
# pqr678         distrisearch_backend_node3   replicated   1/1        127.0.0.1:5000/distrisearch-backend:latest
# stu901         distrisearch_frontend_node1  replicated   1/1        127.0.0.1:5000/distrisearch-frontend:latest
# vwx234         distrisearch_frontend_node2  replicated   1/1        127.0.0.1:5000/distrisearch-frontend:latest
# yza567         distrisearch_frontend_node3  replicated   1/1        127.0.0.1:5000/distrisearch-frontend:latest
```

### 5.3 Ver Distribución de Tareas

```bash
docker stack ps distrisearch
```

### 5.4 Verificar Logs

```bash
# Logs del backend node1
docker service logs distrisearch_backend_node1 --follow --tail 50

# Logs de todos los backends
docker service logs distrisearch_backend_node1 &
docker service logs distrisearch_backend_node2 &
docker service logs distrisearch_backend_node3 &
```

### 5.5 Verificar Cluster DistriSearch

```bash
# Esperar 30-60 segundos para que los nodos se descubran

# Verificar nodos del cluster
curl -s http://192.168.1.101:8001/cluster/nodes | jq .
curl -s http://192.168.1.102:8002/cluster/nodes | jq .
curl -s http://192.168.1.103:8003/cluster/nodes | jq .

# Verificar quién es el Master
curl -s http://192.168.1.101:8001/cluster/status | jq .
```

---

## 🌐 Paso 6: Acceder a la Aplicación

### URLs de Acceso

| Nodo | Frontend | Backend API | Swagger Docs |
|------|----------|-------------|--------------|
| Node 1 | http://192.168.1.101:8511 | http://192.168.1.101:8001 | http://192.168.1.101:8001/docs |
| Node 2 | http://192.168.1.102:8512 | http://192.168.1.102:8002 | http://192.168.1.102:8002/docs |
| Node 3 | http://192.168.1.103:8513 | http://192.168.1.103:8003 | http://192.168.1.103:8003/docs |

### Configurar Load Balancer con Nginx (Opcional)

Para un único punto de entrada, instala Nginx en el manager:

```bash
sudo apt install -y nginx

sudo tee /etc/nginx/sites-available/distrisearch << 'EOF'
upstream distrisearch_backend {
    least_conn;
    server 192.168.1.101:8001 weight=1;
    server 192.168.1.102:8002 weight=1;
    server 192.168.1.103:8003 weight=1;
}

upstream distrisearch_frontend {
    least_conn;
    server 192.168.1.101:8511 weight=1;
    server 192.168.1.102:8512 weight=1;
    server 192.168.1.103:8513 weight=1;
}

server {
    listen 80;
    server_name distrisearch.local;

    # API Backend
    location /api/ {
        proxy_pass http://distrisearch_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
    }

    # Frontend Streamlit
    location / {
        proxy_pass http://distrisearch_frontend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # WebSocket para Streamlit
    location /_stcore/stream {
        proxy_pass http://distrisearch_frontend/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/distrisearch /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Acceso unificado: http://192.168.1.101 (o el hostname del manager)

---

## 🔄 Paso 7: Operaciones Comunes

### Actualizar Imágenes

```bash
cd ~/DS-Project/DistriSearch

# Reconstruir imágenes
docker build -t localhost:5000/distrisearch-backend:latest -f backend/Dockerfile .
docker build -t localhost:5000/distrisearch-frontend:latest -f frontend/Dockerfile frontend/

# Subir al registry
docker push localhost:5000/distrisearch-backend:latest
docker push localhost:5000/distrisearch-frontend:latest

# Actualizar servicios (rolling update)
docker service update --image localhost:5000/distrisearch-backend:latest distrisearch_backend_node1
docker service update --image localhost:5000/distrisearch-backend:latest distrisearch_backend_node2
docker service update --image localhost:5000/distrisearch-backend:latest distrisearch_backend_node3

docker service update --image localhost:5000/distrisearch-frontend:latest distrisearch_frontend_node1
docker service update --image localhost:5000/distrisearch-frontend:latest distrisearch_frontend_node2
docker service update --image localhost:5000/distrisearch-frontend:latest distrisearch_frontend_node3
```

### Reiniciar un Servicio

```bash
# Forzar redespliegue
docker service update --force distrisearch_backend_node1
```

### Ver Logs en Tiempo Real

```bash
# Todos los logs de backend
docker service logs -f distrisearch_backend_node1

# Filtrar por nivel
docker service logs distrisearch_backend_node1 2>&1 | grep -E "ERROR|WARNING"
```

### Escalar Servicios (No aplica para servicios con constraint)

```bash
# Para servicios sin constraint de nodo específico
docker service scale distrisearch_frontend=5
```

### Eliminar Stack

```bash
# Eliminar stack (mantiene volúmenes)
docker stack rm distrisearch

# Limpiar volúmenes (¡ELIMINA DATOS!)
docker volume prune -f

# Salir del Swarm (en cada nodo)
docker swarm leave --force  # En workers
docker swarm leave --force  # En manager (último)
```

---

## 🔧 Paso 8: Monitoreo y Troubleshooting

### Comandos de Diagnóstico

```bash
# Estado del cluster Swarm
docker node ls
docker node inspect node1 --pretty

# Estado de servicios
docker stack services distrisearch
docker stack ps distrisearch --no-trunc

# Recursos por nodo
docker node ps node1
docker node ps node2
docker node ps node3

# Redes
docker network ls
docker network inspect distrisearch_distrisearch_net
```

### Verificar Conectividad entre Nodos

```bash
# Test de ping entre contenedores
docker run --rm --network distrisearch_distrisearch_net alpine ping -c 3 backend_node1
docker run --rm --network distrisearch_distrisearch_net alpine ping -c 3 backend_node2
docker run --rm --network distrisearch_distrisearch_net alpine ping -c 3 backend_node3
```

### Verificar Heartbeats UDP

```bash
# Ver logs de heartbeat
docker service logs distrisearch_backend_node1 2>&1 | grep -i "heartbeat\|ping\|pong"

# Verificar puertos UDP en el host
sudo netstat -tulpn | grep -E "5001|5002|5003|5011|5012|5013"
```

### Problemas Comunes y Soluciones

#### ❌ "No suitable node" al desplegar

**Causa:** El constraint no encuentra nodos que coincidan.

**Solución:**
```bash
# Verificar nombres de host
docker node ls

# Verificar que el hostname en docker-stack.yml coincida
docker node inspect node1 --format '{{ .Description.Hostname }}'
```

#### ❌ Imágenes no disponibles en workers

**Causa:** El registry local no es accesible desde los workers.

**Solución:**
```bash
# En cada worker, verificar acceso al registry
curl http://192.168.1.101:5000/v2/_catalog

# Si no funciona, agregar insecure-registry
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "insecure-registries": ["192.168.1.101:5000"]
}
EOF
sudo systemctl restart docker
```

#### ❌ Nodos DistriSearch no se descubren

**Causa:** Puertos UDP bloqueados o configuración incorrecta.

**Solución:**
```bash
# Verificar firewall
sudo ufw status | grep -E "5000|5001|5353"

# Verificar variable CLUSTER_PEERS
docker service inspect distrisearch_backend_node1 --format '{{ .Spec.TaskTemplate.ContainerSpec.Env }}' | tr ',' '\n' | grep CLUSTER
```

#### ❌ MongoDB no conecta

**Causa:** El servicio MongoDB no está listo.

**Solución:**
```bash
# Verificar estado de MongoDB
docker service ps distrisearch_mongo_node1

# Test de conexión
docker run --rm --network distrisearch_distrisearch_net mongo:6.0 \
    mongosh --host mongo_node1 --eval "db.adminCommand('ping')"
```

#### ❌ Frontend no carga

**Causa:** Backend no accesible o variable de entorno incorrecta.

**Solución:**
```bash
# Verificar conectividad
docker run --rm --network distrisearch_distrisearch_net curlimages/curl \
    curl -s http://backend_node1:8000/health

# Verificar variable
docker service inspect distrisearch_frontend_node1 --format '{{ .Spec.TaskTemplate.ContainerSpec.Env }}'
```

---

## 🛡️ Paso 9: Alta Disponibilidad

### Agregar Managers Adicionales

Para tolerancia a fallos del plano de control, añade más managers:

```bash
# En el manager actual, obtener token de manager
docker swarm join-token manager

# En el nuevo nodo manager
docker swarm join --token SWMTKN-1-manager-token... 192.168.1.101:2377
```

**Recomendación:** Para producción, usa 3 o 5 managers (número impar para quorum).

### Promocionar Worker a Manager

```bash
docker node promote node2
```

### Degradar Manager a Worker

```bash
docker node demote node2
```

### Verificar Quorum

```bash
docker node ls
# Debe mostrar múltiples managers con estado "Reachable" o "Leader"
```

---

## 📊 Paso 10: Métricas y Observabilidad (Opcional)

### Agregar Prometheus y Grafana

Añade al final de `docker-stack.yml`:

```yaml
  # Prometheus
  prometheus:
    image: prom/prometheus:v2.47.0
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    networks:
      - distrisearch_net
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  # Grafana
  grafana:
    image: grafana/grafana:10.1.0
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=distrisearch
      - GF_USERS_ALLOW_SIGN_UP=false
    networks:
      - distrisearch_net
```

Crear `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'distrisearch-backends'
    static_configs:
      - targets:
        - 'backend_node1:8000'
        - 'backend_node2:8000'
        - 'backend_node3:8000'
    metrics_path: '/metrics'
    
  - job_name: 'docker-swarm'
    static_configs:
      - targets: ['host.docker.internal:9323']
```

Acceder:
- Prometheus: http://192.168.1.101:9090
- Grafana: http://192.168.1.101:3000 (admin/distrisearch)

---

## ✅ Verificación Final

### Checklist de Despliegue

- [ ] `docker node ls` muestra todos los nodos como **Ready**
- [ ] `docker stack services distrisearch` muestra **X/X** réplicas en todos los servicios
- [ ] Cada backend responde en `/health`
- [ ] Cada frontend es accesible en su puerto
- [ ] `/cluster/nodes` muestra todos los nodos DistriSearch
- [ ] `/cluster/status` identifica al Master correctamente
- [ ] Las búsquedas funcionan desde cualquier nodo
- [ ] La replicación de archivos funciona entre nodos

### Test de Failover

1. Apagar un nodo worker: `sudo shutdown now` en node3
2. Verificar que `/cluster/nodes` detecta el nodo offline
3. Si el nodo caído era Master, verificar elección de nuevo Master
4. Encender el nodo y verificar que se reincorpora al cluster

---

## 📚 Referencias

- [Docker Swarm Documentation](https://docs.docker.com/engine/swarm/)
- [Docker Stack Deploy](https://docs.docker.com/engine/reference/commandline/stack_deploy/)
- [Overlay Networks](https://docs.docker.com/network/overlay/)
- [DistriSearch - Arquitectura](../arquitectura.md)
- [DistriSearch - FAQ](../faq.md)

---

**Última actualización:** Diciembre 2024
