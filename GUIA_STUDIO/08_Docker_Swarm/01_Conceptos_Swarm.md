# Conceptos fundamentales de Docker Swarm

## Nodos Manager vs Worker
- **Managers**: mantienen el estado del cluster vía Raft interno, programan tareas, exponen la API y pueden ejecutar contenedores.
- **Workers**: ejecutan contenedores asignados por los managers; no participan en decisiones de orquestación.
- Recomendación: 3 o 5 managers (tolerancia 1 o 2 caídas) y N workers según carga.

## Servicios y tareas
- **Servicio**: definición declarativa (imagen, réplicas, redes, volúmenes, deploy).
- **Tarea**: instancia de un contenedor de un servicio en un nodo específico.

## Funcionalidades clave
| Característica | Beneficio |
|----------------|-----------|
| DNS integrado | "master" → IP sin configurar resolvers externos |
| Routing mesh | Petición a cualquier nodo llega al servicio correcto |
| Rolling updates | Actualiza réplicas de a poco sin downtime |
| Self-healing | Reinicia o reubica contenedores caídos |
| Secrets | Variables sensibles cifradas en memoria de contenedores |

## Secrets usados en DistriSearch
- `mongodb-password`, `jwt-secret`, `tls-cert`, `tls-key`, `mongodb-keyfile` (externos; crearlos antes del deploy).

## Inicialización típica
```bash
docker swarm init --advertise-addr <IP>
docker swarm join-token worker   # para agregar workers
docker swarm join-token manager  # para agregar managers
docker stack deploy -c docker-compose.swarm.yml distrisearch
```