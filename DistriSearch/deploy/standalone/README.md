# DistriSearch - Despliegue con Docker Run + Swarm Overlay Network

## 📋 Índice

1. [Introducción](#introducción)
2. [Arquitectura](#arquitectura)
3. [Pre-requisitos](#pre-requisitos)
4. [Guía Rápida](#guía-rápida)
5. [Despliegue Paso a Paso](#despliegue-paso-a-paso)
6. [Control Manual de Nodos](#control-manual-de-nodos)
7. [Escenarios de Prueba](#escenarios-de-prueba)
8. [Troubleshooting](#troubleshooting)

---

## Introducción

Este despliegue usa **contenedores Docker autónomos** (`docker run`) conectados a una **red overlay de Docker Swarm**.

### ¿Por qué esta arquitectura?

**Docker Swarm se usa SOLO para la red overlay:**
- Proporciona comunicación entre máquinas
- Red cifrada y automática

**NO usamos Docker Services porque:**
- Docker Swarm requiere **quórum de managers** para funcionar
- Con solo 2 máquinas, si el líder cae, todo el sistema se detiene
- No hay tolerancia real a particiones de red

### Ventajas de este enfoque

- ✅ **Red overlay de Swarm** - comunicación entre máquinas sin configuración manual
- ✅ **Contenedores autónomos** - no dependen de Swarm para seguir corriendo
- ✅ **Cada nodo es 100% autónomo** - tiene MongoDB, Redis, Backend y Frontend
- ✅ **Tolerancia a split-brain** - si la red se divide, cada lado sigue funcionando
- ✅ **Control manual** - puedes detener/iniciar nodos individualmente para demos
- ✅ **CoreDNS + Load Balancer** en cada máquina para redundancia

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLUSTER DISTRISEARCH                              │
│                    (Red Overlay: distrisearch-network)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Máquina A (192.168.1.11)                   Máquina B (192.168.1.13)       │
│  richard-VirtualBox                          abel-VirtualBox                │
│                                                                             │
│  ┌───────────────────┐                       ┌───────────────────┐         │
│  │ 🔀 Load Balancer  │                       │ 🔀 Load Balancer  │         │
│  │    Puerto 443     │                       │    Puerto 443     │         │
│  └───────────────────┘                       └───────────────────┘         │
│                                                                             │
│  ┌───────────────────┐                       ┌───────────────────┐         │
│  │ 📡 CoreDNS        │                       │ 📡 CoreDNS        │         │
│  │    Puerto 5353    │                       │    Puerto 5353    │         │
│  └───────────────────┘                       └───────────────────┘         │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐       │
│  │  🖥️ Node-1        │  │  🖥️ Node-2        │  │  🖥️ Node-3        │       │
│  │  ┌─────────────┐  │  │  ┌─────────────┐  │  │  ┌─────────────┐  │       │
│  │  │ MongoDB     │  │  │  │ MongoDB     │  │  │  │ MongoDB     │  │       │
│  │  │ Redis       │←─┼──┼──│ Redis       │←─┼──┼──│ Redis       │  │       │
│  │  │ Backend     │  │  │  │ Backend     │  │  │  │ Backend     │  │       │
│  │  │ Frontend    │  │  │  │ Frontend    │  │  │  │ Frontend    │  │       │
│  │  └─────────────┘  │  │  └─────────────┘  │  │  └─────────────┘  │       │
│  │  API: 8001        │  │  API: 8002        │  │  API: 8003        │       │
│  │  HTTP: 8081       │  │  HTTP: 8082       │  │  HTTP: 8083       │       │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘       │
│                                                                             │
│  ←────────────────── SWARM OVERLAY NETWORK ──────────────────→             │
│                     (10.10.0.0/24 cifrada)                                  │
└─────────────────────────────────────────────────────────────────────────────┘

COMUNICACIÓN ENTRE NODOS:
  - Red overlay de Swarm para comunicación IP directa
  - BULLY Algorithm para elección de líder (nivel aplicación)
  - Cada nodo conoce a los demás via BULLY_PEERS
  - Si hay partición, cada lado elige su propio líder (split-brain)

ACCESO AL SISTEMA:
  - https://192.168.1.11:443 (Load Balancer Máquina A)
  - https://192.168.1.13:443 (Load Balancer Máquina B)
```

---

## Pre-requisitos

### En ambas máquinas:

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Reiniciar sesión para aplicar grupo docker
```

### Inicializar Docker Swarm:

```bash
# En Máquina A (será el manager):
docker swarm init --advertise-addr 192.168.1.11

# Copiar el comando 'docker swarm join' que se muestra

# En Máquina B:
docker swarm join --token <TOKEN> 192.168.1.11:2377
```

### Verificar conectividad:

```bash
# Desde Máquina A
ping 192.168.1.13
docker node ls  # Debería mostrar ambos nodos

# Desde Máquina B
ping 192.168.1.11
```

---

## Guía Rápida

### Últimos pasos (copy/paste)

En Máquina A (manager):

```bash
cd ~/Escritorio/DistriSearch/DistriSearch/deploy/standalone
chmod +x *.sh

docker swarm init --advertise-addr 192.168.1.11
./init-swarm-network.sh

./build-image.sh
./transfer-image.sh richard@192.168.1.13

./deploy-machine-a.sh
./status.sh
```

En Máquina B:

```bash
docker swarm join --token <TOKEN> 192.168.1.11:2377
docker load -i ~/distrisearch-node-standalone.tar

cd ~/Escritorio/DistriSearch/DistriSearch/deploy/standalone
./deploy-machine-b.sh
./status.sh
```

### 1. Inicializar Swarm y crear red overlay (Máquina A - Manager)

```bash
cd DistriSearch/deploy/standalone
chmod +x *.sh

# Inicializar Swarm (si no está hecho)
docker swarm init --advertise-addr 192.168.1.11

# Crear red overlay
./init-swarm-network.sh
```

### 2. Unir Máquina B al Swarm

```bash
# En Máquina B - usar el token mostrado en el paso anterior
docker swarm join --token <TOKEN> 192.168.1.11:2377
```

### 3. Construir imagen (en Máquina A)

```bash
./build-image.sh
```

### 4. Transferir imagen a Máquina B

```bash
./transfer-image.sh richard@192.168.1.13

# En Máquina B:
docker load -i ~/distrisearch-node-standalone.tar
```

### 5. Desplegar TODO

```bash
# En Máquina A (despliega: CoreDNS, LoadBalancer, Node-1, Node-2):
./deploy-machine-a.sh

# En Máquina B (despliega: CoreDNS, LoadBalancer, Node-3):
./deploy-machine-b.sh
```

### 6. Verificar estado

```bash
./status.sh

# Acceder al sistema
firefox https://192.168.1.11:443   # Via Load Balancer Máquina A
firefox https://192.168.1.13:443   # Via Load Balancer Máquina B
```

---

## Despliegue Paso a Paso

### Paso 1: Inicializar Docker Swarm

En la Máquina A (192.168.1.11) - será el **manager**:

```bash
# Inicializar Swarm
docker swarm init --advertise-addr 192.168.1.11

# Esto mostrará un comando como:
# docker swarm join --token SWMTKN-1-xxx 192.168.1.11:2377
# GUARDA ESTE COMANDO
```

En la Máquina B (192.168.1.13):

```bash
# Unirse al Swarm
docker swarm join --token SWMTKN-1-xxx 192.168.1.11:2377
```

Verificar (desde Máquina A):

```bash
docker node ls
# Debería mostrar 2 nodos: un "Leader" y un "Reachable"
```

### Paso 2: Crear red overlay

En la Máquina A (manager):

```bash
cd ~/Escritorio/DistriSearch/DistriSearch/deploy/standalone
chmod +x *.sh

# Crear la red overlay (SOLO desde el manager)
./init-swarm-network.sh
```

### Paso 3: Construir la imagen Docker

En la Máquina A:

```bash
# Construir la imagen (puede tomar 5-10 minutos)
./build-image.sh

# Verificar que la imagen se creó
docker images | grep distrisearch
```

### Paso 4: Transferir imagen a Máquina B

```bash
# Exportar y transferir via SCP
./transfer-image.sh richard@192.168.1.13

# O manualmente:
docker save distrisearch/node:standalone -o distrisearch-node-standalone.tar
scp distrisearch-node-standalone.tar richard@192.168.1.13:~/
```

En la Máquina B (192.168.1.13):

```bash
# Cargar la imagen
cd ~
docker load -i distrisearch-node-standalone.tar

# Verificar
docker images | grep distrisearch
```

### Paso 3: Desplegar Nodos en Máquina A

```bash
# En Máquina A (192.168.1.11)
cd ~/Escritorio/DistriSearch/DistriSearch/deploy/standalone

# Desplegar nodos 1 y 2
./deploy-machine-a.sh
```

Esto creará:
- `distrisearch-node-node-1` en puertos 8001, 8081, 4431
- `distrisearch-node-node-2` en puertos 8002, 8082, 4432

### Paso 4: Desplegar Nodo en Máquina B

Primero, copiar los scripts a Máquina B:

```bash
# Desde Máquina A
scp -r ~/Escritorio/DistriSearch/DistriSearch/deploy/standalone richard@192.168.1.13:~/
```

En la Máquina B:

```bash
cd ~/standalone
chmod +x *.sh

# Desplegar nodo 3
./deploy-machine-b.sh
```

### Paso 5: Verificar el Cluster

```bash
# Ver estado de contenedores
docker ps | grep distrisearch

# Verificar salud de nodos
./status.sh

# Ver logs de un nodo específico
docker logs -f distrisearch-node-node-1
```

---

## Control Manual de Nodos

### Ver todos los nodos

```bash
docker ps -a | grep distrisearch
```

### Detener un nodo (simular caída)

```bash
# Detener Node-1
docker stop distrisearch-node-node-1

# Detener Node-2
docker stop distrisearch-node-node-2

# Detener Node-3 (en Máquina B)
docker stop distrisearch-node-node-3
```

### Reiniciar un nodo

```bash
docker start distrisearch-node-node-1
```

### Ver logs en tiempo real

```bash
docker logs -f distrisearch-node-node-1
```

### Acceder al shell del contenedor

```bash
docker exec -it distrisearch-node-node-1 bash

# Dentro del contenedor:
# Ver procesos
ps aux

# Ver estado de MongoDB
mongo --eval "db.serverStatus()"

# Ver estado de Redis
redis-cli ping
```

### Eliminar un nodo completamente

```bash
docker rm -f distrisearch-node-node-1
```

---

## Escenarios de Prueba

### Escenario 1: Funcionamiento Normal

1. Todos los nodos están corriendo
2. Acceder a cualquier frontend: http://192.168.1.11:8081
3. Subir un documento
4. Verificar que se replica a los otros nodos

### Escenario 2: Caída de un Nodo

```bash
# 1. Detener Node-1
docker stop distrisearch-node-node-1

# 2. Verificar que el sistema sigue funcionando
curl http://192.168.1.11:8002/api/v1/health/live

# 3. Subir un documento desde otro nodo

# 4. Reiniciar Node-1
docker start distrisearch-node-node-1

# 5. Verificar que sincroniza los datos nuevos
```

### Escenario 3: Partición de Red (Split-Brain)

```bash
# 1. En Máquina A, bloquear tráfico hacia Máquina B
sudo iptables -A OUTPUT -d 192.168.1.13 -j DROP
sudo iptables -A INPUT -s 192.168.1.13 -j DROP

# 2. Verificar que ambos lados siguen funcionando:
#    - Máquina A: Nodos 1 y 2 funcionan juntos
#    - Máquina B: Nodo 3 funciona solo

# 3. Subir documentos en ambos lados

# 4. Restaurar la red
sudo iptables -D OUTPUT -d 192.168.1.13 -j DROP
sudo iptables -D INPUT -s 192.168.1.13 -j DROP

# 5. Verificar sincronización de datos
```

### Escenario 4: Caída del Líder

```bash
# 1. Ver quién es el líder actual
curl http://192.168.1.11:8001/api/v1/cluster/status

# 2. Detener el nodo líder
docker stop distrisearch-node-node-X

# 3. Verificar que se elige nuevo líder
curl http://192.168.1.11:8002/api/v1/cluster/status

# 4. El sistema debe seguir funcionando
```

---

## Troubleshooting

### El contenedor no inicia

```bash
# Ver logs
docker logs distrisearch-node-node-1

# Verificar que los puertos estén libres
sudo netstat -tlnp | grep 8001
```

### MongoDB no inicia dentro del contenedor

```bash
docker exec -it distrisearch-node-node-1 bash
cat /var/log/mongodb/mongod.log
cat /var/log/supervisor/mongodb-stderr.log
```

### Los nodos no se ven entre sí

```bash
# Verificar conectividad
ping 192.168.1.13

# Verificar que BULLY_PEERS esté configurado
docker exec distrisearch-node-node-1 env | grep BULLY

# Verificar que el puerto API esté accesible
curl http://192.168.1.13:8003/api/v1/health/live
```

### Limpiar todo y empezar de nuevo

```bash
# Detener y eliminar todos los contenedores
docker rm -f $(docker ps -aq --filter "name=distrisearch-node-")

# Eliminar datos persistentes
sudo rm -rf /var/lib/distrisearch

# Eliminar imagen
docker rmi distrisearch/node:standalone
```

---

## URLs de Acceso

### Máquina A (192.168.1.11)

| Nodo | API | Frontend HTTP | Frontend HTTPS |
|------|-----|---------------|----------------|
| Node-1 | http://192.168.1.11:8001 | http://192.168.1.11:8081 | https://192.168.1.11:4431 |
| Node-2 | http://192.168.1.11:8002 | http://192.168.1.11:8082 | https://192.168.1.11:4432 |

### Máquina B (192.168.1.13)

| Nodo | API | Frontend HTTP | Frontend HTTPS |
|------|-----|---------------|----------------|
| Node-3 | http://192.168.1.13:8003 | http://192.168.1.13:8083 | https://192.168.1.13:4433 |

---

## Notas Importantes

1. **Los nodos NO se reinician automáticamente** (`restart=no`). Esto es intencional para que puedas controlar manualmente los nodos durante la revisión.

2. **Cada contenedor es completamente autónomo**. Tiene su propio MongoDB, Redis, Backend y Frontend.

3. **Los datos se persisten** en `/var/lib/distrisearch/<node-id>/`. Si reinicias un contenedor, los datos se mantienen.

4. **El algoritmo BULLY** se usa para elección de líder. Cuando un nodo se une o detecta que el líder cayó, inicia una elección.

5. **Split-brain funciona** porque cada nodo tiene sus propios datos locales. Cuando la red se restaura, los nodos sincronizan datos.
