# Scripts de Despliegue Manual - Docker Swarm

## Arquitectura HA (Alta Disponibilidad)

Sistema distribuido donde **TODOS los nodos son MANAGERS** para máxima tolerancia a fallos.
Cada nodo contiene Backend (FastAPI) + Frontend (React/Nginx) integrados en un solo container.
El algoritmo Bully elige dinámicamente quién es el líder del cluster.

## Orden de Ejecución

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE DESPLIEGUE HA                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EN CADA MÁQUINA:                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  01-prepare-node.sh                                     │    │
│  │  → Instala Docker, configura firewall, optimiza sistema │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN EL PRIMER NODO (Manager inicial):                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  02-init-swarm.sh <IP_MANAGER>                          │    │
│  │  → Inicializa Swarm, crea red, genera tokens            │    │
│  │  → IMPORTANTE: Usa el MANAGER_TOKEN para HA             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN CADA NODO ADICIONAL (unir como MANAGER):                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  03-join-swarm.sh <IP_MANAGER> <MANAGER_TOKEN>          │    │
│  │  → Une el nodo al cluster como MANAGER (para HA)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN CUALQUIER MANAGER (distribuir imágenes):                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  03b-distribute-images.sh                               │    │
│  │  → Distribuye imágenes Docker a todos los nodos         │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  03c-create-secrets.sh                                  │    │
│  │  → Crea secrets para TLS y JWT                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN CUALQUIER MANAGER (despliegue):                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  04-deploy-infrastructure-ha.sh                         │    │
│  │  → Despliega CoreDNS, Redis Coordinador, Load Balancer  │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  05-deploy-nodes-ha.sh                                  │    │
│  │  → Despliega nodos DistriSearch (Backend+Frontend+DB)   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  VERIFICACIÓN:                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  06-verify-ha-cluster.sh                                │    │
│  │  → Verifica estado del cluster HA                       │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  07-test-failover.sh                                    │    │
│  │  → Prueba tolerancia a fallos                           │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  08-test-distributed-features.sh                        │    │
│  │  → Prueba características distribuidas                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  LIMPIEZA (opcional):                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  09-cleanup-ha.sh / 10-full-cleanup.sh                  │    │
│  │  → Elimina todo el despliegue                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Descripción de cada Script

| Script | Ejecutar en | Descripción |
|--------|-------------|-------------|
| `01-prepare-node.sh` | Todas las máquinas | Prepara el sistema: Docker, firewall, optimizaciones |
| `02-init-swarm.sh` | Primer nodo | Inicializa el cluster Swarm |
| `03-join-swarm.sh` | Nodos adicionales | Une nodos como MANAGERS (para HA) |
| `03b-distribute-images.sh` | Cualquier Manager | Distribuye imágenes Docker |
| `03c-create-secrets.sh` | Cualquier Manager | Crea secrets TLS y JWT |
| `04-deploy-infrastructure-ha.sh` | Cualquier Manager | Despliega infraestructura HA |
| `05-deploy-nodes-ha.sh` | Cualquier Manager | Despliega nodos DistriSearch |
| `06-verify-ha-cluster.sh` | Cualquier Manager | Verifica estado del cluster |
| `07-test-failover.sh` | Cualquier Manager | Prueba tolerancia a fallos |
| `08-test-distributed-features.sh` | Cualquier Manager | Prueba funcionalidades distribuidas |
| `09-cleanup-ha.sh` | Cualquier Manager | Limpia servicios |
| `10-full-cleanup.sh` | Cualquier Manager | Limpieza completa |

## Arquitectura de Almacenamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALMACENAMIENTO HA                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SQLite (LOCAL por nodo):                                       │
│    • Usuarios sincronizados entre nodos                         │
│    • Cada nodo tiene su propia base de usuarios                 │
│                                                                 │
│  MongoDB (LOCAL por nodo):                                      │
│    • Documentos con replicación k=2                             │
│    • Cada documento existe en 2 nodos distintos                 │
│    • nodeN-mongodb                                              │
│                                                                 │
│  Redis (LOCAL + Coordinador):                                   │
│    • nodeN-redis: Cache local                                   │
│    • coordinator-redis: Sesiones globales                       │
│                                                                 │
│  Gossip Protocol:                                               │
│    • UserDocumentRegistry (mapeo user → documentos)             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Uso Rápido

```bash
# Hacer scripts ejecutables
chmod +x *.sh

# En TODAS las máquinas
sudo ./01-prepare-node.sh

# En el PRIMER NODO (Manager inicial)
sudo ./02-init-swarm.sh 192.168.1.10
# ¡IMPORTANTE! Copia el MANAGER_TOKEN para HA

# En cada NODO ADICIONAL (unir como MANAGER para HA)
sudo ./03-join-swarm.sh 192.168.1.10 SWMTKN-1-xxx...

# Desde cualquier MANAGER: distribuir imágenes y crear secrets
./03b-distribute-images.sh
./03c-create-secrets.sh

# Desplegar infraestructura y nodos
./04-deploy-infrastructure-ha.sh
./05-deploy-nodes-ha.sh

# Verificar
./06-verify-ha-cluster.sh
./07-test-failover.sh
./08-test-distributed-features.sh
```

## Puertos por Servicio

### Nodos DistriSearch
| Puerto | Uso |
|--------|-----|
| 8001, 8002, 8003 | API Backend (FastAPI) - Node 1, 2, 3 |
| 8081, 8082, 8083 | Frontend HTTP (Nginx) - Node 1, 2, 3 |
| 4431, 4432, 4433 | Frontend HTTPS (Nginx) - Node 1, 2, 3 |

### Infraestructura
| Puerto | Uso |
|--------|-----|
| 80 | Load Balancer HTTP |
| 443 | Load Balancer HTTPS |
| 6379 | Redis Coordinator |
| 53 | CoreDNS |

### Docker Swarm
| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 2377 | TCP | Gestión del cluster Swarm |
| 7946 | TCP/UDP | Comunicación entre nodos |
| 4789 | UDP | Red overlay (VXLAN) |

## Acceso a la Aplicación

El frontend está integrado en cada nodo. Accede mediante Load Balancer o directamente:

```
# Via Load Balancer (recomendado)
http://<cualquier-ip>:80   

# Acceso directo a nodos
http://<cualquier-ip>:8081   # Node 1
http://<cualquier-ip>:8082   # Node 2
http://<cualquier-ip>:8083   # Node 3
```

## Alta Disponibilidad (HA)

Con todos los nodos como **MANAGERS**:
- El cluster sigue funcionando si falla cualquier nodo
- Para 3 nodos, tolera 1 fallo de manager
- Para 5 nodos, tolera 2 fallos de manager
- El algoritmo Bully elige líder automáticamente

## Ver la Guía Completa

Para más detalles, consulta `../GUIA_DESPLIEGUE.md`
