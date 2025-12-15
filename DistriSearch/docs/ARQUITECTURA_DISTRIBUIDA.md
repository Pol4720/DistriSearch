# Arquitectura del Sistema Distribuido - DistriSearch

## Despliegue con Docker Swarm y Servicio de Descubrimiento

---

## 1. Visión General del Sistema Distribuido

DistriSearch se despliega como un sistema distribuido orquestado mediante **Docker Swarm**, aprovechando sus capacidades nativas de descubrimiento de servicios, balanceo de carga y tolerancia a fallos. El sistema incluye un mecanismo de respaldo DNS para garantizar alta disponibilidad incluso cuando el DNS interno de Docker falla.

```
                                    ┌─────────────────────────────────┐
                                    │         CLIENTES EXTERNOS       │
                                    │      (Navegadores / APIs)       │
                                    └───────────────┬─────────────────┘
                                                    │
                                                    ▼
                              ┌─────────────────────────────────────────────┐
                              │            DOCKER SWARM CLUSTER             │
                              │  ┌───────────────────────────────────────┐  │
                              │  │         INGRESS NETWORK               │  │
                              │  │    (Routing Mesh + Load Balancer)     │  │
                              │  └───────────────────┬───────────────────┘  │
                              │                      │                      │
                              │  ┌───────────────────▼───────────────────┐  │
                              │  │         OVERLAY NETWORK               │  │
                              │  │      "distrisearch-network"           │  │
                              │  │                                       │  │
                              │  │  ┌─────────┐  ┌─────────┐  ┌────────┐ │  │
                              │  │  │ DNS     │  │ CoreDNS │  │ Consul │ │  │
                              │  │  │ Interno │  │ Backup  │  │ (Opt)  │ │  │
                              │  │  └────┬────┘  └────┬────┘  └────────┘ │  │
                              │  │       │            │                  │  │
                              │  │  ┌────▼────────────▼────────────────┐ │  │
                              │  │  │     SERVICIO: distrisearch       │ │  │
                              │  │  │                                  │ │  │
                              │  │  │  ┌────────┐ ┌────────┐ ┌───────┐ │ │  │
                              │  │  │  │Slave 1 │ │Slave 2 │ │Slave N│ │ │  │
                              │  │  │  │:8000   │ │:8000   │ │:8000  │ │ │  │
                              │  │  │  │:8501   │ │:8501   │ │:8501  │ │ │  │
                              │  │  │  └────────┘ └────────┘ └───────┘ │ │  │
                              │  │  └──────────────────────────────────┘ │  │
                              │  │                                       │  │
                              │  │  ┌──────────────────────────────────┐ │  │
                              │  │  │     SERVICIO: master             │ │  │
                              │  │  │  ┌────────┐  ┌────────┐          │ │  │
                              │  │  │  │Master 1│  │Master 2│ (Standby)│ │  │
                              │  │  │  │(Líder) │  │        │          │ │  │
                              │  │  │  └────────┘  └────────┘          │ │  │
                              │  │  └──────────────────────────────────┘ │  │
                              │  │                                       │  │
                              │  │  ┌──────────────────────────────────┐ │  │
                              │  │  │     SERVICIO: mongodb            │ │  │
                              │  │  │  ┌────────┐ ┌────────┐ ┌───────┐ │ │  │
                              │  │  │  │Mongo 1 │ │Mongo 2 │ │Mongo 3│ │ │  │
                              │  │  │  │(Primary│ │(Second)│ │(Arbtr)│ │ │  │
                              │  │  │  └────────┘ └────────┘ └───────┘ │ │  │
                              │  │  └──────────────────────────────────┘ │  │
                              │  └───────────────────────────────────────┘  │
                              └─────────────────────────────────────────────┘
```

---

## 2. Docker Swarm: Conceptos Fundamentales

### 2.1 ¿Por qué Docker Swarm?

Docker Swarm ofrece ventajas clave para DistriSearch:

| Característica | Beneficio para DistriSearch |
|---------------|----------------------------|
| **DNS Integrado** | Descubrimiento automático de servicios por nombre |
| **Routing Mesh** | Balanceo de carga automático entre réplicas |
| **Rolling Updates** | Actualizaciones sin downtime |
| **Self-Healing** | Reinicio automático de contenedores fallidos |
| **Secretos** | Gestión segura de credenciales |
| **Escalado Declarativo** | `docker service scale` para añadir nodos |

### 2.2 Topología del Swarm

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DOCKER SWARM CLUSTER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐              │
│   │   MANAGER   │     │   MANAGER   │     │   MANAGER   │              │
│   │   NODE 1    │◄───►│   NODE 2    │◄───►│   NODE 3    │              │
│   │  (Leader)   │     │  (Reachable)│     │  (Reachable)│              │
│   │             │     │             │     │             │              │
│   │ • Raft      │     │ • Raft      │     │ • Raft      │              │
│   │ • Scheduler │     │ • Scheduler │     │ • Scheduler │              │
│   │ • API       │     │ • API       │     │ • API       │              │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘              │
│          │                   │                   │                      │
│          └───────────────────┼───────────────────┘                      │
│                              │                                          │
│          ┌───────────────────┼───────────────────┐                      │
│          │                   │                   │                      │
│   ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐              │
│   │   WORKER    │     │   WORKER    │     │   WORKER    │              │
│   │   NODE 1    │     │   NODE 2    │     │   NODE N    │              │
│   │             │     │             │     │             │              │
│   │ • Slave 1   │     │ • Slave 2   │     │ • Slave N   │              │
│   │ • MongoDB   │     │ • Master    │     │ • CoreDNS   │              │
│   │   Replica   │     │             │     │   Backup    │              │
│   └─────────────┘     └─────────────┘     └─────────────┘              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Servicio DNS de Docker Swarm

### 3.1 DNS Interno de Docker

