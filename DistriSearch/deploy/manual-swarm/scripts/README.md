# Scripts de Despliegue Manual - Docker Swarm

## Arquitectura

Cada **Slave** contiene Backend (FastAPI) + Frontend (React/Nginx) integrados en un solo container.
No se necesita un servicio de frontend separado.

## Orden de Ejecución

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE DESPLIEGUE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EN CADA MÁQUINA:                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  01-prepare-node.sh                                     │    │
│  │  → Instala Docker, configura firewall, optimiza sistema │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN EL MANAGER (primera máquina):                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  02-init-swarm.sh <IP_MANAGER>                          │    │
│  │  → Inicializa Swarm, crea red, genera tokens            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN CADA WORKER:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  03-join-swarm.sh <IP_MANAGER> <TOKEN>                  │    │
│  │  → Une el nodo al cluster Swarm                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  EN EL MANAGER (despliegue):                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  04-deploy-infrastructure.sh                            │    │
│  │  → Despliega MongoDB y Redis del Master                 │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  05-deploy-master.sh                                    │    │
│  │  → Despliega el coordinador Master                      │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  06-deploy-slave.sh [NUM_REPLICAS]                      │    │
│  │  → Despliega Slaves (Backend+Frontend+MongoDB+Redis)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  VERIFICACIÓN:                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  07-verify-cluster.sh                                   │    │
│  │  → Verifica estado del cluster                          │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  08-test-distributed-features.sh                        │    │
│  │  → Prueba características distribuidas                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  LIMPIEZA (opcional):                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  09-cleanup.sh                                          │    │
│  │  → Elimina todo el despliegue                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Descripción de cada Script

| Script | Ejecutar en | Descripción |
|--------|-------------|-------------|
| `01-prepare-node.sh` | Todas las máquinas | Prepara el sistema: Docker, firewall, optimizaciones |
| `02-init-swarm.sh` | Solo Manager | Inicializa el cluster Swarm |
| `03-join-swarm.sh` | Solo Workers | Une workers al cluster |
| `04-deploy-infrastructure.sh` | Manager | Despliega MongoDB y Redis del Master |
| `05-deploy-master.sh` | Manager | Despliega el coordinador Master |
| `06-deploy-slave.sh` | Manager | Despliega Slaves (Backend+Frontend integrado) |
| `07-verify-cluster.sh` | Manager | Verifica estado del cluster |
| `08-test-distributed-features.sh` | Manager | Prueba funcionalidades distribuidas |
| `09-cleanup.sh` | Manager | Limpia todo el despliegue |

## Arquitectura de Almacenamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALMACENAMIENTO AP                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SQLite (Raft-replicado):                                       │
│    • Usuarios, nodos, particiones (metadatos cluster)           │
│    • Cada nodo tiene réplica sincronizada via Raft              │
│                                                                 │
│  MongoDB (LOCAL por nodo):                                      │
│    • Solo documentos asignados a ese nodo                       │
│    • Master: master-mongo                                       │
│    • Slaves: slaveN-mongodb                                     │
│                                                                 │
│  Redis (LOCAL por nodo):                                        │
│    • Cache de sesiones, vectores, resultados                    │
│    • Master: master-redis                                       │
│    • Slaves: slaveN-redis                                       │
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

# En el MANAGER
sudo ./02-init-swarm.sh 192.168.1.10

# En cada WORKER (usar el token que muestra el paso anterior)
sudo ./03-join-swarm.sh 192.168.1.10 SWMTKN-1-xxx...

# Volver al MANAGER y desplegar
./04-deploy-infrastructure.sh
./05-deploy-master.sh
./06-deploy-slave.sh

# Verificar
./07-verify-cluster.sh
./08-test-distributed-features.sh
```

## Puertos por Servicio

### Master (en nodo Manager)
| Puerto | Uso |
|--------|-----|
| 8000 | API Master (FastAPI) |
| 27017 | MongoDB Master |
| 6379 | Redis Master |
| 50051 | gRPC |

### Slaves (en Workers)
| Puerto | Uso |
|--------|-----|
| 8081, 8082... | Frontend HTTP (Nginx) - Slave 1, 2... |
| 4431, 4432... | Frontend HTTPS (Nginx) - Slave 1, 2... |
| 8001, 8002... | API Backend (FastAPI) - Slave 1, 2... |

### Docker Swarm
| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 2377 | TCP | Gestión del cluster Swarm |
| 7946 | TCP/UDP | Comunicación entre nodos |
| 4789 | UDP | Red overlay (VXLAN) |

## Acceso a la Aplicación

El frontend está integrado en cada slave. Accede a cualquier slave:

```
http://<worker-ip>:8081   # Slave 1
http://<worker-ip>:8082   # Slave 2
...
```

## Ver la Guía Completa

Para más detalles, consulta `../GUIA_DESPLIEGUE.md`
