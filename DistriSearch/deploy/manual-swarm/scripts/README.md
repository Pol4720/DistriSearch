# Scripts de Despliegue Manual - Docker Swarm

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
│  │  → Despliega MongoDB y Redis                            │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  05-deploy-master.sh                                    │    │
│  │  → Despliega el coordinador Master                      │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  06-deploy-slave.sh [NUM_REPLICAS]                      │    │
│  │  → Despliega los nodos Slave                            │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  07-deploy-frontend.sh                                  │    │
│  │  → Despliega la interfaz web                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  VERIFICACIÓN:                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  08-verify-cluster.sh                                   │    │
│  │  → Verifica estado del cluster                          │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  09-test-distributed-features.sh                        │    │
│  │  → Prueba características distribuidas                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  LIMPIEZA (opcional):                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  10-cleanup.sh                                          │    │
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
| `04-deploy-infrastructure.sh` | Manager | Despliega MongoDB y Redis |
| `05-deploy-master.sh` | Manager | Despliega el coordinador Master |
| `06-deploy-slave.sh` | Manager | Despliega nodos Slave |
| `07-deploy-frontend.sh` | Manager | Despliega la interfaz web |
| `08-verify-cluster.sh` | Manager | Verifica estado del cluster |
| `09-test-distributed-features.sh` | Manager | Prueba funcionalidades distribuidas |
| `10-cleanup.sh` | Manager | Limpia todo el despliegue |

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
./07-deploy-frontend.sh

# Verificar
./08-verify-cluster.sh
./09-test-distributed-features.sh
```

## Puertos Requeridos

| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 2377 | TCP | Gestión del cluster Swarm |
| 7946 | TCP/UDP | Comunicación entre nodos |
| 4789 | UDP | Red overlay (VXLAN) |
| 8000 | TCP | API del Master |
| 8001 | TCP | API de los Slaves |
| 3000 | TCP | Frontend Web |

## Ver la Guía Completa

Para más detalles, consulta `../GUIA_DESPLIEGUE.md`