Docker Swarm proporciona un servidor DNS interno que permite resolver nombres de servicios automáticamente:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DOCKER DNS INTERNO (127.0.0.11)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Resolución de Nombres:                                                 │
│                                                                         │
│  ┌──────────────────┐    DNS Query     ┌──────────────────────────────┐│
│  │ Slave Container  │ ──────────────► │ "master" → 10.0.0.5          ││
│  │                  │                  │ "mongodb" → 10.0.0.10        ││
│  │ resolver:        │                  │ "distrisearch" → VIP         ││
│  │ 127.0.0.11       │ ◄────────────── │                              ││
│  └──────────────────┘    IP Response   └──────────────────────────────┘│
│                                                                         │
│  Tipos de Resolución:                                                   │
│                                                                         │
│  1. SERVICE VIP (Virtual IP):                                          │
│     distrisearch → 10.0.0.100 (VIP, balanceado internamente)           │
│                                                                         │
│  2. SERVICE TASKS (Todas las réplicas):                                │
│     tasks.distrisearch → [10.0.0.5, 10.0.0.6, 10.0.0.7]               │
│                                                                         │
│  3. CONTAINER NAME:                                                     │
│     distrisearch.1.abc123 → 10.0.0.5 (contenedor específico)          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Configuración del DNS en docker-compose.yml

```yaml
# docker/docker-compose.swarm.yml

version: '3.8'

networks:
  distrisearch-network:
    driver: overlay
    attachable: true
    ipam:
      config:
        - subnet: 10.0.10.0/24

services:
  # ═══════════════════════════════════════════════════════════════════════
  # SERVICIO SLAVE (Escalable)
  # ═══════════════════════════════════════════════════════════════════════
  distrisearch:
    image: distrisearch/slave:latest
    networks:
      - distrisearch-network
    environment:
      - NODE_ROLE=slave
      - MASTER_HOST=master          # Resuelto por DNS interno
      - MONGODB_HOST=mongodb        # Resuelto por DNS interno
      - DNS_BACKUP_ENABLED=true
      - DNS_BACKUP_HOST=coredns
    deploy:
      replicas: 3
      endpoint_mode: vip            # Virtual IP para balanceo
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # ═══════════════════════════════════════════════════════════════════════
  # SERVICIO MASTER (Alta Disponibilidad)
  # ═══════════════════════════════════════════════════════════════════════
  master:
    image: distrisearch/master:latest
    networks:
      - distrisearch-network
    environment:
      - NODE_ROLE=master
      - MONGODB_HOST=mongodb
      - RAFT_PEERS=master           # Auto-descubrimiento via DNS
    deploy:
      replicas: 2                   # 1 líder + 1 standby
      endpoint_mode: dnsrr          # DNS Round Robin para Raft
      placement:
        constraints:
          - node.role == manager    # Masters en nodos manager
      restart_policy:
        condition: on-failure
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8001/health')"]
      interval: 15s
      timeout: 5s
      retries: 3

  # ═══════════════════════════════════════════════════════════════════════
  # MONGODB REPLICA SET
  # ═══════════════════════════════════════════════════════════════════════
  mongodb:
    image: mongo:6.0
    networks:
      - distrisearch-network
    command: mongod --replSet rs0 --bind_ip_all
    deploy:
      replicas: 3
      endpoint_mode: dnsrr
      placement:
        max_replicas_per_node: 1    # Distribuir en diferentes nodos
    volumes:
      - mongodb-data:/data/db

volumes:
  mongodb-data:
    driver: local
```

### 3.3 Cómo Funciona el DNS de Docker Swarm

```
┌─────────────────────────────────────────────────────────────────────────┐
│              FLUJO DE RESOLUCIÓN DNS EN DOCKER SWARM                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   PASO 1: Aplicación solicita conexión                                  │
│   ─────────────────────────────────────                                 │
│   ┌─────────────┐                                                       │
│   │ Slave App   │  requests.get("http://master:8001/api/partition")    │
│   │             │  ─────────────────────────────────────────────►       │
│   └─────────────┘                                                       │
│                                                                         │
│   PASO 2: Resolución DNS interna                                        │
│   ──────────────────────────────                                        │
│   ┌─────────────┐          ┌────────────────┐                          │
│   │ Container   │  "master"│ Docker DNS     │                          │
│   │ Resolver    │ ────────►│ 127.0.0.11:53  │                          │
│   │             │          │                │                          │
│   │             │ ◄────────│ 10.0.10.5      │  (IP del servicio master)│
│   └─────────────┘          └────────────────┘                          │
│                                                                         │
│   PASO 3: Conexión TCP al servicio                                      │
│   ────────────────────────────────                                      │
│   ┌─────────────┐          ┌────────────────┐                          │
│   │ Slave App   │          │ Master Service │                          │
│   │             │ ────────►│ 10.0.10.5:8001 │                          │
│   │             │ TCP/HTTP │                │                          │
│   └─────────────┘          └────────────────┘                          │
│                                                                         │
│   PASO 4: Si el Master tiene múltiples réplicas (endpoint_mode: dnsrr) │
│   ───────────────────────────────────────────────────────────────────── │
│                                                                         │
│   Query: "tasks.master" → [10.0.10.5, 10.0.10.6]                       │
│   (La aplicación puede implementar su propio balanceo/failover)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Sistema de Respaldo DNS (Fallback)

### 4.1 ¿Por qué necesitamos DNS de respaldo?

El DNS interno de Docker puede fallar en escenarios como:
- **Saturación del daemon**: Alto número de consultas DNS
- **Fallo del nodo manager**: El DNS depende del estado del Swarm
- **Network partition**: Segmentación de red temporal
- **Bug de Docker**: Casos edge documentados en issues de Docker

### 4.2 Arquitectura del Sistema de Respaldo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SISTEMA DE DNS CON FALLBACK                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    APLICACIÓN (Slave/Master)                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐│   │
│  │  │                   DNS Resolver Client                        ││   │
│  │  │                                                              ││   │
│  │  │  1. Intentar Docker DNS (127.0.0.11)                        ││   │
│  │  │     └─► Si falla → paso 2                                   ││   │
│  │  │                                                              ││   │
│  │  │  2. Intentar CoreDNS Backup (coredns:53)                    ││   │
│  │  │     └─► Si falla → paso 3                                   ││   │
│  │  │                                                              ││   │
│  │  │  3. Intentar Consul DNS (consul:8600)                       ││   │
│  │  │     └─► Si falla → paso 4                                   ││   │
│  │  │                                                              ││   │
│  │  │  4. Usar caché local / archivo hosts                        ││   │
│  │  │     └─► Si falla → ERROR                                    ││   │
│  │  │                                                              ││   │
│  │  └─────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│               ┌──────────────┼──────────────┬──────────────┐           │
│               │              │              │              │           │
│               ▼              ▼              ▼              ▼           │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────┐ ┌──────────┐   │
│  │  Docker DNS    │ │   CoreDNS      │ │  Consul    │ │ Caché    │   │
│  │  (Primario)    │ │   (Backup 1)   │ │ (Backup 2) │ │ Local    │   │
│  │                │ │                │ │            │ │          │   │
│  │  127.0.0.11    │ │  coredns:53    │ │consul:8600 │ │/etc/hosts│   │
│  │                │ │                │ │            │ │          │   │
│  │  • Automático  │ │  • Configurable│ │• Service   │ │• Estático│   │
│  │  • Sin config  │ │  • Zones custom│ │  Discovery │ │• Último  │   │
│  │                │ │  • Forwarding  │ │• Health    │ │  recurso │   │
│  └────────────────┘ └────────────────┘ └────────────┘ └──────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Implementación del CoreDNS como Backup

#### Archivo de configuración CoreDNS: `Corefile`

```
# docker/coredns/Corefile

