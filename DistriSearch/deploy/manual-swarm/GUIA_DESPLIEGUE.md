# Guía de Despliegue Manual - Docker Swarm Multi-Host

## Despliegue de DistriSearch en Múltiples Máquinas Linux

Esta guía explica paso a paso cómo desplegar DistriSearch en un cluster Docker Swarm 
**sin usar docker-compose**, desplegando máquina por máquina.

---

## 📋 Requisitos Previos

### En TODAS las máquinas:
- Ubuntu 20.04+ o similar
- Docker instalado (`sudo apt install docker.io`)
- Usuario en grupo docker (`sudo usermod -aG docker $USER`)
- Puertos abiertos (ver sección de red)

### Puertos necesarios:
| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 2377 | TCP | Gestión del cluster Swarm |
| 7946 | TCP/UDP | Comunicación entre nodos |
| 4789 | UDP | Overlay network (VXLAN) |
| 8443 | TCP | HTTPS Frontend/API |
| 8000 | TCP | Backend API interno |
| 27017 | TCP | MongoDB |

### Abrir puertos en firewall:
```bash
# UFW (Ubuntu)
sudo ufw allow 2377/tcp
sudo ufw allow 7946/tcp
sudo ufw allow 7946/udp
sudo ufw allow 4789/udp
sudo ufw allow 8443/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 27017/tcp
sudo ufw reload
```

---

## 🖥️ Nomenclatura de Máquinas

Para esta guía usaremos:

| Rol | Hostname | IP (ejemplo) | Función |
|-----|----------|--------------|---------|
| Manager Principal | manager1 | 192.168.1.10 | Líder del Swarm + Master DistriSearch |
| Worker 1 | worker1 | 192.168.1.11 | Slave 1 + MongoDB |
| Worker 2 | worker2 | 192.168.1.12 | Slave 2 + MongoDB |
| Worker 3 | worker3 | 192.168.1.13 | Slave 3 + MongoDB |

> **Nota**: Puedes añadir más workers siguiendo el mismo patrón.

---

## 🔧 PASO 1: Preparación de Imágenes Docker

### En la máquina de desarrollo (donde tienes el código):

```bash
# 1. Navegar al directorio del proyecto
cd /ruta/a/DistriSearch

# 2. Construir imágenes
docker build -f docker/master/Dockerfile -t distrisearch/master:latest .
docker build -f docker/slave/Dockerfile -t distrisearch/slave:latest .

# 3. Guardar imágenes para transferir
docker save distrisearch/master:latest | gzip > distrisearch-master.tar.gz
docker save distrisearch/slave:latest | gzip > distrisearch-slave.tar.gz

# 4. Transferir a todas las máquinas
for host in manager1 worker1 worker2 worker3; do
    scp distrisearch-master.tar.gz distrisearch-slave.tar.gz $host:~
done
```

### En CADA máquina del cluster:

```bash
# Cargar imágenes
gunzip -c ~/distrisearch-master.tar.gz | docker load
gunzip -c ~/distrisearch-slave.tar.gz | docker load

# Verificar
docker images | grep distrisearch
```

---

## 🌐 PASO 2: Inicializar Docker Swarm

### En MANAGER1 (máquina principal):

```bash
# Inicializar el Swarm
# Reemplaza 192.168.1.10 con la IP real del manager
docker swarm init --advertise-addr 192.168.1.10

# Este comando mostrará algo como:
# docker swarm join --token SWMTKN-1-xxx... 192.168.1.10:2377
# ¡GUARDA ESTE TOKEN!
```

**¿Qué significa esto?**
- `docker swarm init` crea un nuevo cluster Swarm
- `--advertise-addr` es la IP que otros nodos usarán para conectarse
- El token es la "contraseña" para unirse al cluster

### Obtener tokens (si los perdiste):

```bash
# Token para workers
docker swarm join-token worker

# Token para managers adicionales
docker swarm join-token manager
```

---

## 🔗 PASO 3: Unir Workers al Cluster

### En WORKER1, WORKER2, WORKER3:

```bash
# Usar el token del paso anterior
docker swarm join --token SWMTKN-1-xxx... 192.168.1.10:2377
```

