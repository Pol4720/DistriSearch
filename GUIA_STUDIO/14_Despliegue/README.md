# Despliegue de DistriSearch

Esta sección cubre el proceso de despliegue en un cluster Docker Swarm multi-host.

## Resumen de pasos
0. **Configurar firewall** (si hay problemas de red - script dedicado o integrado).
1. Preparar nodos (Docker, límites, directorios).
2. Inicializar Swarm en el manager (incluye configuración de firewall).
3. Unir workers al cluster (incluye configuración de firewall).
4. Desplegar infraestructura (red overlay).
5. Desplegar Master.
6. Desplegar Slaves (Backend + Frontend integrado).
7. Verificar salud del cluster.

## Scripts de despliegue

Los scripts se encuentran en `deploy/manual-swarm/scripts/`:

| Script | Descripción |
|--------|-------------|
| `00-configure-firewall.sh` | Configura firewall para Docker Swarm (UFW/iptables/firewalld) |
| `01-prepare-node.sh` | Prepara nodos con Docker y configuraciones |
| `02-init-swarm.sh` | Inicializa Swarm en el manager (configura firewall automáticamente) |
| `03-join-swarm.sh` | Une workers al cluster (configura firewall automáticamente) |
| `04-deploy-infrastructure.sh` | Crea red overlay |
| `05-deploy-master.sh` | Despliega el coordinador Master |
| `06-deploy-slave.sh` | Despliega Slaves (opciones: `--update`, `--rebuild`, `--clean`) |
| `07-verify-cluster.sh` | Verifica estado del cluster |
| `08-test-distributed-features.sh` | Prueba funcionalidades distribuidas |
| `09-cleanup.sh` | Limpia completamente el despliegue |

## Opciones de 06-deploy-slave.sh

```bash
./06-deploy-slave.sh [NUM_REPLICAS] [--update] [--rebuild] [--clean]
```

| Opción | Descripción |
|--------|-------------|
| `NUM_REPLICAS` | Número de slaves a desplegar (default: número de workers) |
| `--update` | Forzar actualización de imagen en servicios existentes |
| `--rebuild` | Reconstruir imagen antes de desplegar |
| `--clean` | Eliminar todos los servicios slave antes de desplegar |

## Opciones de despliegue
| Método | Uso |
|--------|-----|
| `docker stack deploy` | Usa docker-compose.swarm.yml |
| Scripts manuales | Control fino, idempotentes |

## Puertos requeridos

### Docker Swarm (internos)
| Puerto | Uso |
|--------|-----|
| 2377/tcp | Gestión Swarm |
| 7946/tcp+udp | Comunicación entre nodos |
| 4789/udp | Red overlay VXLAN (Routing Mesh) - **CRÍTICO** |

### DistriSearch
| Puerto | Uso |
|--------|-----|
| 8001/tcp | Master API |
| 8081-8089/tcp | Slave HTTP (Frontend) |
| 4431-4439/tcp | Slave HTTPS (Frontend) |
| 8002-8009/tcp | Slave API (Backend) |
| 27017/tcp | MongoDB (solo red interna) |
| 6379/tcp | Redis (solo red interna) |

### Mapeo de puertos por Slave
| Slave | HTTP | HTTPS | API |
|-------|------|-------|-----|
| slave-1 | 8081 | 4431 | 8002 |
| slave-2 | 8082 | 4432 | 8003 |
| slave-N | 8080+N | 4430+N | 8001+N |

## Troubleshooting de red

Si hay problemas de conectividad en el routing mesh:

1. Ejecutar `00-configure-firewall.sh` en **TODOS** los nodos
2. Reiniciar Docker: `sudo systemctl restart docker`
3. Verificar red overlay: `docker network inspect distrisearch-network`
4. Probar conectividad UDP: `nc -zuv <otro-nodo> 4789`

Detalles paso a paso en los siguientes archivos.