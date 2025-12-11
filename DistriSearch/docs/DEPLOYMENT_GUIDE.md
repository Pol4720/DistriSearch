# 🚀 Guía de Despliegue DistriSearch en Linux con Docker Swarm

## Índice

1. [Visión General de la Arquitectura](#visión-general-de-la-arquitectura)
2. [Requisitos Previos](#requisitos-previos)
3. [Configuración del Nodo Manager (Primer Nodo)](#configuración-del-nodo-manager-primer-nodo)
4. [Añadir Nodos Worker Gradualmente](#añadir-nodos-worker-gradualmente)
5. [Configuración de Red y Conectividad](#configuración-de-red-y-conectividad)
6. [Despliegue del Stack](#despliegue-del-stack)
7. [Escalado Dinámico](#escalado-dinámico)
8. [Monitoreo y Mantenimiento](#monitoreo-y-mantenimiento)
9. [Solución de Problemas](#solución-de-problemas)
10. [Scripts de Automatización](#scripts-de-automatización)

---

## Visión General de la Arquitectura

DistriSearch utiliza una arquitectura distribuida con Docker Swarm que consiste en:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOCKER SWARM CLUSTER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │   Manager   │  │   Manager   │  │   Manager   │  (Alta disponibilidad)   │
│  │    Node 1   │  │    Node 2   │  │    Node 3   │                          │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │                          │
│  │  │Master │  │  │  │Master │  │  │  │Master │  │  Raft Consensus          │
│  │  │ API   │  │  │  │ API   │  │  │  │ API   │  │                          │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │                          │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │                          │
│  │  │MongoDB│  │  │  │MongoDB│  │  │  │MongoDB│  │  Replica Set             │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │                          │
│  │  ┌───────┐  │  │  ┌───────┐  │  │                                        │
│  │  │ Nginx │  │  │  │ Nginx │  │  │  Load Balancer                         │
│  │  │  LB   │  │  │  │  LB   │  │  │                                        │
│  │  └───────┘  │  │  └───────┘  │  │                                        │
│  └─────────────┘  └─────────────┘  └─────────────┘                          │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Worker    │  │   Worker    │  │   Worker    │  │   Worker    │         │
│  │    Node 1   │  │    Node 2   │  │    Node 3   │  │    Node N   │         │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │         │
│  │  │ Slave │  │  │  │ Slave │  │  │  │ Slave │  │  │  │ Slave │  │         │
│  │  │Backend│  │  │  │Backend│  │  │  │Backend│  │  │  │Backend│  │         │
│  │  │+Front │  │  │  │+Front │  │  │  │+Front │  │  │  │+Front │  │         │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                                              │
│                    ↓↓↓ Los workers se añaden dinámicamente ↓↓↓              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Componentes Principales

| Componente | Rol | Puerto | Ubicación |
|------------|-----|--------|-----------|
| **Master** | Coordinador Raft, gestión de cluster | 8001 | Manager nodes |
| **Slave** | Backend API + Frontend React | 80, 8000 | Worker nodes |
| **Load Balancer** | Balanceo de carga, TLS termination | 80, 443 | Manager nodes |
| **MongoDB** | Base de datos (Replica Set) | 27017 | Manager nodes |
| **Redis** | Cache distribuido | 6379 | Manager nodes |
| **CoreDNS** | DNS interno de respaldo | 53 | Cualquier nodo |

---

## Requisitos Previos

### Requisitos de Hardware (por nodo)

| Tipo de Nodo | CPU | RAM | Disco | Red |
|--------------|-----|-----|-------|-----|
| **Manager** | 2+ cores | 4GB+ | 50GB SSD | 1Gbps |
| **Worker** | 2+ cores | 4GB+ | 100GB SSD | 1Gbps |

### Requisitos de Software

```bash
# Sistema Operativo
Ubuntu 22.04 LTS / Debian 12 / RHEL 8+ / Rocky Linux 8+

# Docker Engine 24.0+
# Docker Compose v2.x (opcional para desarrollo)
```

### Puertos Requeridos

Asegúrate de que los siguientes puertos estén abiertos entre todos los nodos:

```bash
# Docker Swarm - OBLIGATORIOS
TCP 2377   # Comunicación de gestión del cluster
TCP 7946   # Comunicación entre nodos (control plane)
UDP 7946   # Comunicación entre nodos (control plane)
UDP 4789   # Overlay network traffic (VXLAN)

# Aplicación DistriSearch
TCP 80     # HTTP (Load Balancer)
TCP 443    # HTTPS (Load Balancer)
TCP 8000   # Backend API (interno)
TCP 8001   # Master API (interno)
TCP 27017  # MongoDB (interno)
TCP 6379   # Redis (interno)
```

---

## Configuración del Nodo Manager (Primer Nodo)

### Paso 1: Instalar Docker en el Primer Nodo

```bash
#!/bin/bash
# Script: install_docker.sh
# Ejecutar en cada máquina Linux

# Actualizar sistema
sudo apt-get update && sudo apt-get upgrade -y

# Instalar dependencias
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Añadir clave GPG oficial de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Configurar repositorio
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Configurar usuario (no usar sudo con docker)
sudo usermod -aG docker $USER

# Habilitar Docker al inicio
sudo systemctl enable docker
sudo systemctl start docker

# Verificar instalación
docker --version
docker compose version
```

### Paso 2: Inicializar el Swarm (Solo en el PRIMER Manager)

```bash
#!/bin/bash
# Script: init_swarm_manager.sh
# Ejecutar SOLO en el primer nodo manager

# Obtener IP del nodo (ajustar interfaz según tu red)
NODE_IP=$(hostname -I | awk '{print $1}')

# También puedes especificar la IP manualmente:
# NODE_IP="192.168.1.100"

echo "=== Inicializando Docker Swarm ==="
echo "IP del nodo: $NODE_IP"

# Inicializar Swarm
docker swarm init --advertise-addr $NODE_IP

# Guardar tokens para unir otros nodos
echo ""
echo "=== GUARDA ESTOS TOKENS (los necesitarás para añadir más nodos) ==="
echo ""
echo "--- Token para añadir MANAGERS ---"
docker swarm join-token manager
echo ""
echo "--- Token para añadir WORKERS ---"
docker swarm join-token worker
echo ""

# Mostrar estado del cluster
docker node ls
```

### Paso 3: Crear Secretos y Configuraciones

```bash
#!/bin/bash
# Script: setup_secrets.sh
# Ejecutar en un nodo manager

# Crear directorio temporal para secretos
mkdir -p /tmp/distrisearch-secrets

# Generar contraseña MongoDB
echo "$(openssl rand -base64 32)" > /tmp/distrisearch-secrets/mongodb-password

# Generar secreto JWT
echo "$(openssl rand -base64 64)" > /tmp/distrisearch-secrets/jwt-secret

# Generar keyfile para MongoDB Replica Set
openssl rand -base64 756 > /tmp/distrisearch-secrets/mongodb-keyfile

# Crear secretos en Docker Swarm
docker secret create mongodb-password /tmp/distrisearch-secrets/mongodb-password
docker secret create jwt-secret /tmp/distrisearch-secrets/jwt-secret
docker secret create mongodb-keyfile /tmp/distrisearch-secrets/mongodb-keyfile

# (Opcional) Crear certificados TLS autofirmados para desarrollo
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /tmp/distrisearch-secrets/tls.key \
    -out /tmp/distrisearch-secrets/tls.crt \
    -subj "/CN=distrisearch.local"

docker secret create tls-cert /tmp/distrisearch-secrets/tls.crt
docker secret create tls-key /tmp/distrisearch-secrets/tls.key

# Limpiar archivos temporales
rm -rf /tmp/distrisearch-secrets

# Verificar secretos creados
echo "=== Secretos creados ==="
docker secret ls
```

### Paso 4: Crear Redes Overlay

```bash
#!/bin/bash
# Script: create_networks.sh
# Ejecutar en un nodo manager

# Red principal para servicios internos
docker network create \
    --driver overlay \
    --attachable \
    --subnet 10.0.10.0/24 \
    distrisearch-network

# Red para ingress (load balancer)
docker network create \
    --driver overlay \
    --attachable \
    ingress-network

echo "=== Redes creadas ==="
docker network ls | grep distrisearch
```

---

## Añadir Nodos Worker Gradualmente

### Filosofía: Los Nodos Llegan Poco a Poco

DistriSearch está diseñado para que los nodos se unan al cluster de forma dinámica. No es necesario tener todos los nodos listos desde el inicio.

```
Tiempo ──────────────────────────────────────────────────────────────►

     ┌─────────┐
T0:  │Manager 1│  ← Inicia el cluster solo
     └─────────┘

     ┌─────────┐     ┌─────────┐
T1:  │Manager 1│────│Worker 1 │  ← Primer worker se une
     └─────────┘     └─────────┘

     ┌─────────┐     ┌─────────┐     ┌─────────┐
T2:  │Manager 1│────│Worker 1 │────│Worker 2 │  ← Segundo worker
     └─────────┘     └─────────┘     └─────────┘

     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
T3:  │Manager 1│────│Worker 1 │────│Worker 2 │────│Worker N │  ← Más workers...
     └─────────┘     └─────────┘     └─────────┘     └─────────┘

                     El sistema escala automáticamente las réplicas
```

### Script para Añadir un Nodo Worker

Ejecuta este script en **cada nueva máquina** que quieras añadir como worker:

```bash
#!/bin/bash
# Script: join_as_worker.sh
# Ejecutar en cada nueva máquina que se unirá como worker

set -e

# ══════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN - MODIFICAR ESTOS VALORES
# ══════════════════════════════════════════════════════════════════════

# IP del nodo manager principal
MANAGER_IP="192.168.1.100"

# Token de worker (obtenerlo del manager con: docker swarm join-token worker)
WORKER_TOKEN="SWMTKN-1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ══════════════════════════════════════════════════════════════════════
# INSTALACIÓN DE DOCKER (si no está instalado)
# ══════════════════════════════════════════════════════════════════════

install_docker() {
    if command -v docker &> /dev/null; then
        echo "Docker ya está instalado: $(docker --version)"
        return 0
    fi

    echo "Instalando Docker..."
    
    sudo apt-get update
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    sudo usermod -aG docker $USER
    sudo systemctl enable docker
    sudo systemctl start docker
}

# ══════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL SISTEMA
# ══════════════════════════════════════════════════════════════════════

configure_system() {
    echo "Configurando sistema..."
    
    # Deshabilitar swap (recomendado para producción)
    sudo swapoff -a
    sudo sed -i '/ swap / s/^/#/' /etc/fstab

    # Configurar límites del sistema
    cat << EOF | sudo tee /etc/security/limits.d/docker.conf
* soft nofile 65536
* hard nofile 65536
* soft nproc 65536
* hard nproc 65536
EOF

    # Parámetros de kernel para networking
    cat << EOF | sudo tee /etc/sysctl.d/99-docker.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 3
EOF
    
    sudo sysctl --system
}

# ══════════════════════════════════════════════════════════════════════
# CONFIGURAR FIREWALL
# ══════════════════════════════════════════════════════════════════════

configure_firewall() {
    echo "Configurando firewall..."
    
    # Si usa UFW
    if command -v ufw &> /dev/null; then
        sudo ufw allow 2377/tcp   # Swarm management
        sudo ufw allow 7946/tcp   # Node communication
        sudo ufw allow 7946/udp   # Node communication
        sudo ufw allow 4789/udp   # Overlay network
        sudo ufw allow 8000/tcp   # Backend API
        sudo ufw allow 80/tcp     # HTTP
        sudo ufw allow 443/tcp    # HTTPS
        sudo ufw reload
    fi

    # Si usa firewalld
    if command -v firewall-cmd &> /dev/null; then
        sudo firewall-cmd --permanent --add-port=2377/tcp
        sudo firewall-cmd --permanent --add-port=7946/tcp
        sudo firewall-cmd --permanent --add-port=7946/udp
        sudo firewall-cmd --permanent --add-port=4789/udp
        sudo firewall-cmd --permanent --add-port=8000/tcp
        sudo firewall-cmd --permanent --add-port=80/tcp
        sudo firewall-cmd --permanent --add-port=443/tcp
        sudo firewall-cmd --reload
    fi
}

# ══════════════════════════════════════════════════════════════════════
# UNIRSE AL SWARM
# ══════════════════════════════════════════════════════════════════════

join_swarm() {
    echo "Uniéndose al Swarm..."
    
    # Verificar conectividad con el manager
    if ! ping -c 3 $MANAGER_IP &> /dev/null; then
        echo "ERROR: No se puede alcanzar el manager en $MANAGER_IP"
        echo "Verifica la conectividad de red y el firewall"
        exit 1
    fi

    # Si ya está en un swarm, salir primero
    if docker info | grep -q "Swarm: active"; then
        echo "Este nodo ya está en un Swarm. Saliendo..."
        docker swarm leave --force || true
    fi

    # Unirse al Swarm
    docker swarm join --token $WORKER_TOKEN $MANAGER_IP:2377

    echo ""
    echo "=== Nodo unido exitosamente al Swarm ==="
    echo "El nodo ahora está disponible para recibir tareas"
    docker info | grep -A 5 "Swarm"
}

# ══════════════════════════════════════════════════════════════════════
# EJECUCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════

main() {
    echo "═══════════════════════════════════════════════════════════"
    echo "   DistriSearch - Configuración de Nodo Worker"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    
    install_docker
    configure_system
    configure_firewall
    join_swarm
    
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "   ¡Configuración completada!"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Próximos pasos:"
    echo "1. Verifica en el manager: docker node ls"
    echo "2. El servicio slave se desplegará automáticamente"
    echo "3. Monitorea: docker service ps distrisearch_slave"
}

main "$@"
```

### Obtener el Token de Worker (en el Manager)

```bash
# Ejecutar en cualquier nodo manager para obtener el comando de unión
docker swarm join-token worker

# Salida ejemplo:
# docker swarm join --token SWMTKN-1-0abc123... 192.168.1.100:2377
```

### Verificar Nodos en el Cluster (en el Manager)

```bash
# Ver todos los nodos del cluster
docker node ls

# Salida ejemplo:
# ID                            HOSTNAME     STATUS    AVAILABILITY   MANAGER STATUS
# abc123 *                      manager-1    Ready     Active         Leader
# def456                        worker-1     Ready     Active         
# ghi789                        worker-2     Ready     Active         
```

---

## Configuración de Red y Conectividad

### Escenario 1: Red Local (LAN)

Si todos los nodos están en la misma red local:

```bash
# Configuración simple - usar IP privada
MANAGER_IP="192.168.1.100"
docker swarm init --advertise-addr $MANAGER_IP
```

### Escenario 2: Múltiples Subredes

Si los nodos están en diferentes subredes (ej: diferentes oficinas):

```bash
# En el manager - especificar también la interfaz de datos
docker swarm init \
    --advertise-addr 192.168.1.100 \
    --data-path-addr 192.168.1.100

# Configurar VPN o túnel entre subredes
# Los puertos 2377, 7946, 4789 deben ser accesibles
```

### Escenario 3: Cloud (AWS/GCP/Azure)

```bash
# Usar IP privada de la instancia
PRIVATE_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)  # AWS
docker swarm init --advertise-addr $PRIVATE_IP

# Asegurar que Security Groups/Firewall Rules permitan:
# - TCP 2377 (swarm management)
# - TCP/UDP 7946 (container network discovery)
# - UDP 4789 (overlay network)
```

### Script de Diagnóstico de Conectividad

```bash
#!/bin/bash
# Script: check_connectivity.sh
# Verificar conectividad entre nodos

MANAGER_IP="${1:-192.168.1.100}"

echo "=== Verificando conectividad con $MANAGER_IP ==="

# Test ICMP
echo -n "Ping: "
ping -c 1 $MANAGER_IP &> /dev/null && echo "OK" || echo "FAIL"

# Test puertos
for port in 2377 7946; do
    echo -n "TCP $port: "
    timeout 3 bash -c "echo > /dev/tcp/$MANAGER_IP/$port" 2>/dev/null && echo "OK" || echo "FAIL"
done

# Test DNS
echo -n "DNS resolution: "
host $MANAGER_IP &> /dev/null && echo "OK" || echo "FAIL (puede estar bien)"

echo ""
echo "Si hay FAILs, verifica:"
echo "1. Firewall/Security Groups"
echo "2. Enrutamiento de red"
echo "3. VPN/Túnel si aplica"
```

---

## Despliegue del Stack

### Paso 1: Preparar Imágenes Docker

```bash
#!/bin/bash
# Script: build_and_push.sh
# Construir y publicar imágenes (ejecutar donde está el código)

# Configuración de registry (usar Docker Hub o registry privado)
REGISTRY="your-registry.com"  # o "docker.io/tu-usuario"
VERSION="latest"

cd /path/to/DistriSearch

# Construir imágenes
echo "Construyendo imágenes..."

# Master
docker build -t $REGISTRY/distrisearch/master:$VERSION \
    -f docker/master/Dockerfile .

# Slave
docker build -t $REGISTRY/distrisearch/slave:$VERSION \
    -f docker/slave/Dockerfile .

# Load Balancer
docker build -t $REGISTRY/distrisearch/load-balancer:$VERSION \
    -f docker/load-balancer/Dockerfile docker/load-balancer/

# CoreDNS
docker build -t $REGISTRY/distrisearch/coredns:$VERSION \
    -f docker/coredns/Dockerfile docker/coredns/

# DNS Sync
docker build -t $REGISTRY/distrisearch/dns-sync:$VERSION \
    -f docker/dns-sync/Dockerfile docker/dns-sync/

# Publicar imágenes
echo "Publicando imágenes..."
docker push $REGISTRY/distrisearch/master:$VERSION
docker push $REGISTRY/distrisearch/slave:$VERSION
docker push $REGISTRY/distrisearch/load-balancer:$VERSION
docker push $REGISTRY/distrisearch/coredns:$VERSION
docker push $REGISTRY/distrisearch/dns-sync:$VERSION

echo "¡Imágenes listas!"
```

### Paso 2: Desplegar el Stack

```bash
#!/bin/bash
# Script: deploy_stack.sh
# Desplegar el stack completo

STACK_NAME="distrisearch"

# Verificar que estamos en un manager
if ! docker info | grep -q "Is Manager: true"; then
    echo "ERROR: Este script debe ejecutarse en un nodo manager"
    exit 1
fi

# Verificar secretos
echo "Verificando secretos..."
for secret in mongodb-password jwt-secret mongodb-keyfile tls-cert tls-key; do
    if ! docker secret ls | grep -q $secret; then
        echo "ERROR: Secreto '$secret' no encontrado. Ejecuta setup_secrets.sh primero"
        exit 1
    fi
done

# Crear configs
echo "Creando configuraciones..."
docker config create nginx-config ./docker/load-balancer/nginx.conf 2>/dev/null || true
docker config create coredns-config ./docker/coredns/Corefile 2>/dev/null || true

# Desplegar stack
echo "Desplegando stack $STACK_NAME..."
docker stack deploy -c docker/docker-compose.swarm.yml $STACK_NAME

# Esperar a que los servicios estén listos
echo "Esperando servicios..."
sleep 10

# Mostrar estado
docker stack services $STACK_NAME
```

### Paso 3: Verificar Despliegue

```bash
#!/bin/bash
# Script: verify_deployment.sh

STACK_NAME="distrisearch"

echo "=== Estado de Servicios ==="
docker stack services $STACK_NAME

echo ""
echo "=== Tareas en Ejecución ==="
docker stack ps $STACK_NAME --filter "desired-state=running"

echo ""
echo "=== Health Checks ==="
for service in master slave load-balancer mongodb redis; do
    echo -n "$service: "
    if docker service ps ${STACK_NAME}_${service} --filter "desired-state=running" -q | head -1 | xargs docker inspect --format='{{.Status.State}}' 2>/dev/null | grep -q "running"; then
        echo "✓ Running"
    else
        echo "✗ Not ready"
    fi
done
```

---

## Escalado Dinámico

### Escalar Servicios Manualmente

```bash
# Escalar slaves (añadir más capacidad de búsqueda)
docker service scale distrisearch_slave=5

# Escalar masters (para HA - usar números impares: 3, 5, 7)
docker service scale distrisearch_master=5

# Escalar load balancers
docker service scale distrisearch_load-balancer=3
```

### Auto-escalado con Nuevo Worker

Cuando un nuevo worker se une al cluster, Docker Swarm automáticamente:

1. Detecta el nuevo nodo disponible
2. Programa tareas pendientes en el nuevo nodo
3. Redistribuye la carga si es necesario

```bash
# Ver cómo se distribuyen los slaves
docker service ps distrisearch_slave

# Forzar redistribución (opcional)
docker service update --force distrisearch_slave
```

### Script de Monitoreo de Capacidad

```bash
#!/bin/bash
# Script: monitor_capacity.sh

echo "=== Capacidad del Cluster ==="

# Nodos totales
TOTAL_NODES=$(docker node ls -q | wc -l)
WORKERS=$(docker node ls --filter "role=worker" -q | wc -l)
MANAGERS=$(docker node ls --filter "role=manager" -q | wc -l)

echo "Nodos totales: $TOTAL_NODES (Managers: $MANAGERS, Workers: $WORKERS)"

# Servicios
SLAVE_REPLICAS=$(docker service ls --filter "name=distrisearch_slave" --format "{{.Replicas}}")
echo "Slaves desplegados: $SLAVE_REPLICAS"

# Recursos
echo ""
echo "=== Uso de Recursos por Nodo ==="
docker node ls --format "{{.Hostname}}" | while read hostname; do
    echo "--- $hostname ---"
    docker node ps $hostname --filter "desired-state=running" --format "{{.Name}}"
done
```

---

## Monitoreo y Mantenimiento

### Ver Logs de Servicios

```bash
# Logs del master
docker service logs distrisearch_master -f --tail 100

# Logs de un slave específico
docker service logs distrisearch_slave -f --tail 100

# Logs de todos los contenedores de un servicio
docker service logs distrisearch_slave --raw
```

### Health Check Manual

```bash
#!/bin/bash
# Script: healthcheck.sh

LOAD_BALANCER_IP=$(docker service inspect distrisearch_load-balancer \
    --format '{{range .Endpoint.VirtualIPs}}{{.Addr}}{{end}}' | cut -d'/' -f1)

echo "=== Health Checks ==="

# API Health
echo -n "API: "
curl -sf http://$LOAD_BALANCER_IP/api/v1/health && echo "OK" || echo "FAIL"

# Cluster status
echo -n "Cluster: "
curl -sf http://$LOAD_BALANCER_IP/api/v1/cluster/status && echo "" || echo "FAIL"

# Frontend
echo -n "Frontend: "
curl -sf http://$LOAD_BALANCER_IP/ -o /dev/null && echo "OK" || echo "FAIL"
```

### Actualizar Servicios (Rolling Update)

```bash
#!/bin/bash
# Script: update_service.sh

SERVICE="distrisearch_slave"
NEW_IMAGE="your-registry.com/distrisearch/slave:v2.0"

echo "Actualizando $SERVICE a $NEW_IMAGE..."

docker service update \
    --image $NEW_IMAGE \
    --update-parallelism 1 \
    --update-delay 30s \
    --update-failure-action rollback \
    $SERVICE

echo "Actualización completada"
docker service ps $SERVICE
```

### Mantenimiento de Nodos

```bash
# Poner nodo en mantenimiento (drenar tareas)
docker node update --availability drain worker-1

# Restaurar nodo
docker node update --availability active worker-1

# Remover nodo del cluster (desde el nodo a remover)
docker swarm leave

# Remover nodo desde el manager (si el nodo ya no responde)
docker node rm worker-1 --force
```

---

## Solución de Problemas

### Problema: El Worker No Se Une al Swarm

```bash
# Verificar conectividad
ping $MANAGER_IP

# Verificar puertos
nc -zv $MANAGER_IP 2377

# Ver logs de Docker
journalctl -u docker -f

# Regenerar token si expiró
docker swarm join-token worker
```

### Problema: Servicio No Inicia

```bash
# Ver estado detallado
docker service ps distrisearch_slave --no-trunc

# Ver logs de error
docker service logs distrisearch_slave 2>&1 | grep -i error

# Inspeccionar servicio
docker service inspect distrisearch_slave --pretty
```

### Problema: Red Overlay No Funciona

```bash
# Verificar redes
docker network ls

# Inspeccionar red
docker network inspect distrisearch-network

# Recrear red (si está corrupta)
docker network rm distrisearch-network
docker network create --driver overlay --attachable distrisearch-network
docker stack deploy -c docker-compose.swarm.yml distrisearch
```

### Problema: MongoDB No Forma Replica Set

```bash
# Conectar a MongoDB
docker exec -it $(docker ps -q -f name=distrisearch_mongodb) mongosh

# Verificar estado del replica set
rs.status()

# Inicializar manualmente si es necesario
rs.initiate({
    _id: "rs0",
    members: [
        { _id: 0, host: "mongodb:27017" }
    ]
})
```

### Comandos de Diagnóstico Útiles

```bash
# Estado general del Swarm
docker info

# Listar todos los servicios
docker stack services distrisearch

# Ver todas las tareas (incluidas fallidas)
docker stack ps distrisearch --no-trunc

# Inspeccionar un nodo específico
docker node inspect worker-1 --pretty

# Ver recursos usados
docker stats

# Limpiar recursos no usados
docker system prune -a
```

---

## Scripts de Automatización

### Script Completo: setup_manager.sh

```bash
#!/bin/bash
# Script maestro para configurar el primer manager
# Uso: ./setup_manager.sh [ADVERTISE_IP]

set -e

ADVERTISE_IP="${1:-$(hostname -I | awk '{print $1}')}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "═══════════════════════════════════════════════════════════════"
echo "   DistriSearch - Configuración de Nodo Manager Principal"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "IP de anuncio: $ADVERTISE_IP"
echo ""

# 1. Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "[1/6] Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
else
    echo "[1/6] Docker ya instalado ✓"
fi

# 2. Inicializar Swarm
echo "[2/6] Inicializando Swarm..."
if docker info 2>/dev/null | grep -q "Swarm: active"; then
    echo "Swarm ya inicializado ✓"
else
    docker swarm init --advertise-addr $ADVERTISE_IP
fi

# 3. Crear secretos
echo "[3/6] Creando secretos..."
mkdir -p /tmp/ds-secrets
echo "$(openssl rand -base64 32)" > /tmp/ds-secrets/mongodb-password
echo "$(openssl rand -base64 64)" > /tmp/ds-secrets/jwt-secret
openssl rand -base64 756 > /tmp/ds-secrets/mongodb-keyfile
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /tmp/ds-secrets/tls.key -out /tmp/ds-secrets/tls.crt \
    -subj "/CN=distrisearch.local" 2>/dev/null

for secret in mongodb-password jwt-secret mongodb-keyfile; do
    docker secret create $secret /tmp/ds-secrets/$secret 2>/dev/null || true
done
docker secret create tls-cert /tmp/ds-secrets/tls.crt 2>/dev/null || true
docker secret create tls-key /tmp/ds-secrets/tls.key 2>/dev/null || true
rm -rf /tmp/ds-secrets

# 4. Crear redes
echo "[4/6] Creando redes..."
docker network create --driver overlay --attachable --subnet 10.0.10.0/24 distrisearch-network 2>/dev/null || true
docker network create --driver overlay --attachable ingress-network 2>/dev/null || true

# 5. Mostrar tokens
echo "[5/6] Información de unión al cluster:"
echo ""
echo "=== Para añadir MANAGERS ==="
docker swarm join-token manager
echo ""
echo "=== Para añadir WORKERS ==="
docker swarm join-token worker
echo ""

# 6. Estado final
echo "[6/6] Estado del cluster:"
docker node ls

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "   ¡Manager configurado exitosamente!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Próximos pasos:"
echo "1. Usa los comandos de arriba para añadir más nodos"
echo "2. Construye las imágenes: ./build_and_push.sh"
echo "3. Despliega el stack: docker stack deploy -c docker-compose.swarm.yml distrisearch"
```

### Script: add_worker_automated.sh

```bash
#!/bin/bash
# Script para añadir worker de forma automatizada
# Uso: ./add_worker_automated.sh <MANAGER_IP> <JOIN_TOKEN>

set -e

MANAGER_IP="$1"
JOIN_TOKEN="$2"

if [ -z "$MANAGER_IP" ] || [ -z "$JOIN_TOKEN" ]; then
    echo "Uso: $0 <MANAGER_IP> <JOIN_TOKEN>"
    echo "Ejemplo: $0 192.168.1.100 SWMTKN-1-xxx..."
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════"
echo "   DistriSearch - Añadiendo Worker al Cluster"
echo "═══════════════════════════════════════════════════════════════"

# Instalar Docker si es necesario
if ! command -v docker &> /dev/null; then
    echo "[1/3] Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    sudo systemctl enable docker
    sudo systemctl start docker
else
    echo "[1/3] Docker ya instalado ✓"
fi

# Configurar firewall
echo "[2/3] Configurando firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 2377/tcp
    sudo ufw allow 7946/tcp
    sudo ufw allow 7946/udp
    sudo ufw allow 4789/udp
    sudo ufw allow 80/tcp
    sudo ufw allow 8000/tcp
fi

# Unirse al Swarm
echo "[3/3] Uniéndose al Swarm..."
docker swarm leave --force 2>/dev/null || true
docker swarm join --token $JOIN_TOKEN $MANAGER_IP:2377

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "   ¡Worker añadido exitosamente!"
echo "═══════════════════════════════════════════════════════════════"
docker info | grep -A 3 "Swarm"
```

---

## Resumen de Comandos Frecuentes

```bash
# ═══════════════════════════════════════════════════════════════════
# GESTIÓN DEL CLUSTER
# ═══════════════════════════════════════════════════════════════════
docker swarm init --advertise-addr <IP>          # Inicializar swarm
docker swarm join-token worker                    # Obtener token worker
docker swarm join-token manager                   # Obtener token manager
docker node ls                                    # Listar nodos
docker node inspect <NODE> --pretty               # Inspeccionar nodo

# ═══════════════════════════════════════════════════════════════════
# GESTIÓN DEL STACK
# ═══════════════════════════════════════════════════════════════════
docker stack deploy -c docker-compose.swarm.yml distrisearch  # Desplegar
docker stack services distrisearch                # Ver servicios
docker stack ps distrisearch                      # Ver tareas
docker stack rm distrisearch                      # Eliminar stack

# ═══════════════════════════════════════════════════════════════════
# GESTIÓN DE SERVICIOS
# ═══════════════════════════════════════════════════════════════════
docker service ls                                 # Listar servicios
docker service scale distrisearch_slave=5         # Escalar servicio
docker service logs distrisearch_master -f        # Ver logs
docker service update --force distrisearch_slave  # Forzar redistribución

# ═══════════════════════════════════════════════════════════════════
# MANTENIMIENTO
# ═══════════════════════════════════════════════════════════════════
docker node update --availability drain <NODE>    # Drenar nodo
docker node update --availability active <NODE>   # Activar nodo
docker system prune -a                            # Limpiar recursos
```

---

## Checklist de Despliegue

- [ ] **Preparación**
  - [ ] Docker instalado en todas las máquinas
  - [ ] Puertos de firewall abiertos (2377, 7946, 4789)
  - [ ] Conectividad de red entre nodos verificada

- [ ] **Manager Principal**
  - [ ] Swarm inicializado
  - [ ] Secretos creados
  - [ ] Redes overlay creadas
  - [ ] Tokens de unión guardados

- [ ] **Workers**
  - [ ] Docker instalado
  - [ ] Firewall configurado
  - [ ] Unido al Swarm correctamente

- [ ] **Despliegue**
  - [ ] Imágenes construidas y publicadas
  - [ ] Stack desplegado
  - [ ] Servicios en estado "Running"
  - [ ] Health checks pasando

- [ ] **Verificación**
  - [ ] API responde en /api/v1/health
  - [ ] Frontend accesible
  - [ ] MongoDB replica set funcional
  - [ ] Logs sin errores críticos

---

**Última actualización:** Diciembre 2024  
**Versión de DistriSearch:** 1.0.0