# ═══════════════════════════════════════════════════════════════════════
# ZONA PRINCIPAL: distrisearch.local
# ═══════════════════════════════════════════════════════════════════════
distrisearch.local:53 {
    # Logs para debugging
    log
    errors
    
    # Health check endpoint
    health :8080
    
    # Métricas Prometheus
    prometheus :9153
    
    # Caché de respuestas DNS
    cache 300
    
    # Zona de archivos estáticos (fallback)
    file /etc/coredns/zones/distrisearch.local.zone
    
    # Si no se encuentra en archivo, preguntar a Docker DNS
    forward . 127.0.0.11 {
        except distrisearch.local
    }
    
    # Reescritura de nombres para compatibilidad
    rewrite name master.distrisearch.local master.distrisearch-network
    rewrite name mongodb.distrisearch.local mongodb.distrisearch-network
}

# ═══════════════════════════════════════════════════════════════════════
# ZONA DE SERVICIOS INTERNOS
# ═══════════════════════════════════════════════════════════════════════
services.local:53 {
    log
    cache 60
    
    # Auto-descubrimiento desde Docker
    docker {
        endpoint unix:///var/run/docker.sock
        ttl 30
    }
}

# ═══════════════════════════════════════════════════════════════════════
# FORWARD A DNS EXTERNOS (para dependencias externas)
# ═══════════════════════════════════════════════════════════════════════
.:53 {
    cache 3600
    forward . 8.8.8.8 8.8.4.4 1.1.1.1
}
```

#### Archivo de zona: `distrisearch.local.zone`

```dns
; docker/coredns/zones/distrisearch.local.zone
; ═══════════════════════════════════════════════════════════════════════
; ZONA DE RESPALDO ESTÁTICA PARA DISTRISEARCH
; Se actualiza automáticamente mediante script de sincronización
; ═══════════════════════════════════════════════════════════════════════

$ORIGIN distrisearch.local.
$TTL 60

; SOA Record
@       IN      SOA     ns1.distrisearch.local. admin.distrisearch.local. (
                        2024120901      ; Serial (YYYYMMDDNN)
                        3600            ; Refresh (1 hora)
                        600             ; Retry (10 minutos)
                        86400           ; Expire (1 día)
                        60              ; Minimum TTL (1 minuto)
                        )

; Name Servers
@       IN      NS      ns1.distrisearch.local.
ns1     IN      A       10.0.10.100

; ═══════════════════════════════════════════════════════════════════════
; SERVICIOS PRINCIPALES
; ═══════════════════════════════════════════════════════════════════════

; Master Service (múltiples registros para failover)
master          IN      A       10.0.10.5
master          IN      A       10.0.10.6

; Slave Services (Virtual IP del servicio)
distrisearch    IN      A       10.0.10.100

; Slaves individuales (para acceso directo)
slave-1         IN      A       10.0.10.11
slave-2         IN      A       10.0.10.12
slave-3         IN      A       10.0.10.13

; MongoDB Replica Set
mongodb         IN      A       10.0.10.20
mongodb-1       IN      A       10.0.10.21
mongodb-2       IN      A       10.0.10.22
mongodb-3       IN      A       10.0.10.23

; CoreDNS Backup
coredns         IN      A       10.0.10.50

; ═══════════════════════════════════════════════════════════════════════
; SRV RECORDS (Para Service Discovery)
; ═══════════════════════════════════════════════════════════════════════

; _service._proto.name TTL class SRV priority weight port target
_master._tcp            IN      SRV     10 50 8001 master.distrisearch.local.
_slave._tcp             IN      SRV     10 50 8000 distrisearch.distrisearch.local.
_mongodb._tcp           IN      SRV     10 50 27017 mongodb.distrisearch.local.
```

### 4.4 Servicio CoreDNS en Docker Swarm

```yaml
# Añadir al docker-compose.swarm.yml

  # ═══════════════════════════════════════════════════════════════════════
  # COREDNS - DNS DE RESPALDO
  # ═══════════════════════════════════════════════════════════════════════
  coredns:
    image: coredns/coredns:1.11.1
    networks:
      distrisearch-network:
        ipv4_address: 10.0.10.50    # IP fija para el DNS de respaldo
    volumes:
      - ./coredns/Corefile:/etc/coredns/Corefile:ro
      - ./coredns/zones:/etc/coredns/zones:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: ["-conf", "/etc/coredns/Corefile"]
    deploy:
      replicas: 2
      placement:
        constraints:
          - node.role == manager
        preferences:
          - spread: node.id        # Distribuir en diferentes nodos
      restart_policy:
        condition: any
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

### 4.5 Cliente DNS con Fallback (Python)