**¿Qué significa esto?**
- Cada worker se une al cluster como nodo de trabajo
- El manager coordinará qué contenedores corren en cada worker

### Verificar (en manager1):

```bash
docker node ls

# Deberías ver:
# ID          HOSTNAME   STATUS    AVAILABILITY   MANAGER STATUS
# abc123 *    manager1   Ready     Active         Leader
# def456      worker1    Ready     Active         
# ghi789      worker2    Ready     Active         
# jkl012      worker3    Ready     Active         
```

---

## 🕸️ PASO 4: Crear Red Overlay

### En MANAGER1:

```bash
# Crear red overlay para que los contenedores se comuniquen
docker network create \
    --driver overlay \
    --attachable \
    --subnet 10.0.10.0/24 \
    distrisearch-network
```

**¿Qué significa esto?**
- `overlay` permite comunicación entre contenedores en diferentes máquinas
- `--attachable` permite conectar contenedores standalone (no solo servicios)
- `--subnet` define el rango de IPs internas

### Verificar:

```bash
docker network ls | grep distrisearch
```

---

## 💾 PASO 5: Desplegar MongoDB (Almacenamiento Local por Nodo)

### IMPORTANTE: Cada Slave tiene su PROPIA base de datos MongoDB

### En WORKER1:

```bash
# Crear volumen persistente
docker volume create mongodb-data-worker1

# Ejecutar MongoDB
docker run -d \
    --name mongodb-local \
    --network distrisearch-network \
    --restart unless-stopped \
    -v mongodb-data-worker1:/data/db \
    -e MONGO_INITDB_DATABASE=distrisearch \
    -p 27017:27017 \
    mongo:6.0 \
    mongod --bind_ip_all
```

### En WORKER2:

```bash
docker volume create mongodb-data-worker2

docker run -d \
    --name mongodb-local \
    --network distrisearch-network \
    --restart unless-stopped \
    -v mongodb-data-worker2:/data/db \
    -e MONGO_INITDB_DATABASE=distrisearch \
    -p 27017:27017 \
    mongo:6.0 \
    mongod --bind_ip_all
```

### En WORKER3:

```bash
docker volume create mongodb-data-worker3

docker run -d \
    --name mongodb-local \
    --network distrisearch-network \
    --restart unless-stopped \
    -v mongodb-data-worker3:/data/db \
    -e MONGO_INITDB_DATABASE=distrisearch \
    -p 27017:27017 \
    mongo:6.0 \
    mongod --bind_ip_all
```

**¿Por qué MongoDB local en cada nodo?**
- Cada Slave almacena sus propios documentos (particionamiento)
- El VP-Tree del Master decide qué documentos van a qué nodo
- Esto permite escalabilidad horizontal del almacenamiento

---

## 👑 PASO 6: Desplegar Master Node

### En MANAGER1:

```bash
docker run -d \
    --name distrisearch-master \
    --network distrisearch-network \
    --restart unless-stopped \
    -e NODE_ROLE=master \
    -e NODE_ID=master-1 \
    -e MONGODB_URI=mongodb://mongodb-central:27017/distrisearch \
    -e CLUSTER_NODES=worker1,worker2,worker3 \
    -e RAFT_ENABLED=true \
    -e LOG_LEVEL=INFO \
    -p 8001:8001 \
    distrisearch/master:latest
```

**Variables de entorno explicadas:**
- `NODE_ROLE=master`: Este nodo es el coordinador
- `CLUSTER_NODES`: Lista de slaves que coordinará
- `RAFT_ENABLED`: Activa el consenso Raft para elección de líder

### Si necesitas MongoDB central para metadatos del cluster:

```bash
docker run -d \
    --name mongodb-central \
    --network distrisearch-network \
    --restart unless-stopped \
    -v mongodb-central:/data/db \
    mongo:6.0 \
    mongod --bind_ip_all
```

---

## 🖥️ PASO 7: Desplegar Slaves

### En WORKER1:

```bash
docker run -d \
    --name distrisearch-slave \
    --network distrisearch-network \
    --restart unless-stopped \
    -e NODE_ROLE=slave \
    -e NODE_ID=slave-worker1 \
    -e MASTER_HOST=distrisearch-master \
    -e MONGODB_URI=mongodb://mongodb-local:27017/distrisearch \
    -e HTTPS_ENABLED=true \
    -e LOG_LEVEL=INFO \
    -p 8443:443 \
    -p 8000:8000 \
    distrisearch/slave:latest
```

