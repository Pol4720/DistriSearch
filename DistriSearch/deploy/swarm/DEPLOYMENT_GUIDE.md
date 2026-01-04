# Guía de Despliegue Docker Swarm - DistriSearch

## Índice

1. [Visión General](#visión-general)
2. [Requisitos Previos](#requisitos-previos)
3. [Arquitectura del Despliegue](#arquitectura-del-despliegue)
4. [Preparación de las Máquinas](#preparación-de-las-máquinas)
5. [Paso 1: Configurar el Manager (Máquina Principal)](#paso-1-configurar-el-manager)
6. [Paso 2: Unir Workers al Swarm](#paso-2-unir-workers-al-swarm)
7. [Paso 3: Desplegar Servicios Compartidos](#paso-3-desplegar-servicios-compartidos)
8. [Paso 4: Desplegar Nodos DistriSearch](#paso-4-desplegar-nodos-distrisearch)
9. [Verificación del Despliegue](#verificación-del-despliegue)
10. [Comandos Útiles](#comandos-útiles)
11. [Troubleshooting](#troubleshooting)

---

## Visión General

DistriSearch es un sistema de búsqueda distribuida que implementa:

- **Consenso Raft**: Elección de líder y replicación de log
- **Modo AP (CAP)**: Prioriza disponibilidad sobre consistencia fuerte
- **Tolerancia a Particiones**: Sigue funcionando cuando nodos se desconectan
- **Replicación Adaptativa**: Ajusta factor de replicación según nodos disponibles
- **Rebalanceo Automático**: Distribuye carga entre nodos

### ¿Por qué Docker Swarm sin Compose?

Docker Compose está diseñado para un solo host. Docker Swarm permite:
- Despliegue en múltiples máquinas físicas
- Orquestación nativa de contenedores
- Red overlay para comunicación entre hosts
- Descubrimiento de servicios integrado

---

## Requisitos Previos

### En TODAS las máquinas:

```bash
# 1. Docker instalado (versión 20.10+)
docker --version

# 2. Puertos abiertos (firewall)
# - 2377/tcp: Comunicación del cluster Swarm
# - 7946/tcp+udp: Comunicación entre nodos
# - 4789/udp: Overlay network
# - 8000/tcp: API Backend DistriSearch
# - 8443/tcp: HTTPS Frontend
# - 27017/tcp: MongoDB (solo si usas réplicas)

# 3. Sincronización de tiempo (NTP)
sudo apt install chrony -y
sudo systemctl enable chrony
```

### Información que necesitas:

| Máquina | Rol | IP | Hostname |
|---------|-----|-------|----------|
| PC1 | Manager + Nodo Master | 192.168.1.100 | manager1 |
| PC2 | Worker + Nodo Slave 1 | 192.168.1.101 | worker1 |
| PC3 | Worker + Nodo Slave 2 | 192.168.1.102 | worker2 |

> **Nota**: Ajusta las IPs según tu red local.

---

## Arquitectura del Despliegue

```
┌─────────────────────────────────────────────────────────────────┐
│                        RED OVERLAY                              │
│                    (distrisearch-network)                       │
├─────────────────┬─────────────────┬─────────────────────────────┤
│     PC1         │      PC2        │        PC3                  │
│   (Manager)     │    (Worker)     │      (Worker)               │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ ┌─────────────┐ │ ┌─────────────┐ │ ┌─────────────┐             │
│ │   Master    │ │ │   Slave 1   │ │ │   Slave 2   │             │
│ │  Backend    │ │ │  Backend    │ │ │  Backend    │             │
│ │  + Frontend │ │ │  + Frontend │ │ │  + Frontend │             │
│ │  + MongoDB  │ │ │             │ │ │             │             │
│ │  + Redis    │ │ │             │ │ │             │             │
│ └─────────────┘ │ └─────────────┘ │ └─────────────┘             │
├─────────────────┴─────────────────┴─────────────────────────────┤
│                    DNS Docker + CoreDNS                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Preparación de las Máquinas

### En CADA máquina, ejecuta:

```bash
# Crear directorio de trabajo
mkdir -p ~/distrisearch
cd ~/distrisearch

# Clonar el repositorio (o copiar archivos)
git clone https://github.com/Pol4720/DistriSearch.git
cd DistriSearch/DistriSearch

# Construir imágenes localmente (o usar registry)
# Opción A: Construir en cada máquina
./deploy/swarm/scripts/build-images.sh

# Opción B: Usar un registry privado (más eficiente)
# Ver sección "Usando Registry Privado"
```

---

## Paso 1: Configurar el Manager

### En PC1 (192.168.1.100) - Máquina Manager:

```bash
# 1. Inicializar Docker Swarm
docker swarm init --advertise-addr 192.168.1.100

# IMPORTANTE: Guarda el token que aparece, lo necesitas para los workers
# Ejemplo de salida:
# docker swarm join --token SWMTKN-1-xxx 192.168.1.100:2377
```

**¿Qué hace `docker swarm init`?**
- Convierte esta máquina en el **Manager** del cluster
- Crea una red overlay interna para comunicación
- Genera tokens de autenticación para workers
- Inicia el motor de orquestación Raft (sí, Swarm también usa Raft!)

```bash
# 2. Crear la red overlay para DistriSearch
docker network create \
  --driver overlay \
  --attachable \
  --subnet 10.0.10.0/24 \
  distrisearch-network

# --driver overlay: Red que abarca múltiples hosts
# --attachable: Permite contenedores standalone conectarse
# --subnet: Rango de IPs interno para contenedores
```

**¿Qué es una red overlay?**
- Permite que contenedores en diferentes máquinas físicas se comuniquen
- Usa VXLAN para encapsular tráfico entre hosts
- Docker gestiona el enrutamiento automáticamente

```bash
# 3. Verificar el estado del Swarm
docker node ls

# Deberías ver algo como:
# ID          HOSTNAME   STATUS   AVAILABILITY   MANAGER STATUS
# abc123 *    manager1   Ready    Active         Leader
```

---

## Paso 2: Unir Workers al Swarm

### En PC2 (192.168.1.101) - Worker 1:

```bash
# 1. Unirse al Swarm usando el token del paso anterior
docker swarm join --token SWMTKN-1-xxxxx 192.168.1.100:2377

# Si perdiste el token, en el Manager ejecuta:
# docker swarm join-token worker
```

**¿Qué hace `docker swarm join`?**
- Conecta esta máquina al cluster Swarm
- Establece comunicación encriptada con el Manager
- Permite que el Manager despliegue contenedores aquí
- Se une a las redes overlay del cluster

### En PC3 (192.168.1.102) - Worker 2:

```bash
# Repetir el mismo comando
docker swarm join --token SWMTKN-1-xxxxx 192.168.1.100:2377
```

### Verificar en el Manager:

```bash
docker node ls

# Ahora deberías ver 3 nodos:
# ID          HOSTNAME   STATUS   AVAILABILITY   MANAGER STATUS
# abc123 *    manager1   Ready    Active         Leader
# def456      worker1    Ready    Active         
# ghi789      worker2    Ready    Active
```

---

## Paso 3: Desplegar Servicios Compartidos

### En PC1 (Manager) - Desplegar MongoDB y Redis:

Estos servicios son compartidos y solo necesitan una instancia (o réplicas para HA).

```bash
# 1. Desplegar MongoDB (en el Manager)
docker run -d \
  --name mongodb \
  --network distrisearch-network \
  --restart unless-stopped \
  -v mongodb_data:/data/db \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=distrisearch_secret \
  -p 27017:27017 \
  mongo:6.0

# --network distrisearch-network: Conecta a la red overlay
# -v mongodb_data:/data/db: Persiste datos en volumen
# -p 27017:27017: Expone puerto (opcional, para debug)
```

**¿Por qué MongoDB en el Manager?**
- Es el almacenamiento central de metadatos
- Los nodos slave se conectan a él vía red overlay
- En producción, podrías usar MongoDB ReplicaSet para HA

```bash
# 2. Desplegar Redis (en el Manager)
docker run -d \
  --name redis \
  --network distrisearch-network \
  --restart unless-stopped \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes

# Redis se usa para:
# - Caché de búsquedas
# - Contadores compartidos
# - Pub/Sub para notificaciones entre nodos
```

```bash
# 3. Verificar servicios
docker ps

# Deberías ver:
# CONTAINER ID   IMAGE         STATUS         NAMES
# xxx            mongo:6.0     Up 2 minutes   mongodb
# yyy            redis:7       Up 1 minute    redis
```

---

## Paso 4: Desplegar Nodos DistriSearch

### 4.1 En PC1 - Desplegar Nodo Master:

```bash
# Ejecutar script de despliegue del Master
./deploy/swarm/scripts/deploy-master.sh

# O manualmente:
docker run -d \
  --name distrisearch-master \
  --hostname master \
  --network distrisearch-network \
  --restart unless-stopped \
  -e NODE_ROLE=master \
  -e NODE_ID=master \
  -e MONGODB_URL=mongodb://admin:distrisearch_secret@mongodb:27017 \
  -e REDIS_URL=redis://redis:6379 \
  -e CLUSTER_NODES=master,slave-1,slave-2 \
  -e ADVERTISE_ADDR=192.168.1.100 \
  -p 8000:8000 \
  -p 8443:8443 \
  -v distrisearch_data:/app/data \
  distrisearch/node:latest
```

**Explicación de variables de entorno:**

| Variable | Descripción |
|----------|-------------|
| `NODE_ROLE` | `master` o `slave` - Define el rol del nodo |
| `NODE_ID` | Identificador único del nodo |
| `MONGODB_URL` | Conexión a MongoDB (usa nombre del contenedor) |
| `REDIS_URL` | Conexión a Redis |
| `CLUSTER_NODES` | Lista de nodos esperados en el cluster |
| `ADVERTISE_ADDR` | IP que otros nodos usarán para contactar a este |

### 4.2 En PC2 - Desplegar Nodo Slave 1:

```bash
# Ejecutar script de despliegue del Slave
./deploy/swarm/scripts/deploy-slave.sh slave-1 192.168.1.100

# O manualmente:
docker run -d \
  --name distrisearch-slave-1 \
  --hostname slave-1 \
  --network distrisearch-network \
  --restart unless-stopped \
  -e NODE_ROLE=slave \
  -e NODE_ID=slave-1 \
  -e MASTER_HOST=192.168.1.100 \
  -e MASTER_PORT=8000 \
  -e MONGODB_URL=mongodb://admin:distrisearch_secret@mongodb:27017 \
  -e REDIS_URL=redis://redis:6379 \
  -e ADVERTISE_ADDR=192.168.1.101 \
  -p 8000:8000 \
  -p 8443:8443 \
  -v distrisearch_data:/app/data \
  distrisearch/node:latest
```

**¿Qué pasa cuando un Slave se inicia?**
1. Contacta al Master en `MASTER_HOST:MASTER_PORT`
2. Se registra en el cluster
3. Recibe información de otros nodos
4. Comienza a participar en elecciones Raft
5. Recibe documentos replicados

### 4.3 En PC3 - Desplegar Nodo Slave 2:

```bash
docker run -d \
  --name distrisearch-slave-2 \
  --hostname slave-2 \
  --network distrisearch-network \
  --restart unless-stopped \
  -e NODE_ROLE=slave \
  -e NODE_ID=slave-2 \
  -e MASTER_HOST=192.168.1.100 \
  -e MASTER_PORT=8000 \
  -e MONGODB_URL=mongodb://admin:distrisearch_secret@mongodb:27017 \
  -e REDIS_URL=redis://redis:6379 \
  -e ADVERTISE_ADDR=192.168.1.102 \
  -p 8000:8000 \
  -p 8443:8443 \
  -v distrisearch_data:/app/data \
  distrisearch/node:latest
```

---

## Verificación del Despliegue

### 1. Verificar que todos los contenedores están corriendo:

```bash
# En cada máquina
docker ps

# En el Manager, ver estado del cluster
docker node ls
```

### 2. Verificar conectividad entre nodos:

```bash
# Desde el Master, hacer ping a los slaves
docker exec distrisearch-master ping -c 3 slave-1
docker exec distrisearch-master ping -c 3 slave-2

# Verificar resolución DNS
docker exec distrisearch-master nslookup slave-1
```

### 3. Verificar el estado del cluster DistriSearch:

```bash
# Ver estado del cluster
curl http://192.168.1.100:8000/api/v1/cluster/status

# Respuesta esperada:
{
  "status": "healthy",
  "leader": "master",
  "nodes": [
    {"id": "master", "status": "healthy", "role": "leader"},
    {"id": "slave-1", "status": "healthy", "role": "follower"},
    {"id": "slave-2", "status": "healthy", "role": "follower"}
  ],
  "partition_status": "connected"
}
```

### 4. Verificar replicación:

```bash
# Subir un documento
curl -X POST http://192.168.1.100:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "content": "Documento de prueba"}'

# Verificar que está en los slaves
curl http://192.168.1.101:8000/api/v1/documents
curl http://192.168.1.102:8000/api/v1/documents
```

### 5. Probar tolerancia a particiones:

```bash
# En PC2, detener el slave-1
docker stop distrisearch-slave-1

# Verificar que el cluster sigue funcionando (modo AP)
curl http://192.168.1.100:8000/api/v1/cluster/status

# Las búsquedas deben seguir funcionando
curl http://192.168.1.100:8000/api/v1/search?q=prueba

# Reiniciar el slave
docker start distrisearch-slave-1

# Verificar que se reconecta
curl http://192.168.1.100:8000/api/v1/cluster/status
```

---

## Comandos Útiles

### Gestión del Swarm:

```bash
# Ver todos los nodos
docker node ls

# Ver servicios desplegados
docker service ls

# Ver logs de un servicio
docker service logs <service_name>

# Escalar un servicio
docker service scale <service_name>=3

# Drenar un nodo (para mantenimiento)
docker node update --availability drain <node_id>

# Reactivar un nodo
docker node update --availability active <node_id>

# Sacar un nodo del Swarm
# En el worker: docker swarm leave
# En el manager: docker node rm <node_id>
```

### Gestión de DistriSearch:

```bash
# Ver logs del nodo
docker logs -f distrisearch-master

# Entrar al contenedor
docker exec -it distrisearch-master /bin/bash

# Ver métricas
curl http://localhost:8000/api/v1/metrics

# Forzar rebalanceo
curl -X POST http://localhost:8000/api/v1/cluster/rebalance

# Ver historial de elecciones
curl http://localhost:8000/api/v1/cluster/elections
```

---

## Troubleshooting

### Problema: Los workers no pueden unirse al Swarm

```bash
# Verificar firewall
sudo ufw status
sudo ufw allow 2377/tcp
sudo ufw allow 7946/tcp
sudo ufw allow 7946/udp
sudo ufw allow 4789/udp

# Verificar conectividad
ping 192.168.1.100
telnet 192.168.1.100 2377
```

### Problema: Los contenedores no pueden comunicarse

```bash
# Verificar red overlay
docker network inspect distrisearch-network

# Verificar que el contenedor está en la red
docker inspect distrisearch-slave-1 | grep Networks

# Probar DNS
docker exec distrisearch-slave-1 nslookup mongodb
```

### Problema: MongoDB connection refused

```bash
# Verificar que MongoDB está corriendo
docker ps | grep mongo

# Verificar logs
docker logs mongodb

# Verificar conectividad desde otro contenedor
docker exec distrisearch-slave-1 nc -zv mongodb 27017
```

### Problema: Nodo no se une al cluster DistriSearch

```bash
# Ver logs del nodo
docker logs distrisearch-slave-1

# Verificar variables de entorno
docker inspect distrisearch-slave-1 | grep -A 20 Env

# Verificar que el Master está accesible
docker exec distrisearch-slave-1 curl http://master:8000/health
```

### Problema: Elección de líder fallando

```bash
# Ver estado de Raft
curl http://localhost:8000/api/v1/raft/status

# Forzar nueva elección (solo en emergencias)
curl -X POST http://localhost:8000/api/v1/raft/trigger-election
```

---

## Apéndice: Usando Registry Privado

Para evitar construir imágenes en cada máquina:

### 1. En el Manager, iniciar registry:

```bash
docker run -d \
  --name registry \
  --restart unless-stopped \
  -p 5000:5000 \
  -v registry_data:/var/lib/registry \
  registry:2
```

### 2. Construir y subir imagen:

```bash
# Construir
docker build -t 192.168.1.100:5000/distrisearch/node:latest ./docker/slave

# Subir
docker push 192.168.1.100:5000/distrisearch/node:latest
```

### 3. En cada Worker, configurar Docker para usar registry inseguro:

```bash
# Editar /etc/docker/daemon.json
{
  "insecure-registries": ["192.168.1.100:5000"]
}

# Reiniciar Docker
sudo systemctl restart docker
```

### 4. Descargar imagen en workers:

```bash
docker pull 192.168.1.100:5000/distrisearch/node:latest
```

---

## Próximos Pasos

1. ✅ Despliegue básico funcionando
2. ⬜ Configurar HTTPS con certificados reales
3. ⬜ Configurar backups automáticos de MongoDB
4. ⬜ Configurar monitorización (Prometheus + Grafana)
5. ⬜ Configurar alertas

---

**¡Listo!** Tu cluster DistriSearch debería estar funcionando. Si tienes problemas, revisa la sección de Troubleshooting o los logs de cada contenedor.