```python
# backend/app/core/dns/dns_resolver.py

import dns.resolver
import socket
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class DNSConfig:
    """Configuración del sistema DNS con fallback."""
    docker_dns: str = "127.0.0.11"
    coredns_host: str = "coredns"
    coredns_port: int = 53
    consul_host: str = "consul"
    consul_port: int = 8600
    cache_ttl: int = 60
    timeout: float = 2.0
    max_retries: int = 3


class FallbackDNSResolver:
    """
    Resolvedor DNS con múltiples niveles de fallback.
    
    Orden de resolución:
    1. Docker DNS interno (127.0.0.11)
    2. CoreDNS backup (coredns:53)
    3. Consul DNS (consul:8600) - opcional
    4. Caché local / archivo hosts
    """
    
    def __init__(self, config: Optional[DNSConfig] = None):
        self.config = config or DNSConfig()
        self._cache: dict[str, Tuple[List[str], float]] = {}
        self._resolvers = self._init_resolvers()
    
    def _init_resolvers(self) -> List[dns.resolver.Resolver]:
        """Inicializa los resolvers en orden de prioridad."""
        resolvers = []
        
        # 1. Docker DNS
        docker_resolver = dns.resolver.Resolver()
        docker_resolver.nameservers = [self.config.docker_dns]
        docker_resolver.lifetime = self.config.timeout
        resolvers.append(("docker", docker_resolver))
        
        # 2. CoreDNS Backup
        coredns_resolver = dns.resolver.Resolver()
        coredns_resolver.nameservers = [
            socket.gethostbyname(self.config.coredns_host)
        ]
        coredns_resolver.lifetime = self.config.timeout
        resolvers.append(("coredns", coredns_resolver))
        
        return resolvers
    
    async def resolve(
        self, 
        hostname: str, 
        record_type: str = "A"
    ) -> List[str]:
        """
        Resuelve un hostname intentando múltiples DNS servers.
        
        Args:
            hostname: Nombre del host a resolver (ej: "master", "mongodb")
            record_type: Tipo de registro DNS (A, AAAA, SRV, etc.)
        
        Returns:
            Lista de IPs/valores resueltos
        
        Raises:
            DNSResolutionError: Si todos los métodos fallan
        """
        # Verificar caché primero
        cache_key = f"{hostname}:{record_type}"
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"DNS cache hit: {hostname} -> {cached}")
            return cached
        
        last_error = None
        
        # Intentar cada resolver en orden
        for resolver_name, resolver in self._resolvers:
            try:
                logger.debug(f"Trying DNS resolution via {resolver_name}: {hostname}")
                
                answers = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: resolver.resolve(hostname, record_type)
                )
                
                results = [str(rdata) for rdata in answers]
                
                # Guardar en caché
                self._save_to_cache(cache_key, results)
                
                logger.info(
                    f"DNS resolved via {resolver_name}: {hostname} -> {results}"
                )
                return results
                
            except dns.resolver.NXDOMAIN:
                logger.warning(f"{resolver_name}: NXDOMAIN for {hostname}")
                last_error = f"NXDOMAIN: {hostname}"
                
            except dns.resolver.NoAnswer:
                logger.warning(f"{resolver_name}: No answer for {hostname}")
                last_error = f"NoAnswer: {hostname}"
                
            except dns.resolver.Timeout:
                logger.warning(f"{resolver_name}: Timeout resolving {hostname}")
                last_error = f"Timeout: {hostname}"
                
            except Exception as e:
                logger.warning(f"{resolver_name}: Error resolving {hostname}: {e}")
                last_error = str(e)
        
        # Último recurso: archivo hosts / caché local persistente
        fallback_result = await self._fallback_resolve(hostname)
        if fallback_result:
            logger.info(f"DNS fallback: {hostname} -> {fallback_result}")
            return fallback_result
        
        raise DNSResolutionError(
            f"Failed to resolve {hostname} after trying all DNS sources. "
            f"Last error: {last_error}"
        )
    
    async def resolve_service(
        self, 
        service_name: str
    ) -> List[Tuple[str, int]]:
        """
        Resuelve un servicio Docker Swarm obteniendo todas sus réplicas.
        
        Args:
            service_name: Nombre del servicio (ej: "distrisearch", "master")
        
        Returns:
            Lista de tuplas (host, port) para cada réplica
        """
        # Intentar resolución via tasks.{service} para obtener todas las IPs
        try:
            # Docker Swarm: tasks.{service} resuelve a todas las réplicas
            ips = await self.resolve(f"tasks.{service_name}")
            # Puerto por defecto según el servicio
            port = self._get_default_port(service_name)
            return [(ip, port) for ip in ips]
        except DNSResolutionError:
            # Fallback: resolver el nombre del servicio (VIP)
            try:
                ips = await self.resolve(service_name)
                port = self._get_default_port(service_name)
                return [(ips[0], port)]
            except DNSResolutionError:
                raise
    
    def _get_default_port(self, service_name: str) -> int:
        """Obtiene el puerto por defecto para un servicio conocido."""
        ports = {
            "master": 8001,
            "distrisearch": 8000,
            "mongodb": 27017,
            "coredns": 53,
        }
        return ports.get(service_name, 8000)
    
    def _get_from_cache(self, key: str) -> Optional[List[str]]:
        """Obtiene valor del caché si no ha expirado."""
        import time
        if key in self._cache:
            values, timestamp = self._cache[key]
            if time.time() - timestamp < self.config.cache_ttl:
                return values
            del self._cache[key]
        return None
    
    def _save_to_cache(self, key: str, values: List[str]):
        """Guarda valor en caché con timestamp."""
        import time
        self._cache[key] = (values, time.time())
    
    async def _fallback_resolve(self, hostname: str) -> Optional[List[str]]:
        """
        Último recurso: resolver usando archivo hosts o caché persistente.
        """
        # Leer archivo hosts personalizado
        hosts_file = "/app/config/hosts.fallback"
        try:
            with open(hosts_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == hostname:
                            return [parts[0]]
        except FileNotFoundError:
            pass
        
        return None
    
    async def health_check(self) -> dict:
        """Verifica el estado de todos los DNS servers."""
        results = {}
        test_hostname = "master"  # Servicio conocido para testing
        
        for resolver_name, resolver in self._resolvers:
            try:
                start = asyncio.get_event_loop().time()
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: resolver.resolve(test_hostname, "A")
                )
                latency = asyncio.get_event_loop().time() - start
                results[resolver_name] = {
                    "status": "healthy",
                    "latency_ms": round(latency * 1000, 2)
                }
            except Exception as e:
                results[resolver_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return results


class DNSResolutionError(Exception):
    """Error cuando no se puede resolver un hostname."""
    pass


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON PARA USO GLOBAL
# ═══════════════════════════════════════════════════════════════════════

_resolver_instance: Optional[FallbackDNSResolver] = None


def get_dns_resolver() -> FallbackDNSResolver:
    """Obtiene la instancia singleton del resolver DNS."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = FallbackDNSResolver()
    return _resolver_instance


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

async def resolve_master() -> str:
    """Atajo para resolver el servicio master."""
    resolver = get_dns_resolver()
    ips = await resolver.resolve("master")
    return ips[0]


async def resolve_mongodb() -> str:
    """Atajo para resolver el servicio mongodb."""
    resolver = get_dns_resolver()
    ips = await resolver.resolve("mongodb")
    return ips[0]


async def get_all_slaves() -> List[Tuple[str, int]]:
    """Obtiene todas las réplicas del servicio distrisearch."""
    resolver = get_dns_resolver()
    return await resolver.resolve_service("distrisearch")
```