### En WORKER2:

```bash
docker run -d \
    --name distrisearch-slave \
    --network distrisearch-network \
    --restart unless-stopped \
    -e NODE_ROLE=slave \
    -e NODE_ID=slave-worker2 \
    -e MASTER_HOST=distrisearch-master \
    -e MONGODB_URI=mongodb://mongodb-local:27017/distrisearch \
    -e HTTPS_ENABLED=true \
    -e LOG_LEVEL=INFO \
    -p 8443:443 \
    -p 8000:8000 \
    distrisearch/slave:latest
```

### En WORKER3:

```bash
docker run -d \
    --name distrisearch-slave \
    --network distrisearch-network \
    --restart unless-stopped \
    -e NODE_ROLE=slave \
    -e NODE_ID=slave-worker3 \
    -e MASTER_HOST=distrisearch-master \
    -e MONGODB_URI=mongodb://mongodb-local:27017/distrisearch \
    -e HTTPS_ENABLED=true \
    -e LOG_LEVEL=INFO \
    -p 8443:443 \
    -p 8000:8000 \
    distrisearch/slave:latest
```

**Variables de entorno explicadas:**
- `MASTER_HOST`: Nombre DNS del master en la red overlay
- `MONGODB_URI`: Conexión a MongoDB LOCAL de este nodo
- El slave se registrará automáticamente con el master

---

## ⚖️ PASO 8: Configurar Load Balancer (Opcional)

### En MANAGER1 (o máquina dedicada):

```bash
# Crear configuración nginx
cat > /tmp/nginx-lb.conf << 'EOF'
upstream distrisearch_backend {
    least_conn;  # Balanceo por menor conexiones
    server worker1:8443;
    server worker2:8443;
    server worker3:8443;
}

server {
    listen 443 ssl;
    server_name distrisearch.local;
    
    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;
    
    location / {
        proxy_pass https://distrisearch_backend;
        proxy_ssl_verify off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Ejecutar nginx como load balancer
docker run -d \
    --name load-balancer \
    --network distrisearch-network \
    -p 443:443 \
    -v /tmp/nginx-lb.conf:/etc/nginx/conf.d/default.conf:ro \
    nginx:alpine
```

---

## ✅ PASO 9: Verificar Despliegue

### En MANAGER1:

```bash
# Ver todos los contenedores del cluster
docker node ls
for node in manager1 worker1 worker2 worker3; do
    echo "=== $node ===" 
    ssh $node docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
done

# Verificar que los slaves se registraron con el master
docker exec distrisearch-master curl -s http://localhost:8001/api/cluster/nodes

# Verificar red overlay
docker network inspect distrisearch-network
```

### Probar acceso:

```bash
# Desde cualquier máquina
curl -k https://worker1:8443/health
curl -k https://worker2:8443/health
curl -k https://worker3:8443/health

# Verificar búsqueda distribuida
curl -k -X POST https://worker1:8443/api/v1/search/ \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "search_type": "hybrid"}'
```

---

## 🧪 PASO 10: Probar Funcionalidades Distribuidas

### Test 1: Tolerancia a Particiones

```bash
# Simular fallo de un nodo
ssh worker2 docker stop distrisearch-slave

# Verificar que el sistema sigue funcionando
curl -k https://worker1:8443/health
curl -k https://worker3:8443/health

# Subir un documento (debería distribuirse entre nodos activos)
curl -k -X POST https://worker1:8443/api/v1/documents/upload \
    -F "file=@test.txt"

# Restaurar nodo
ssh worker2 docker start distrisearch-slave
```

### Test 2: Rebalanceo

```bash
# Ver distribución actual de documentos
docker exec distrisearch-master curl -s http://localhost:8001/api/cluster/stats

# Añadir nuevo nodo (worker4)
# Seguir pasos 5 y 7 para worker4

# Verificar que el rebalanceo ocurre automáticamente
docker logs distrisearch-master | grep -i rebalance
```

