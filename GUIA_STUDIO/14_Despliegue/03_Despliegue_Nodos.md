# Despliegue de Servicios

## Script automatizado para Slaves

```bash
./06-deploy-slave.sh [NUM_REPLICAS] [--update] [--rebuild] [--clean]
```

### Opciones disponibles
| Opción | Descripción |
|--------|-------------|
| `NUM_REPLICAS` | Número de slaves (default: número de workers) |
| `--update` | Forzar actualización de imagen existente |
| `--rebuild` | Reconstruir imagen desde Dockerfile |
| `--clean` | Eliminar todos los slaves antes de desplegar |

### Qué despliega por cada Slave:
1. **MongoDB LOCAL** (`slave{N}-mongodb`) - Almacena documentos locales
2. **Redis LOCAL** (`slave{N}-redis`) - Caché local
3. **Slave Service** (`distrisearch-slave-{N}`) - Backend+Frontend integrado

## Arquitectura de cada Slave

```
┌─────────────────────────────────────────────┐
│            distrisearch-slave-N             │
│  ┌────────────────┐  ┌──────────────────┐   │
│  │  Nginx (80/443)│  │  FastAPI (8000)  │   │
│  │   Frontend     │  │    Backend       │   │
│  └────────────────┘  └──────────────────┘   │
│          │                   │              │
│  ┌───────┴───────┐   ┌──────┴───────┐       │
│  │ MongoDB LOCAL │   │  Redis LOCAL │       │
│  └───────────────┘   └──────────────┘       │
└─────────────────────────────────────────────┘
```

## Mapeo de puertos por Slave

| Slave | HTTP | HTTPS | API |
|-------|------|-------|-----|
| slave-1 | 8081 | 4431 | 8002 |
| slave-2 | 8082 | 4432 | 8003 |
| slave-N | 8080+N | 4430+N | 8001+N |

## Desplegar Master

```bash
./05-deploy-master.sh
```

O manualmente:
```bash
docker service create \
    --name distrisearch-master \
    --network distrisearch-network \
    --publish published=8001,target=8001 \
    --env NODE_ROLE=master \
    --env RAFT_ENABLED=true \
    distrisearch/master:latest
```

## Desplegar Slaves (manual)

```bash
docker service create \
    --name distrisearch-slave-1 \
    --network distrisearch-network \
    --publish published=8081,target=80 \
    --publish published=4431,target=443 \
    --publish published=8002,target=8000 \
    --env NODE_ID=slave-1 \
    --env NODE_ROLE=slave \
    --env MASTER_HOST=distrisearch-master \
    --env MONGODB_URI=mongodb://slave1-mongodb:27017/distrisearch_slave1 \
    --env REDIS_URL=redis://slave1-redis:6379 \
    distrisearch/slave:latest
```

## Verificar despliegue

```bash
# Ver servicios
docker service ls

# Ver tareas
docker service ps distrisearch-slave-1

# Ver logs
docker service logs -f distrisearch-slave-1
```

## Actualizar slaves existentes

```bash
# Forzar actualización de imagen
./06-deploy-slave.sh --update

# Reconstruir imagen y desplegar
./06-deploy-slave.sh --rebuild

# Eliminar todo y redesplegar
./06-deploy-slave.sh --clean
```

## Con docker stack

```bash
docker stack deploy -c docker-compose.swarm.yml distrisearch
```