---

## 5. Script de Sincronización de Zona DNS

```python
#!/usr/bin/env python3
# scripts/sync_dns_zone.py

"""
Script para sincronizar la zona DNS de CoreDNS con el estado actual de Docker Swarm.
Se ejecuta periódicamente mediante cron o como sidecar container.
"""

import docker
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DNSZoneSynchronizer:
    """Sincroniza zona DNS de CoreDNS con servicios de Docker Swarm."""
    
    ZONE_TEMPLATE = """; Zona DNS de respaldo para DistriSearch
; Generado automáticamente: {timestamp}
; NO EDITAR MANUALMENTE

$ORIGIN distrisearch.local.
$TTL 60

@       IN      SOA     ns1.distrisearch.local. admin.distrisearch.local. (
                        {serial}        ; Serial
                        3600            ; Refresh
                        600             ; Retry
                        86400           ; Expire
                        60              ; Minimum TTL
                        )

@       IN      NS      ns1.distrisearch.local.
ns1     IN      A       10.0.10.50

; ═══════════════════════════════════════════════════════════════════════
; SERVICIOS DETECTADOS AUTOMÁTICAMENTE
; ═══════════════════════════════════════════════════════════════════════

{records}
"""
    
    def __init__(self, zone_file: str = "/etc/coredns/zones/distrisearch.local.zone"):
        self.zone_file = Path(zone_file)
        self.client = docker.from_env()
    
    def get_swarm_services(self) -> Dict[str, List[str]]:
        """Obtiene IPs de todos los servicios del Swarm."""
        services = {}
        
        try:
            for service in self.client.services.list():
                service_name = service.name
                tasks = service.tasks(filters={"desired-state": "running"})
                
                ips = []
                for task in tasks:
                    # Obtener IP del contenedor
                    if task.get("Status", {}).get("State") == "running":
                        networks = task.get("NetworksAttachments", [])
                        for net in networks:
                            if "distrisearch" in net.get("Network", {}).get("Spec", {}).get("Name", ""):
                                addresses = net.get("Addresses", [])
                                for addr in addresses:
                                    ip = addr.split("/")[0]
                                    ips.append(ip)
                
                if ips:
                    services[service_name] = ips
                    
        except docker.errors.APIError as e:
            logger.error(f"Error accessing Docker API: {e}")
        
        return services
    
    def generate_zone_records(self, services: Dict[str, List[str]]) -> str:
        """Genera registros DNS para los servicios."""
        records = []
        
        for service_name, ips in services.items():
            records.append(f"; Service: {service_name}")
            
            # Registro principal (primera IP o VIP)
            if ips:
                records.append(f"{service_name:<16} IN      A       {ips[0]}")
            
            # Registros individuales para cada réplica
            for i, ip in enumerate(ips, 1):
                records.append(f"{service_name}-{i:<12} IN      A       {ip}")
            
            records.append("")  # Línea vacía entre servicios
        
        return "\n".join(records)
    
    def update_zone_file(self):
        """Actualiza el archivo de zona DNS."""
        services = self.get_swarm_services()
        
        if not services:
            logger.warning("No services found in Swarm")
            return
        
        # Generar serial basado en timestamp
        serial = datetime.now().strftime("%Y%m%d%H")
        
        # Generar registros
        records = self.generate_zone_records(services)
        
        # Generar contenido de la zona
        zone_content = self.ZONE_TEMPLATE.format(
            timestamp=datetime.now().isoformat(),
            serial=serial,
            records=records
        )
        
        # Escribir archivo
        self.zone_file.parent.mkdir(parents=True, exist_ok=True)
        self.zone_file.write_text(zone_content)
        
        logger.info(f"Zone file updated: {self.zone_file}")
        logger.info(f"Services synchronized: {list(services.keys())}")
    
    def run_daemon(self, interval: int = 30):
        """Ejecuta como daemon, actualizando periódicamente."""
        import time
        
        logger.info(f"Starting DNS zone synchronizer (interval: {interval}s)")
        
        while True:
            try:
                self.update_zone_file()
            except Exception as e:
                logger.error(f"Error updating zone: {e}")
            
            time.sleep(interval)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync DNS zone with Docker Swarm")
    parser.add_argument("--zone-file", default="/etc/coredns/zones/distrisearch.local.zone")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=30, help="Sync interval in seconds")
    
    args = parser.parse_args()
    
    syncer = DNSZoneSynchronizer(args.zone_file)
    
    if args.daemon:
        syncer.run_daemon(args.interval)
    else:
        syncer.update_zone_file()
```

---

## 6. Despliegue Completo con Docker Swarm

### 6.1 Inicialización del Swarm