### Test 3: Elección de Líder

```bash
# Ver líder actual
docker exec distrisearch-master curl -s http://localhost:8001/api/cluster/leader

# Simular fallo del master
docker stop distrisearch-master

# Verificar que se elige nuevo líder (si hay master standby)
# O que los slaves continúan operando en modo degradado
```

---

## 📊 Arquitectura Final

```
┌─────────────────────────────────────────────────────────────────┐
│                     DOCKER SWARM CLUSTER                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  OVERLAY NETWORK                             │ │
│  │               (distrisearch-network)                         │ │
│  │                    10.0.10.0/24                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           │              │              │              │          │
│  ┌────────▼────────┐ ┌───▼────────┐ ┌───▼────────┐ ┌───▼───────┐│
│  │   MANAGER1      │ │  WORKER1   │ │  WORKER2   │ │  WORKER3  ││
│  │                 │ │            │ │            │ │           ││
│  │ ┌─────────────┐ │ │┌──────────┐│ │┌──────────┐│ │┌─────────┐││
│  │ │   Master    │ │ ││  Slave   ││ ││  Slave   ││ ││  Slave  │││
│  │ │  (Raft)     │ │ ││  :8443   ││ ││  :8443   ││ ││  :8443  │││
│  │ │  :8001      │ │ │└──────────┘│ │└──────────┘│ │└─────────┘││
│  │ └─────────────┘ │ │┌──────────┐│ │┌──────────┐│ │┌─────────┐││
│  │                 │ ││ MongoDB  ││ ││ MongoDB  ││ ││ MongoDB │││
│  │ ┌─────────────┐ │ ││  LOCAL   ││ ││  LOCAL   ││ ││  LOCAL  │││
│  │ │  MongoDB    │ │ │└──────────┘│ │└──────────┘│ │└─────────┘││
│  │ │  CENTRAL    │ │ │            │ │            │ │           ││
│  │ └─────────────┘ │ │ Docs: 33% │ │ Docs: 33% │ │ Docs: 34% ││
│  └─────────────────┘ └────────────┘ └────────────┘ └───────────┘│
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                   VP-TREE PARTITIONING                     │   │
│  │  El Master decide dónde almacenar cada documento           │   │
│  │  basándose en similitud semántica (vectores TF-IDF)       │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔥 Comandos Útiles

```bash
# Ver logs de un contenedor
docker logs -f distrisearch-slave

# Ejecutar comando dentro del contenedor
docker exec -it distrisearch-slave bash

# Ver uso de recursos
docker stats

# Limpiar contenedores parados
docker container prune

# Salir del Swarm (en un worker)
docker swarm leave

# Forzar salida del Swarm (en manager)
docker swarm leave --force

# Eliminar nodo del cluster (desde manager)
docker node rm worker1
```

---

## 🚨 Troubleshooting

### "Network distrisearch-network not found"
```bash
# El nodo no ve la red overlay
# Solución: Verificar que está en el Swarm
docker info | grep Swarm
```

### "Cannot connect to master"
```bash
# Verificar DNS interno
docker exec distrisearch-slave ping distrisearch-master

# Verificar que master está corriendo
docker ps | grep master
```

### "MongoDB connection failed"
```bash
# Verificar MongoDB local
docker logs mongodb-local

# Probar conexión
docker exec distrisearch-slave python -c "from pymongo import MongoClient; print(MongoClient('mongodb://mongodb-local:27017').admin.command('ping'))"
```

### "Port already in use"
```bash
# Ver qué usa el puerto
sudo lsof -i :8443
# O cambiar el puerto mapeado
docker run ... -p 9443:443 ...
```

---

## 📝 Siguiente: Scripts Automatizados

Ver carpeta `scripts/` para scripts que automatizan estos pasos:
- `01-prepare-node.sh` - Prepara una máquina
- `02-init-swarm.sh` - Inicializa el Swarm (solo manager)
- `03-join-swarm.sh` - Une un worker al Swarm
- `04-deploy-mongodb.sh` - Despliega MongoDB local
- `05-deploy-master.sh` - Despliega el Master
- `06-deploy-slave.sh` - Despliega un Slave
- `07-verify-cluster.sh` - Verifica el estado del cluster