```bash
#!/bin/bash
# scripts/init_swarm.sh

# ═══════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN DEL DOCKER SWARM CLUSTER
# ═══════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════════════"
echo "  INICIALIZANDO DOCKER SWARM PARA DISTRISEARCH"
echo "═══════════════════════════════════════════════════════════════════"

# Variables
MANAGER_IP=${MANAGER_IP:-$(hostname -I | awk '{print $1}')}
SWARM_ADVERTISE_ADDR=${SWARM_ADVERTISE_ADDR:-$MANAGER_IP}

# 1. Inicializar Swarm (si no existe)
if ! docker info | grep -q "Swarm: active"; then
    echo "[1/5] Inicializando Docker Swarm..."
    docker swarm init --advertise-addr $SWARM_ADVERTISE_ADDR
else
    echo "[1/5] Docker Swarm ya está activo"
fi

# 2. Crear red overlay
echo "[2/5] Creando red overlay..."
docker network create \
    --driver overlay \
    --attachable \
    --subnet 10.0.10.0/24 \
    --gateway 10.0.10.1 \
    distrisearch-network 2>/dev/null || echo "Red ya existe"

# 3. Crear secretos
echo "[3/5] Creando secretos..."
if [ -f .env.production ]; then
    # MongoDB credentials
    grep MONGO_PASSWORD .env.production | cut -d= -f2 | \
        docker secret create mongo_password - 2>/dev/null || true
    
    # JWT Secret
    grep JWT_SECRET .env.production | cut -d= -f2 | \
        docker secret create jwt_secret - 2>/dev/null || true
fi

# 4. Crear configs
echo "[4/5] Creando configuraciones..."
docker config create coredns_config ./docker/coredns/Corefile 2>/dev/null || true
docker config create coredns_zone ./docker/coredns/zones/distrisearch.local.zone 2>/dev/null || true

# 5. Desplegar stack
echo "[5/5] Desplegando stack DistriSearch..."
docker stack deploy \
    --compose-file docker/docker-compose.swarm.yml \
    --with-registry-auth \
    distrisearch

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  SWARM INICIALIZADO CORRECTAMENTE"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Para añadir workers, ejecuta en cada nodo:"
docker swarm join-token worker
echo ""
echo "Para añadir managers, ejecuta en cada nodo:"
docker swarm join-token manager
```

### 6.2 Docker Compose para Swarm

```yaml
# docker/docker-compose.swarm.yml

version: '3.8'

# ═══════════════════════════════════════════════════════════════════════
# REDES
# ═══════════════════════════════════════════════════════════════════════
networks:
  distrisearch-network:
    external: true

# ═══════════════════════════════════════════════════════════════════════
# VOLÚMENES
# ═══════════════════════════════════════════════════════════════════════
volumes:
  mongodb-data:
  coredns-zones:

# ═══════════════════════════════════════════════════════════════════════
# CONFIGS
# ═══════════════════════════════════════════════════════════════════════
configs:
  coredns_config:
    external: true
  coredns_zone:
    external: true

# ═══════════════════════════════════════════════════════════════════════
# SECRETS
# ═══════════════════════════════════════════════════════════════════════
secrets:
  mongo_password:
    external: true
  jwt_secret:
    external: true

# ═══════════════════════════════════════════════════════════════════════
# SERVICIOS
# ═══════════════════════════════════════════════════════════════════════
services:

  # ─────────────────────────────────────────────────────────────────────
  # COREDNS - DNS de Respaldo
  # ─────────────────────────────────────────────────────────────────────
  coredns:
    image: coredns/coredns:1.11.1
    networks:
      distrisearch-network:
        ipv4_address: 10.0.10.50
    configs:
      - source: coredns_config
        target: /etc/coredns/Corefile
      - source: coredns_zone
        target: /etc/coredns/zones/distrisearch.local.zone
    command: ["-conf", "/etc/coredns/Corefile"]
    deploy:
      replicas: 2
      placement:
        constraints:
          - node.role == manager
        preferences:
          - spread: node.id
      restart_policy:
        condition: any
        delay: 5s
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # ─────────────────────────────────────────────────────────────────────
  # DNS ZONE SYNCHRONIZER - Mantiene zona DNS actualizada
  # ─────────────────────────────────────────────────────────────────────
  dns-sync:
    image: distrisearch/dns-sync:latest
    networks:
      - distrisearch-network
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - coredns-zones:/etc/coredns/zones
    environment:
      - SYNC_INTERVAL=30
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure

  # ─────────────────────────────────────────────────────────────────────
  # MONGODB - Base de datos distribuida
  # ─────────────────────────────────────────────────────────────────────
  mongodb:
    image: mongo:6.0
    networks:
      - distrisearch-network
    command: mongod --replSet rs0 --bind_ip_all
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD_FILE: /run/secrets/mongo_password
    secrets:
      - mongo_password
    volumes:
      - mongodb-data:/data/db
    deploy:
      replicas: 3
      endpoint_mode: dnsrr
      placement:
        max_replicas_per_node: 1
      restart_policy:
        condition: on-failure
        delay: 10s
      resources:
        limits:
          cpus: '2'
          memory: 4G

  # ─────────────────────────────────────────────────────────────────────
  # MASTER - Coordinador del cluster
  # ─────────────────────────────────────────────────────────────────────
  master:
    image: distrisearch/master:latest
    networks:
      - distrisearch-network
    environment:
      - NODE_ROLE=master
      - MONGODB_URI=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
      - RAFT_PEERS=tasks.master
      - DNS_FALLBACK_ENABLED=true
      - DNS_FALLBACK_HOST=10.0.10.50
    secrets:
      - jwt_secret
    deploy:
      replicas: 2
      endpoint_mode: dnsrr
      placement:
        constraints:
          - node.role == manager
      update_config:
        parallelism: 1
        delay: 30s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 10s
      resources:
        limits:
          cpus: '1'
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 30s

  # ─────────────────────────────────────────────────────────────────────
  # DISTRISEARCH - Nodos Slave (Frontend + Backend)
  # ─────────────────────────────────────────────────────────────────────
  distrisearch:
    image: distrisearch/slave:latest
    networks:
      - distrisearch-network
    ports:
      - target: 8000
        published: 8000
        protocol: tcp
        mode: ingress
      - target: 8501
        published: 8501
        protocol: tcp
        mode: ingress
    environment:
      - NODE_ROLE=slave
      - MASTER_HOST=master
      - MONGODB_URI=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
      - DNS_FALLBACK_ENABLED=true
      - DNS_FALLBACK_HOST=10.0.10.50
    secrets:
      - jwt_secret
    deploy:
      replicas: 3
      endpoint_mode: vip
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
        order: start-first
      rollback_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

---

## 7. Comandos de Operación

### 7.1 Gestión del Cluster

```bash
# Ver estado del swarm
docker node ls

# Ver servicios desplegados
docker service ls

# Ver réplicas de un servicio
docker service ps distrisearch_distrisearch

# Escalar servicio
docker service scale distrisearch_distrisearch=5

# Ver logs de un servicio
docker service logs -f distrisearch_distrisearch

# Actualizar imagen de un servicio
docker service update --image distrisearch/slave:v2.0 distrisearch_distrisearch

# Rollback de un servicio
docker service rollback distrisearch_distrisearch
```

### 7.2 Diagnóstico de DNS

```bash
# Verificar resolución DNS desde un contenedor
docker run --rm --network distrisearch-network alpine nslookup master

# Verificar todas las réplicas de un servicio
docker run --rm --network distrisearch-network alpine nslookup tasks.distrisearch

# Verificar CoreDNS backup
docker run --rm --network distrisearch-network alpine nslookup master 10.0.10.50

# Ver configuración DNS de un contenedor
docker exec <container_id> cat /etc/resolv.conf
```

---

## 8. Diagrama de Flujo de Resolución DNS

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 FLUJO COMPLETO DE RESOLUCIÓN DNS                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐                                                       │
│  │ Aplicación   │ requests.get("http://master:8001/api/...")           │
│  │ (Slave)      │                                                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ FallbackDNSResolver                                               │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │ 1. Verificar Caché Local                                    │ │  │
│  │  │    ├─ Hit → Retornar IP cacheada                           │ │  │
│  │  │    └─ Miss → Continuar                                      │ │  │
│  │  └───────────────────────────┬─────────────────────────────────┘ │  │
│  │                              │                                    │  │
│  │  ┌───────────────────────────▼─────────────────────────────────┐ │  │
│  │  │ 2. Docker DNS (127.0.0.11)                                  │ │  │
│  │  │    ├─ Éxito → Cachear + Retornar IP                        │ │  │
│  │  │    └─ Fallo (timeout/NXDOMAIN) → Continuar                  │ │  │
│  │  └───────────────────────────┬─────────────────────────────────┘ │  │
│  │                              │                                    │  │
│  │  ┌───────────────────────────▼─────────────────────────────────┐ │  │
│  │  │ 3. CoreDNS Backup (10.0.10.50:53)                          │ │  │
│  │  │    ├─ Éxito → Cachear + Retornar IP                        │ │  │
│  │  │    └─ Fallo → Continuar                                     │ │  │
│  │  └───────────────────────────┬─────────────────────────────────┘ │  │
│  │                              │                                    │  │
│  │  ┌───────────────────────────▼─────────────────────────────────┐ │  │
│  │  │ 4. Archivo Hosts Fallback (/app/config/hosts.fallback)     │ │  │
│  │  │    ├─ Encontrado → Retornar IP estática                    │ │  │
│  │  │    └─ No encontrado → ERROR                                 │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Resultado: IP del servicio master (ej: 10.0.10.5)                     │
│                                                                         │
│  ┌──────────────┐         ┌──────────────┐                             │
│  │ Aplicación   │ ──────► │   Master     │                             │
│  │ (Slave)      │  HTTP   │  10.0.10.5   │                             │
│  └──────────────┘         └──────────────┘                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Monitoreo y Alertas

### 9.1 Health Checks del Sistema DNS

```yaml
# monitoring/prometheus/dns_alerts.yml

groups:
  - name: dns_alerts
    rules:
      - alert: DockerDNSUnhealthy
        expr: dns_health_check{resolver="docker"} == 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Docker DNS no responde"
          description: "El DNS interno de Docker no está respondiendo. CoreDNS backup activo."

      - alert: AllDNSUnhealthy
        expr: sum(dns_health_check) == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "CRÍTICO: Todos los DNS servers caídos"
          description: "Ningún servidor DNS responde. Sistema en modo degradado."

      - alert: DNSResolutionLatencyHigh
        expr: dns_resolution_latency_seconds > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Latencia DNS elevada"
          description: "La resolución DNS está tardando más de 500ms."
```

---

## 10. Comportamiento Adaptativo del Cluster

### 10.1 Arranque Incremental

El sistema **NO arranca con n nodos predefinidos**. En su lugar, crece incrementalmente:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CICLO DE VIDA DEL CLUSTER                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  SINGLE_NODE │───►│   GROWING    │───►│    MULTI_NODE        │  │
│  │              │    │              │    │                      │  │
│  │ • 1 nodo     │    │ • 2+ nodos   │    │ • n nodos objetivo   │  │
│  │ • Sin réplica│    │ • Réplica=1  │    │ • Réplica=config     │  │
│  │ • k=0        │    │ • k=0 o k=1  │    │ • k según quorum     │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                                                                     │
│  El sistema es FUNCIONAL en cada fase con las capacidades          │
│  disponibles según el número de nodos activos.                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Tolerancia a Fallos Adaptativa

**Regla fundamental**: La tolerancia de nivel k solo aplica si hay al menos k+1 instancias operando.

| Nodos Activos | Factor Replicación | Quorum | Tolerancia k | Capacidades |
|--------------|-------------------|--------|--------------|-------------|
| 1 | 0 (sin réplica) | 1 | 0 | Lectura/Escritura local |
| 2 | 1 | 2 | 0 | Replicación básica |
| 3 | 2 | 2 | 1 | Tolerancia a 1 fallo |
| 4 | 2 | 3 | 1 | Tolerancia a 1 fallo |
| 5 | 2 | 3 | 2 | Tolerancia a 2 fallos |

### 10.3 Particiones de Red - Enfoque AP (CAP Theorem)

DistriSearch implementa un **enfoque AP (Availability + Partition tolerance)** del teorema CAP:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TEOREMA CAP - ENFOQUE AP                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│     ┌───────────────────┐                                          │
│     │   Consistencia    │                                          │
│     │       (C)         │  ← Sacrificamos consistencia estricta    │
│     └───────────────────┘                                          │
│              △                                                      │
│             ╱ ╲                                                     │
│            ╱   ╲                                                    │
│           ╱     ╲                                                   │
│          ╱  AP   ╲  ← DistriSearch opera aquí                      │
│         ╱         ╲                                                 │
│  ┌─────▼───────┐   ┌──────▼─────┐                                  │
│  │Disponibilidad│   │ Tolerancia │                                  │
│  │     (A)     │   │ Partición  │                                  │
│  │             │   │    (P)     │                                  │
│  │  ✓ SIEMPRE  │   │  ✓ SIEMPRE │                                  │
│  │  RESPONDE   │   │  SOPORTA   │                                  │
│  └─────────────┘   └────────────┘                                  │
│                                                                     │
│  GARANTÍA: El sistema SIEMPRE procesa consultas y devuelve         │
│  la versión más reciente disponible de la información.             │
└─────────────────────────────────────────────────────────────────────┘
```

**Comportamiento durante particiones de red:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PARTICIÓN DE RED (AP MODE)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐         ┌─────────────────────┐           │
│  │   PARTICIÓN A       │   ╳╳╳   │   PARTICIÓN B       │           │
│  │                     │   ╳╳╳   │                     │           │
│  │  Node 1, Node 2     │   ╳╳╳   │  Node 3, Node 4     │           │
│  │                     │         │                     │           │
│  │  ✓ Lecturas OK      │         │  ✓ Lecturas OK      │           │
│  │  ✓ Escrituras OK    │         │  ✓ Escrituras OK    │           │
│  │  ⚠ Datos pueden     │         │  ⚠ Datos pueden     │           │
│  │    estar stale      │         │    estar stale      │           │
│  └─────────────────────┘         └─────────────────────┘           │
│                                                                     │
│  AMBAS PARTICIONES OPERAN COMPLETAMENTE                            │
│                                                                     │
│  Respuesta incluye indicadores de frescura:                        │
│  • CONFIRMED: Datos confirmados por quorum                         │
│  • LIKELY_CURRENT: Reciente pero no confirmado                     │
│  • POTENTIALLY_STALE: Puede estar desactualizado                   │
│  • STALE: Se sabe que está desactualizado                          │
│                                                                     │
│  Cuando se restaura la conexión:                                    │
│  1. Anti-entropy sync automático                                   │
│  2. Vector clocks para detectar conflictos                         │
│  3. Last-write-wins para resolución                                │
└─────────────────────────────────────────────────────────────────────┘
```

**Ejemplo de respuesta durante partición:**

```python
from app.distributed.consensus import PartitionTolerantConsensus

# Ejecutar búsqueda con garantía AP
result = await consensus.query(
    query_func=lambda: search_engine.search("machine learning"),
    query_id="search-123"
)

# Respuesta SIEMPRE se entrega:
{
    "success": True,
    "data": [...resultados...],
    "freshness": "potentially_stale",
    "availability_mode": "AP",
    "partition_status": "partitioned",
    "staleness_warning": "Resultados obtenidos durante partición de red (duración: 45s). Los datos pueden no reflejar actualizaciones recientes de nodos inalcanzables: ['node-3', 'node-4']",
    "source_nodes": ["node-1", "node-2"],
    "unavailable_nodes": ["node-3", "node-4"]
}
```

### 10.4 Niveles de Degradación

El sistema reporta su estado de degradación:

| Nivel | Estado | Descripción |
|-------|--------|-------------|
| NONE | Óptimo | Todos los nodos activos, replicación completa |
| MINIMAL | Bueno | Ligera reducción de redundancia |
| MODERATE | Degradado | Replicación reducida, quorum mínimo |
| SIGNIFICANT | Limitado | Modo single-node o partición minoritaria |
| CRITICAL | Crítico | Solo lectura o severamente limitado |

### 10.5 Componentes de Adaptación

```python
# Uso del coordinador adaptativo
from app.distributed.coordination import (
    AdaptiveClusterCoordinator,
    create_adaptive_coordinator
)

# Crear coordinador
coordinator = create_adaptive_coordinator(
    node_id="node-1",
    node_address="localhost:8001",
    target_nodes=3,
    target_replication=2
)

# Iniciar (funciona incluso solo)
await coordinator.start()

# Verificar operaciones permitidas
check = coordinator.check_operation("write")
if check["allowed"]:
    # Realizar operación
    pass
else:
    print(f"Operación no disponible: {check['reason']}")

# Obtener salud del cluster
health = coordinator.get_cluster_health()
print(f"Estado: {health['status']}, Score: {health['health_score']}")
```

---

## 11. Resumen

Esta arquitectura proporciona:

| Característica | Implementación |
|---------------|----------------|
| **Descubrimiento de Servicios** | DNS interno de Docker Swarm |
| **Alta Disponibilidad DNS** | CoreDNS como backup + caché local |
| **Balanceo de Carga** | Routing Mesh de Swarm + VIP |
| **Escalado Horizontal** | `docker service scale` |
| **Tolerancia a Fallos** | Self-healing + Raft (masters) |
| **Actualizaciones sin Downtime** | Rolling updates |
| **Seguridad** | Secrets management + overlay networks |
| **Arranque Incremental** | Single-node bootstrap + crecimiento |
| **Degradación Grácil** | Adaptación automática a recursos |
| **Tolerancia a Particiones** | Operación independiente por partición |

### Flujo de Fallback DNS:
1. **Docker DNS (127.0.0.11)** → Principal, automático
2. **CoreDNS Backup (10.0.10.50)** → Sincronizado con Swarm
3. **Archivo hosts estático** → Último recurso

Esta arquitectura garantiza que el sistema DistriSearch mantenga conectividad entre servicios incluso en escenarios de fallo del DNS interno de Docker, y se adapte dinámicamente al número de nodos disponibles.
